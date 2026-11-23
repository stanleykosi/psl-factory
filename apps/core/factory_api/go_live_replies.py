"""Evidence and decisions following a delivered Go-live report."""
from time import monotonic

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.core.read_observation import read_observation
from apps.pmo.go_live_reply_forms import panels
from apps.pmo.issue_access import public_current_issues
from apps.policy.go_live_reply_validators import CHANNELS, VALUE as RULE_VALUE
from apps.workflows import factory_go_live as domain, factory_go_live_milestone as milestones

from .commands import require_line
from .delivery import NOTE, PROOF, RESPONSE, proof_rows, recorded
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj
from .reviews import VERSIONS
from .work import WORK_RESULT, result


OUTCOME = choice('changes_requested', 'declined', 'withdrawn')
ROLE = {**TEXT, 'maxLength': 100}
REPLY = obj({'id': ID, 'receipt_id': ID, 'version_id': ID, 'number': REVISION, 'outcome': OUTCOME,
    'party': nullable(TEXT), 'channel': nullable(choice(*CHANNELS)), 'responded_at': nullable(DATETIME),
    'note': nullable(TEXT), 'evidence_id': nullable(ID)})
CHOICE = obj({'receipt_id': ID, 'previous_id': nullable(ID), 'roles': array(ROLE)})
DECLINE_OPTION = obj({'id': ID, 'label': TEXT})
RULE_INPUT = obj({key: value for key, value in RULE_VALUE['properties'].items() if key not in {'kind', 'key'}})


@endpoint(response=obj({**VERSIONS,
    'issues': array(obj({'reply_id': ID, 'existing_issues': array(DECLINE_OPTION, limit=50),
                         'owners': array(DECLINE_OPTION, limit=50)})),
    'new_candidates': array(obj({'reply_id': ID, 'requirements_id': ID})),
    'review_options': array(obj({'reply_id': ID, 'previous_id': nullable(ID), 'roles': array(ROLE),
                                 'destinations': array(DECLINE_OPTION, limit=50)})),
    'rules': nullable(obj({'base_configuration_id': nullable(ID), 'current': nullable(RULE_INPUT),
                           'proofs': array(PROOF, limit=50)})),
}), summary='Read approved options for declined replies and the source-backed response rule draft')
@read_observation
def decline_options(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, domain.DEFINITION)
    with limit_queries(650, deadline=monotonic() + 8):
        state = domain.reply_state(actor, work)
        actions = panels(actor, work, state)
        issue_options = []
        if actions['problems']:
            fields = actions['problems'][0]['form'].fields
            users = fields['owner_id'].queryset.only('first_name', 'last_name', 'username')[:50]
            owners = [{'id': user.pk, 'label': user.get_full_name() or user.username} for user in users]
            issues = fields['existing_issue_id'].queryset.filter(pk__in=public_current_issues(work.case).values('pk'))
            active = [{'id': pk, 'label': reference} for pk, reference in issues.values_list('pk', 'reference')[:50]]
            issue_options = [{'reply_id': row['reply'].pk, 'existing_issues': active, 'owners': owners}
                             for row in actions['problems']]
        reviews = []
        for row in actions['remediation']:
            reply, form = row['reply'], row['form']
            choices = form.fields['destination_id'].queryset.filter(declined_reply__receipt_id=reply.receipt_id)
            candidates = choices.exclude(records__kind__in=['closure', 'release_outcome']).order_by('-pk')
            reviews.append({'reply_id': reply.pk, 'previous_id': form.initial['previous_id'],
                            'roles': [key for key, _ in form.fields['role'].choices if key],
                            'destinations': [{'id': pk, 'label': reference} for pk, reference in
                                             candidates.values_list('pk', 'candidate__reference')[:50]]})
        rules = None
        if actions['rules'] is not None:
            current = state['client_responses']['rules']
            proofs = public_evidence(work.case.evidence.filter(kind='policy_decision')).only('kind', 'version').order_by('-pk')[:50]
            rules = {'base_configuration_id': actions['rules'].initial['base_configuration'] or None,
                     'current': {key: current[key] for key in RULE_INPUT['properties']} if current else None,
                     'proofs': proof_rows(proofs)}
    return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'issues': issue_options,
            'new_candidates': [{'reply_id': row['reply'].pk, 'requirements_id': row['form'].initial['requirements_id']}
                               for row in actions['candidates']], 'review_options': reviews, 'rules': rules}


@endpoint(method='POST', request=obj({**VERSIONS, 'base_configuration_id': nullable(ID),
                                     'rules': RULE_INPUT, 'evidence_id': ID}), response=RESPONSE, status=201,
          summary='Draft the Go-live client response rules for separate policy validation and activation')
def draft_rules(request, work_id, *, body):
    work = require_line(request.user, work_id, domain.DEFINITION)
    fields = {**body['rules'], 'base_configuration': body['base_configuration_id'] or 0, 'evidence_id': body['evidence_id']}
    fields['allow_recorder_correction'] = 'yes' if fields['allow_recorder_correction'] else 'no'
    row = domain.client_response_action(request.user, work.pk, body['expected_revision'], body['case_revision'],
                                        'client_reply_rules', fields)
    return recorded(work, row)


@endpoint(response=obj({**VERSIONS, 'channels': array(choice(*CHANNELS)), 'finding': {'type': 'string'},
    'capture': array(CHOICE), 'corrections': array(CHOICE), 'replies': array(REPLY),
    'linked_issues': array(obj({'reply_id': ID, 'issue_id': ID})),
    'reviewed_handoffs': array(obj({'reply_id': ID, 'review_id': ID, 'dossier_id': ID})),
    'milestone': obj({'recorded_id': nullable(ID), 'configuration_id': nullable(ID), 'name': nullable(TEXT),
        'acceptance_id': nullable(ID), 'proof_ids': array(ID, limit=100), 'owner_decision_ids': array(ID, limit=100),
        'can_confirm': BOOLEAN, 'confirmation': nullable(obj({'id': ID, 'actor_id': ID, 'at': DATETIME,
            'role': choice('PMO Lead'), 'name': TEXT, 'note': nullable(NOTE)}))}),
}), summary='Read exact Go-live replies, current role controls and the evidenced milestone handoff')
@read_observation
def detail(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, domain.DEFINITION)
    with limit_queries(600, deadline=monotonic() + 8):
        state = domain.reply_state(actor, work, include_milestone=True)
        response = state['client_responses']
        available = panels(actor, work, state)
        replies = []
        for row in response['items']:
            replies.append({**{key: row[key] for key in ('id', 'receipt_id', 'version_id', 'number', 'outcome')},
                **{key: row[key] if row['source_available'] else None for key in
                   ('party', 'channel', 'responded_at', 'note', 'evidence_id')}})
        opening = {}
        for kind in ('capture', 'corrections'):
            opening[kind] = [{'receipt_id': row['form'].initial['receipt_id'],
                              'previous_id': row['form'].initial['previous_id'],
                              'roles': [key for key, _ in row['form'].fields['role'].choices if key]}
                             for row in available[kind]]
        activity = milestones.panel(actor, work, state)
        completion = activity.get('completion', {})
        direct = activity.get('direct_confirmation', {})
        confirmation = activity.get('confirmation')
    return {'expected_revision': work.revision, 'case_revision': work.case.revision,
            'channels': response['rules']['channels'] if response['rules'] else CHANNELS, 'finding': response['finding'],
            **opening, 'replies': replies, 'linked_issues': [{'reply_id': row.reply_id, 'issue_id': row.issue_id}
                                                            for row in response['issues']],
            'reviewed_handoffs': response['destinations'],
            'milestone': {'recorded_id': activity['recorded'].pk if 'recorded' in activity else None,
                'configuration_id': completion.get('configuration'),
                'name': activity['recorded'].name if 'recorded' in activity else completion.get('name'),
                'acceptance_id': confirmation.data['acceptance'] if confirmation else
                    completion.get('acceptance') or direct.get('acceptance'),
                'proof_ids': [row['pk'] for row in (completion or direct).get('sources', [])],
                'can_confirm': bool(direct),
                'confirmation': {'id': confirmation.pk, 'actor_id': confirmation.actor_id, 'at': confirmation.created_at,
                                 'role': 'PMO Lead',
                                 'name': confirmation.data['milestone_name'], 'note': confirmation.data['note']}
                if confirmation else None,
                'owner_decision_ids': [row['pk'] for row in activity.get('settings', [])]}}


COMMANDS = {
    'record_reply': ('client_reply', {'receipt_id': ID, 'previous_id': nullable(ID), 'outcome': OUTCOME,
        'party': {**TEXT, 'maxLength': 160}, 'responded_at': DATETIME, 'channel': choice(*CHANNELS), 'evidence_id': ID,
        'note': NOTE, 'role': ROLE, 'attested': BOOLEAN}),
    'link_decline_issue': ('client_decline_issue', {'reply_id': ID, 'existing_issue_id': nullable(ID), 'title': nullable({**TEXT, 'maxLength': 240}),
        'owner_id': nullable(ID), 'next_action': nullable({**TEXT, 'maxLength': 1000}), 'note': NOTE}),
    'prepare_new_candidate': ('client_decline_candidate', {'reply_id': ID, 'reference': {**TEXT, 'maxLength': 160},
                                                        'requirements_id': ID, 'note': NOTE}),
    'review_remediation': ('client_decline_handoff', {'reply_id': ID, 'previous_id': nullable(ID), 'destination_id': ID,
                                                       'role': ROLE, 'evidence_id': ID, 'note': NOTE}),
}


@endpoint(method='POST', request={'oneOf': [obj({'action': {'const': key}, **VERSIONS, **fields})
          for key, (_, fields) in COMMANDS.items()]}, response=RESPONSE, status=201,
          summary='Record the client response or review its exact declined-release remediation')
def command(request, work_id, *, body):
    work = require_line(request.user, work_id, domain.DEFINITION)
    action, fields = COMMANDS[body['action']]
    values = {key: str(body[key]) if type(body[key]) is int else body[key] for key in fields}
    row = domain.client_response_action(request.user, work.pk, body['expected_revision'], body['case_revision'], action, values)
    return recorded(work, row)


@endpoint(method='POST', request=obj({**VERSIONS, 'inputs': domain.INPUT, 'reason': {**TEXT, 'maxLength': 2000}}),
          response=WORK_RESULT, summary='Prepare a new Go-live report following a supported client request for changes')
def prepare_successor(request, work_id, *, body):
    work = require_line(request.user, work_id, domain.DEFINITION)
    return result(domain.prepare_client_revision(request.user, work.pk, body['expected_revision'], body['case_revision'],
                                                 body['inputs'], body['reason']))


@endpoint(method='POST', request={'oneOf': [
    obj({'action': {'const': 'draft_mapping'}, **VERSIONS, 'name': {**TEXT, 'maxLength': 200}, 'owner_decision_id': ID}),
    obj({'action': {'const': 'record_completion'}, **VERSIONS, 'configuration_id': ID, 'acceptance_id': ID, 'evidence_id': ID}),
    obj({'action': {'const': 'confirm_and_complete'}, **VERSIONS, 'name': {**TEXT, 'maxLength': 200},
         'note': NOTE, 'acceptance_id': ID, 'evidence_id': ID}, optional=('note',)),
]}, response=RESPONSE, status=201, summary='Draft a sourced milestone mapping or record its independently evidenced PMO completion')
def milestone(request, work_id, *, body):
    work = require_line(request.user, work_id, domain.DEFINITION)
    args = (request.user, work.pk, body['expected_revision'], body['case_revision'])
    if body['action'] == 'draft_mapping':
        row = milestones.draft_mapping(*args, body['name'], body['owner_decision_id'])
    elif body['action'] == 'confirm_and_complete':
        row = milestones.confirm_and_complete(*args, body['name'], body['acceptance_id'], body['evidence_id'], body.get('note', ''))
    else:
        row = milestones.record(*args, body['configuration_id'], body['acceptance_id'], body['evidence_id'])
    return recorded(work, row)
