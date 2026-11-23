"""Prescribed human decisions and observed work for an exact Emergency incident."""

from uuid import UUID

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.core.views import accessible_case
from apps.identity.services import active_case_grants, require
from apps.pmo.models import ChangeClosure, DeliveryCandidate, EmergencyAuthorization, EmergencyFollowup
from apps.pmo.models import EmergencyFollowupCompletion, EmergencyOutcome, EmergencyProfile
from apps.pmo import emergency_followups
from apps.policy.document_validators import ROLES
from apps.workflows import factory_emergency as workflow, factory_emergency_intake as intake

from .commands import require_line
from .delivery import NOTE, PROOF, proof_rows, recorded
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID as UUID_SCHEMA, Problem, array, choice, endpoint, nullable, obj
from .intake import START_RESULT, progress_result
from .reviews import VERDICT, VERSIONS
from .work import PAGE, WORK_RESULT, page_number


PREAUTH_ROLE = choice('Incident Lead', 'Engineering Lead', 'CTO', *(f'GLPI exception:{role}' for role in ROLES))
AUTHORITY = choice(*ROLES)
HUMAN_ACTIONS = {
    'preauthorization_decision': ('emergency.decide', 'emergency_decision'),
    'authorize': ('emergency.authorize', None),
    'capture_outcome': ('emergency.record_outcome', 'change_implementation'),
    'record_review': ('emergency.review', 'post_implementation_review'),
    'retrospective_decision': ('emergency.retrospective_decide', 'emergency_decision'),
    'reconcile_retrospective': ('emergency.manage', None),
}
PROOF_AND_NOTE = {'evidence_id': ID, 'note': NOTE}
IMPACT = {'customers_affected': nullable({'type': 'integer', 'minimum': 0, 'maximum': 2**31 - 1}),
          'side_effects': nullable(NOTE)}
FIELDS = {
    'preauthorization_decision': {**PROOF_AND_NOTE, 'role': PREAUTH_ROLE, 'authority_role': AUTHORITY, 'verdict': VERDICT},
    'authorize': {},
    'capture_outcome': {**PROOF_AND_NOTE, 'implemented_at': DATETIME, **IMPACT},
    'record_review': PROOF_AND_NOTE,
    'retrospective_decision': {**PROOF_AND_NOTE, 'role': choice('Product', 'Engineering Lead'), 'verdict': VERDICT},
    'reconcile_retrospective': {},
}
OPTION = obj({'role': PREAUTH_ROLE, 'authority_role': AUTHORITY, 'verdicts': array(VERDICT)})
RECORD = obj({'id': ID, 'role': PREAUTH_ROLE, 'authority_role': AUTHORITY, 'verdict': VERDICT})
REF = {**TEXT, 'maxLength': 160}


def intake_scope(actor, case_id):
    case = accessible_case(actor, case_id)
    if case.kind != 'project':
        raise Http404
    intake._request_authority(actor, case)
    return case


@endpoint(response=obj({'revision': REVISION, 'incidents': array(PROOF, limit=40)}),
          summary='Read authorised incident sources for a new Emergency request')
def incidents(request, case_id):
    case = intake_scope(request.user, case_id)
    return {'revision': case.revision, 'incidents': proof_rows(intake._sources(case, 'incident')[:40])}


@endpoint(method='POST', request=obj({'revision': REVISION, 'request_id': UUID_SCHEMA, 'incident_id': ID,
                                     'module': REF, 'plan': NOTE}), status=201,
          response=obj({'version_id': ID, 'revision': REVISION}),
          summary='Open one incident-linked Emergency request using its current project revision')
def request_change(request, case_id, *, body):
    actor = request.user
    case = intake_scope(actor, case_id)
    revision = intake.request_change(actor, case.pk, body['revision'], UUID(body['request_id']), body['incident_id'],
                                     body['module'], body['plan'])
    case.refresh_from_db(fields=['revision'])
    return {'version_id': revision.pk, 'revision': case.revision}


@endpoint(response=obj({'revision': REVISION, 'incident_id': ID, 'module': TEXT, 'plan': TEXT,
    'profile_id': nullable(ID), 'work_id': nullable(ID), 'can_classify': BOOLEAN,
    'candidates': array(obj({'id': ID, 'reference': TEXT}), limit=40), 'evidence': array(PROOF, limit=40)}),
    summary='Read the requester-owned Emergency plan and exact classification references')
def classification(request, case_id, version_id):
    actor = request.user
    case = intake_scope(actor, case_id)
    revision = intake._request_scope(actor, case, version_id)
    profile_id = EmergencyProfile.objects.filter(version=revision).order_by('-pk').values_list('pk', flat=True).first()
    work = intake._work_for(case, revision)
    can_classify = bool(active_case_grants(actor, [case.pk], actions=['emergency.manage']))
    candidates = list(DeliveryCandidate.objects.filter(case=case).order_by('-pk').values('id', 'reference')[:40]) if can_classify else []
    return {'revision': case.revision, 'incident_id': revision.incident_id, 'module': revision.module,
            'plan': revision.description, 'profile_id': profile_id, 'work_id': work.pk if work else None,
            'can_classify': can_classify, 'candidates': candidates,
            'evidence': proof_rows(intake._sources(case, 'incident_classification')[:40]) if can_classify else []}


@endpoint(method='POST', request={'oneOf': [obj({'revision': REVISION, 'profile_id': ID}),
    obj({'revision': REVISION, 'candidate_id': ID, 'evidence_id': ID, 'critical_production': nullable(BOOLEAN),
         'p1': nullable(BOOLEAN), 'note': NOTE})]}, response=START_RESULT, status=201,
    summary='Record exact incident classification or use its current profile and start the background work')
def classify(request, case_id, version_id, *, body):
    actor = request.user
    case = intake_scope(actor, case_id)
    require(actor, case, 'emergency.manage')
    values = {'profile': body.get('profile_id')}
    if not values['profile']:
        values.update({'candidate': get_object_or_404(DeliveryCandidate, case=case, pk=body['candidate_id']),
                       'evidence': get_object_or_404(intake._sources(case, 'incident_classification'), pk=body['evidence_id']),
                       'critical_production': body['critical_production'], 'p1': body['p1'], 'note': body['note']})
    work = intake.classify_request(actor, case.pk, version_id, body['revision'], values)
    return progress_result(actor, work, True)


@endpoint(response=obj({**VERSIONS, 'profile_id': ID, 'change_version_id': ID, 'incident_id': ID,
    'critical_production': nullable(BOOLEAN), 'p1': nullable(BOOLEAN), 'stage': TEXT, 'finding': {'type': 'string'},
    'actions': array(choice(*HUMAN_ACTIONS)), 'options': array(OPTION), 'decisions': array(RECORD),
    'authorization_id': nullable(ID), 'recorded_authorizations': array(ID, limit=20),
    'outcome_id': nullable(ID), 'recorded_outcomes': array(ID, limit=20),
    'outcome_impact': nullable(obj(IMPACT)),
    'authorization_history': array(obj({'id': ID, 'by': TEXT, 'at': DATETIME}), limit=20),
    'outcome_history': array(obj({'id': ID, 'by': TEXT, 'at': DATETIME}), limit=20),
    'document_version_id': nullable(ID), 'review_verdicts': array(VERDICT),
    'receipt_ids': array(ID, limit=30), 'evidence': array(PROOF, limit=50)}),
    summary='Read the incident, prescribed decisions, actual outcome and retained publication receipts')
def detail(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, workflow.DEFINITION)
    with limit_queries(900):
        panel = workflow.projection(actor, work, include_worker=False)
        profile = panel['profile']
        status = panel['status']
        grants = {action for _, action in active_case_grants(actor, [work.case_id])}
        allowed, current = workflow.preauthorization_decisions(actor, work.case, profile)
        actions = [name for name, (action, _) in HUMAN_ACTIONS.items() if panel['human'].get(name) and action in grants]
        if 'preauthorization_decision' in actions and not allowed:
            actions.remove('preauthorization_decision')
        if not status.get('outcome'):
            actions = [name for name in actions if name not in ('record_review', 'retrospective_decision',
                                                                 'reconcile_retrospective')]
        selected_kinds = [HUMAN_ACTIONS[action][1] for action in actions if HUMAN_ACTIONS[action][1]]
        proof = public_evidence(work.case.evidence.filter(kind__in=selected_kinds)).only('id', 'kind', 'version').order_by('-pk')[:50]
        authorizations = list(EmergencyAuthorization.objects.filter(profile=profile).select_related('actor').order_by('-pk')[:20])
        outcomes = list(EmergencyOutcome.objects.filter(profile=profile).select_related('actor').order_by('-pk')[:20])
        def history(rows):
            return [{'id': row.pk, 'by': row.actor.get_full_name() or row.actor.get_username(),
                     'at': row.created_at} for row in rows]
        outcome_id = panel['data']['inputs']['outcome_id']
        impact = EmergencyOutcome.objects.filter(profile=profile, pk=outcome_id).values(*IMPACT).first() if outcome_id else None
        if work.cancel_requested or work.lease_until and work.lease_until > timezone.now():
            allowed = []
        return {'expected_revision': work.revision, 'case_revision': work.case.revision,
                'profile_id': profile.pk, 'change_version_id': profile.version_id, 'incident_id': profile.version.incident_id,
                'critical_production': profile.critical_production, 'p1': profile.p1, 'stage': status['stage'],
                'finding': status.get('finding', ''), 'actions': actions, 'options': allowed,
                'decisions': [{'id': row.pk, 'role': row.role, 'authority_role': row.authority_role,
                               'verdict': row.verdict} for row in current],
                'authorization_id': panel['data']['inputs']['authorization_id'],
                'recorded_authorizations': [row.pk for row in authorizations],
                'outcome_id': outcome_id, 'recorded_outcomes': [row.pk for row in outcomes], 'outcome_impact': impact,
                'authorization_history': history(authorizations), 'outcome_history': history(outcomes),
                'document_version_id': panel['document'].pk if panel['document'] else None,
                'review_verdicts': panel['review_verdicts'], 'receipt_ids': [row.pk for row in panel['receipts'][:30]],
                'evidence': proof_rows(proof)}


@endpoint(method='POST', request={'oneOf': [obj({'action': {'const': action}, **VERSIONS, 'profile_id': ID, **fields},
    optional=tuple(IMPACT) if action == 'capture_outcome' else ())
    for action, fields in FIELDS.items()]}, response=obj({**WORK_RESULT['properties'], 'record_id': ID}), status=201,
    summary='Record the exact human Emergency decision, implementation evidence or retrospective')
def command(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, workflow.DEFINITION)
    action = body['action']
    values = {key: body[key] for key in FIELDS[action] if key in body}
    if 'evidence_id' in values:
        evidence_id = values.pop('evidence_id')
        if not public_evidence(work.case.evidence.filter(pk=evidence_id, kind=HUMAN_ACTIONS[action][1])).exists():
            raise Problem(422, 'invalid_input', 'Choose available evidence for this Emergency step.')
        values['evidence'] = evidence_id
    row = workflow.human_action(actor, work.pk, body['expected_revision'], body['case_revision'], body['profile_id'],
                                action, values, pending_only=True)
    return recorded(work, row)


FOLLOWUP = obj({'id': ID, 'version_id': ID, 'supersedes_id': nullable(ID), 'closure_id': nullable(ID), 'note': TEXT})
FOLLOWUP_FIELDS = {
    'create': {'reference': REF, 'category': choice('Normal', 'Standard'), 'module': REF,
               'description': NOTE, 'note': NOTE, 'evidence_id': ID},
    'link_revision': {'followup_id': ID, 'version_id': ID, 'note': NOTE},
    'complete': {'followup_id': ID, 'closure_id': ID, 'note': NOTE},
}


def followup_scope(actor, case_id, outcome_id):
    case = accessible_case(actor, case_id)
    require(actor, case, 'emergency.read')
    outcome = get_object_or_404(EmergencyOutcome, profile__version__change__case=case, pk=outcome_id)
    return case, outcome


@endpoint(response=obj({'revision': REVISION, 'outcome_id': ID, 'can_manage': BOOLEAN,
    'records': array(FOLLOWUP, limit=20), 'evidence': array(PROOF, limit=30), 'next_page': nullable(PAGE)}),
    query={'page': PAGE}, summary='Read ordinary scope or cost changes linked to the exact Emergency outcome')
def followups(request, case_id, outcome_id):
    case, outcome = followup_scope(request.user, case_id, outcome_id)
    manage = bool(active_case_grants(request.user, [case.pk], actions=['emergency.followup']))
    page = page_number(request)
    offset = (page - 1) * 20
    rows = list(EmergencyFollowup.objects.filter(outcome=outcome).order_by('-pk')[offset:offset + 21])
    completions = dict(EmergencyFollowupCompletion.objects.filter(followup__in=rows[:20]).values_list('followup_id', 'closure_id'))
    evidence = public_evidence(case.evidence.filter(kind='change_request')).only('id', 'kind', 'version').order_by('-pk')[:30]
    return {'revision': case.revision, 'outcome_id': outcome.pk, 'can_manage': manage,
            'records': [{'id': row.pk, 'version_id': row.version_id, 'supersedes_id': row.supersedes_id,
                         'closure_id': completions.get(row.pk), 'note': row.note} for row in rows[:20]],
            'evidence': proof_rows(evidence) if manage else [],
            'next_page': page + 1 if len(rows) > 20 and page < PAGE['maximum'] else None}


@endpoint(response=obj({'revision': REVISION, 'followup_id': ID, 'current_version_id': nullable(ID),
                        'recorded_closures': array(ID, limit=20)}),
          summary='Read the exact current ordinary change and its recorded closure options')
def followup_options(request, case_id, outcome_id, followup_id):
    case, outcome = followup_scope(request.user, case_id, outcome_id)
    require(request.user, case, 'emergency.followup')
    item = get_object_or_404(EmergencyFollowup.objects.select_related('version__change'), outcome=outcome, pk=followup_id)
    closures = list(ChangeClosure.objects.filter(authorization__version_id=item.version_id).order_by('-pk')
                    .values_list('pk', flat=True)[:20])
    return {'revision': case.revision, 'followup_id': item.pk, 'current_version_id': item.version.change.current_id,
            'recorded_closures': closures}


@endpoint(method='POST', request={'oneOf': [obj({'action': {'const': action}, 'revision': REVISION, **fields})
    for action, fields in FOLLOWUP_FIELDS.items()]}, response=obj({'id': ID, 'revision': REVISION}), status=201,
    summary='Open, revise or complete an ordinary change for an exact Emergency outcome')
def followup_command(request, case_id, outcome_id, *, body):
    actor = request.user
    case, outcome = followup_scope(actor, case_id, outcome_id)
    require(actor, case, 'emergency.followup')
    args = (actor, case.pk)
    action, revision = body['action'], body['revision']
    if action == 'create':
        if not public_evidence(case.evidence.filter(pk=body['evidence_id'], kind='change_request')).exists():
            raise Problem(422, 'invalid_input', 'Choose available proof of the ordinary change request.')
        row = emergency_followups.create_followup(*args, outcome.pk, body['reference'], body['category'], body['module'],
                                                 body['description'], body['note'], body['evidence_id'], revision)
    else:
        item = get_object_or_404(EmergencyFollowup, outcome=outcome, pk=body['followup_id'])
        if action == 'link_revision':
            row = emergency_followups.link_followup_revision(*args, item.pk, body['version_id'], body['note'], revision)
        else:
            row = emergency_followups.complete_followup(*args, item.pk, body['closure_id'], body['note'], revision)
    case.refresh_from_db(fields=['revision'])
    return {'id': row.pk, 'revision': case.revision}
