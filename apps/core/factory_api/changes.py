"""Standard and Normal Change human checkpoints over the native work."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.core.views import accessible_case
from apps.documents.models import PublicationReceipt
from apps.identity.services import active_case_grants, require
from apps.pmo import change_applicability, change_impacts, change_signatures, changes, standard_changes
from apps.pmo.models import ChangeAuthorization, ChangeRequest, ChangeVersion
from apps.policy.change_validators import REUSABLE_ROLES
from apps.policy.services import decision_authority
from apps.workflows import factory_change as native
from apps.workflows.factory_progress import wake_waiting

from .commands import require_line
from .delivery import NOTE, PROOF, proof_rows, recorded
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, array, choice, endpoint, nullable, obj
from .reviews import VERSIONS
from .work import WORK_RESULT


VERDICT = choice('approve', 'return', 'reject')
CONTRIBUTOR = choice(*changes.CONTRIBUTORS)
ROLE = choice(*changes.DECISION_ROLES)
PURPOSE = choice('notice', 'go_live')
IMPACT = obj({'team': CONTRIBUTOR, 'status': TEXT, 'assessment_id': nullable(ID), 'summary': nullable(TEXT),
              'effort': nullable({'type': 'string', 'maxLength': 32})})
DOCUMENT = obj({'id': ID, 'purpose': PURPOSE, 'verdicts': array(VERDICT), 'receipt_ids': array(ID)})
DECISION = obj({'role': ROLE, 'status': TEXT, 'verdicts': array(VERDICT)})
ACTUAL_SIGNATURE = obj({'source_system': TEXT, 'source_reference': TEXT, 'decision_id': TEXT,
                        'decision_version': TEXT, 'signer_reference': TEXT, 'signed_at': DATETIME})
CATEGORY = choice('Standard', 'Normal')
STANDARD_ROLE = choice(*REUSABLE_ROLES)
CATALOGUE_KEY = {**TEXT, 'maxLength': 160}


def case_for(actor, case_id):
    case = accessible_case(actor, case_id, source_action='change.read')
    require(actor, case, 'change.read')
    return case


@endpoint(response=obj({'id': ID, 'change_id': ID, 'reference': TEXT, 'number': REVISION,
    'category': choice('Standard', 'Normal', 'Emergency'), 'module': TEXT, 'description': TEXT,
    'current': BOOLEAN, 'evidence_id': ID}), summary='Read a directly selected authorised change version and its source')
def version(request, case_id, version_id):
    case = case_for(request.user, case_id)
    row = get_object_or_404(ChangeVersion.objects.select_related('change').filter(
        change__case=case, evidence_id__in=public_evidence(case.evidence.all()).values('pk')), pk=version_id)
    return {'id': row.pk, 'change_id': row.change_id, 'reference': row.change.reference, 'number': row.number,
            'category': row.category, 'module': row.module, 'description': row.description,
            'current': row.change.current_id == row.pk, 'evidence_id': row.evidence_id}


@endpoint(response=obj({'case_revision': REVISION, 'records': array(obj({'id': ID, 'version_id': ID, 'reference': TEXT,
    'category': CATEGORY, 'module': TEXT, 'description': TEXT}), limit=50), 'evidence': array(PROOF, limit=50),
    'catalogue': array(obj({'key': CATALOGUE_KEY, 'module': TEXT, 'roles': array(STANDARD_ROLE)})),
    'catalogue_finding': {'type': 'string'}}),
    summary='Read existing ordinary changes and configured Standard procedures for intake')
def register(request, case_id):
    case = case_for(request.user, case_id)
    proof = public_evidence(case.evidence.filter(kind__in=('change_request', 'change_preapproval', 'change_procedure_match')))
    current = ChangeRequest.objects.filter(case=case, current__category__in=CATEGORY['enum'],
                                           current__evidence_id__in=proof.values('pk')).select_related('current')
    try:
        entries, gates, _ = standard_changes.catalogue(case)
        catalogue = [{'key': key, 'module': value['module'], 'roles': next(
            (row['roles'] for row in gates if row['catalogue_key'] == key), [])} for key, value in entries.items()]
        finding = ''
    except (PermissionDenied, ValidationError) as exc:
        catalogue, finding = [], native.finding(exc)
    return {'case_revision': case.revision, 'records': [
        {'id': row.pk, 'version_id': row.current_id, 'reference': row.reference, 'category': row.current.category,
         'module': row.current.module, 'description': row.current.description} for row in current.order_by('-pk')[:50]],
        'evidence': proof_rows(proof.only('id', 'kind', 'version').order_by('-pk')[:50]),
        'catalogue': catalogue, 'catalogue_finding': finding}


@endpoint(method='POST', request={'oneOf': [
    obj({'action': {'const': 'capture'}, 'case_revision': REVISION, 'reference': CATALOGUE_KEY, 'category': CATEGORY,
         'module': CATALOGUE_KEY, 'description': NOTE, 'reason': NOTE, 'evidence_id': ID}),
    obj({'action': {'const': 'preapprove'}, 'case_revision': REVISION, 'key': CATALOGUE_KEY, 'role': STANDARD_ROLE,
         'verdict': VERDICT, 'evidence_id': ID, 'note': NOTE}),
    obj({'action': {'const': 'bind_standard'}, 'case_revision': REVISION, 'version_id': ID, 'key': CATALOGUE_KEY,
         'evidence_id': ID, 'note': NOTE}),
]}, response=obj({'id': ID, 'case_revision': REVISION}), status=201,
    summary='Record an ordinary change, human Standard procedure preapproval or exact procedure match')
def intake(request, case_id, *, body):
    actor = request.user
    case = case_for(actor, case_id)
    expected = body['case_revision']
    if body['action'] == 'capture':
        row = changes.log_change(actor, case.pk, body['reference'], body['category'], body['module'],
                                 body['description'], body['reason'], body['evidence_id'], expected)
    elif body['action'] == 'preapprove':
        row = standard_changes.preapprove(actor, case.pk, body['key'], body['role'], body['verdict'],
                                          body['evidence_id'], body['note'], expected)
    else:
        row = standard_changes.bind_standard(actor, case.pk, body['version_id'], body['key'], body['evidence_id'],
                                             body['note'], expected)
    case.refresh_from_db(fields=['revision'])
    return {'id': row.pk, 'case_revision': case.revision}


def decision_choices(actor, work, version, grants):
    if version.category != 'Normal' or version.change.current_id != version.pk:
        return []
    try:
        changes.current_change(work.case, version.pk)
        rows = changes.normal_decision_status(version)
    except (PermissionDenied, ValidationError):
        return []
    can_act = 'change.decide' in grants and not work.cancel_requested and work.status not in (
        'verified', 'cancelled', 'followup_needed') and not (work.lease_until and work.lease_until > timezone.now())
    result = []
    for row in rows:
        verdicts = []
        if can_act:
            for verdict in VERDICT['enum']:
                try:
                    decision_authority(actor, work.case, row['role'], verdict)
                except (PermissionDenied, ValidationError):
                    continue
                verdicts.append(verdict)
        result.append({'role': row['role'], 'status': row['status'], 'verdicts': verdicts})
    return result


@endpoint(response=obj({**VERSIONS, 'change_id': ID, 'change_version_id': ID, 'category': choice('Standard', 'Normal'),
    'stage': TEXT, 'finding': {'type': 'string'}, 'next_action': TEXT, 'authorization_id': nullable(ID),
    'authorization_choices': array(ID, limit=20), 'impact': array(IMPACT, limit=4), 'assessors': array(CONTRIBUTOR),
    'decisions': array(DECISION), 'documents': array(DOCUMENT, limit=2), 'evidence': array(PROOF, limit=50),
    'can_close': BOOLEAN, 'closure_id': nullable(ID), 'can_restart': BOOLEAN, 'can_authorize': BOOLEAN,
    'deployment_authorized': {'const': False}, 'jobs': array(obj({'id': ID, 'status': TEXT, 'can_retry': BOOLEAN}), limit=30)}),
    summary='Read current change impact, required decisions, notices, implementation and closure checkpoint')
def detail(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    with limit_queries(1200):
        panel = native.projection(actor, work)
        version, selected = panel['version'], panel['data']
        if version.category == 'Emergency':
            raise ValidationError('Open the separate Emergency preauthorization work.')
        grants = {action for _, action in active_case_grants(actor, [work.case_id])}
        authorizations = ChangeAuthorization.objects.filter(version=version).order_by('-pk')
        auth = selected['inputs']['authorization_id']
        current = version.change.current_id == version.pk
        impact = change_impacts.impact_rows(actor, work.case, version) if current and version.category == 'Normal' else []
        decisions = decision_choices(actor, work, version, grants)
        proof = public_evidence(work.case.evidence.filter(kind__in=('change_request', 'change_assessment', 'change_decision',
            'plan', 'costing', 'change_implementation', 'change_validation', 'document', 'signature'))).only('id', 'kind', 'version')
        closed = native.ChangeClosure.objects.filter(authorization_id=auth).values_list('pk', flat=True).first() if auth else None
        return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'change_id': version.change_id,
                'change_version_id': version.pk, 'category': version.category, 'stage': panel['status']['stage'],
                'finding': panel['finding'] or panel['status']['finding'], 'next_action': panel['next_action'],
                'authorization_id': auth, 'authorization_choices': list(authorizations.values_list('pk', flat=True)[:20]) if current else [],
                'impact': [{'team': item['team'], 'status': item['status'], 'summary': item['summary'],
                            'effort': item['effort'], 'assessment_id': item['record'].pk if item['record'] else None}
                           for item in impact],
                'assessors': [name for name in changes.CONTRIBUTORS if current and f'change.assess:{name}' in grants],
                'decisions': decisions, 'documents': [{'id': item['version'].pk, 'purpose': item['purpose'],
                    'verdicts': item['verdicts'], 'receipt_ids': [row.pk for row in item['receipts']]}
                    for item in panel['documents']], 'evidence': proof_rows(proof.order_by('-pk')[:50]),
                'can_close': panel['can_close'], 'closure_id': closed if not panel['readiness_changed'] else None,
                'can_restart': panel['can_restart'], 'can_authorize': 'change.authorize' in grants and current
                    and not work.cancel_requested and not any(row['status'] == 'Rejected' for row in decisions),
                'deployment_authorized': False,
                'jobs': [{'id': job.pk, 'status': job.status, 'can_retry': job.can_retry} for job in panel['jobs'][:30]]}


FLAG = nullable(BOOLEAN)
SCOPE = nullable(array({**TEXT, 'maxLength': 240}, limit=100))
HUMAN = {
    'assess': {'contributor': CONTRIBUTOR, 'cost_impact': FLAG, 'timeline_impact': FLAG, 'client_facing': FLAG,
               'evidence': ID, 'note': NOTE, 'production_impact': FLAG, 'scope_items': SCOPE,
               'outputs': nullable(obj({key: nullable({**TEXT, 'maxLength': 4000}) for key in change_impacts.OUTPUTS})),
               'effort_person_days': nullable({'type': 'string', 'maxLength': 32}), 'proof_upload': nullable(ID)},
    'decide': {'role': ROLE, 'verdict': VERDICT, 'evidence': ID, 'note': NOTE},
    'authorize': {'commercial': nullable(ID)},
    'execution': {'kind': choice('plan_updated', 'implemented', 'testing_validated', 'documentation_updated'),
                  'evidence': ID, 'note': NOTE, 'scope_items': SCOPE, 'dossier_id': nullable(ID), 'candidate_id': nullable(ID)},
}
OTHER = {
    'document_review': {'version_id': ID, 'verdict': VERDICT, 'note': NOTE},
    'close': {'receipt_id': ID, 'pm_signature_id': ID, 'client_signature_id': nullable(ID), 'note': NOTE,
              'operation_key': nullable(UUID), 'mode': choice('signed', 'owner_applicability'),
              'pm_signature': ACTUAL_SIGNATURE, 'client_signature': nullable(ACTUAL_SIGNATURE)},
    'operate_delivery': {'job_id': ID, 'operation': choice('cancel', 'retry'), 'reason': NOTE},
    'restart': {'reason': {**TEXT, 'maxLength': 2000}},
}


def closure_attestation(actor, work, values):
    _, data = native.source(work, actor)
    auth = native.authorization(work, data)
    receipt = get_object_or_404(PublicationReceipt, pk=values['receipt_id'], publication__factory_work=work)
    signatures = {}
    for role, name in (('PM', 'pm'), ('Client', 'client')):
        proof_id = values[f'{name}_signature_id']
        signer = values[f'{name}_signature']
        if bool(proof_id) != bool(signer):
            raise ValidationError('Provide actual signature facts and their exact evidence together.')
        if signer:
            proof = get_object_or_404(public_evidence(work.case.evidence.filter(kind='signature')), pk=proof_id)
            signatures[role] = {**signer, 'evidence': change_signatures.pin(proof), 'purpose': change_signatures.PURPOSE}
    result = {**change_signatures.subject_pins(auth, receipt), 'protocol': change_signatures.PROTOCOL,
              'purpose': change_signatures.PURPOSE, 'attesting_actor_id': actor.pk, 'signatures': signatures}
    if values['mode'] == 'owner_applicability':
        config, entry = change_applicability.owner_requirement(auth)
        result.update(protocol=change_applicability.PROTOCOL,
                      applicability={'policy_id': config.pk, 'revision': config.revision, 'entry': entry})
    return result


@endpoint(method='POST', request={'oneOf': [
    obj({'action': {'const': action}, **VERSIONS, 'change_version_id': ID, **fields})
    for action, fields in {**HUMAN, **OTHER}.items()]},
    response=obj({**WORK_RESULT['properties'], 'record_id': ID}), status=201,
    summary='Record exact human impacts, decisions, authorization, execution, document review or signed closure')
def command(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    selected, _ = native.source(work, actor)
    if selected.pk != body['change_version_id'] or selected.category == 'Emergency':
        raise ValidationError('Refresh the current exact Standard or Normal Change before proceeding.')
    args = (actor, work.pk, body['expected_revision'], body['case_revision'])
    action = body['action']
    if action in HUMAN:
        row = native.human_action(*args, selected.pk, action, {key: body[key] for key in HUMAN[action]})
    elif action == 'document_review':
        row = native.review(*args, body['version_id'], body['verdict'], body['note'])
    elif action == 'close':
        row = native.close(*args, body['receipt_id'], body['pm_signature_id'], body['client_signature_id'], body['note'],
                           attestation=closure_attestation(actor, work, body), operation_key=body['operation_key'])
    elif action == 'operate_delivery':
        row = native.operate(*args, body['job_id'], body['operation'], body['reason'])
    else:
        row = native.restart(*args, body['reason'])
    wake_waiting(work.pk)
    return recorded(work, row)
