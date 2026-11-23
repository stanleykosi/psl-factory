"""Current project issue evidence for an optional reviewed stability criterion."""

from collections import defaultdict

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import F
from django.urls import reverse

from apps.core.evidence_access import public_evidence
from apps.core.models import Audit, Evidence
from apps.core.read_observation import observed_fact
from apps.documents.contracts import digest
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.delivery_validators import ISSUE_SEVERITIES, ISSUE_STATUSES
from apps.policy.services import active_component, reference_values
from .issue_access import public_states
from .issue_models import Issue


MAX_ISSUES = 100


def issue_proof_ids(state):
    links = state['external_links']
    if not isinstance(links, list) or len(links) > 20:
        return None
    ids = {state['evidence_id'], state['fix_id'], state['root_cause_id']}
    ids.discard(None)
    ids.update(link.get('evidence_id') for link in links)
    if any(type(pk) is not int or pk < 1 for pk in ids):
        return None
    return sorted(ids)


def issue_source_grants(case, actor_ids):
    grants = defaultdict(set)
    rows = Grant.objects.filter(case=case, user_id__in=actor_ids, user__is_active=True, active=True,
        action__in=('case.read', 'issue.read', 'evidence.add')).values_list('user_id', 'action')
    for actor_id, action in rows:
        grants[actor_id].add(action)
    return grants


def unknown_issue_clearance():
    return {'status': 'unknown', 'source_sha256': None}, []


@observed_fact
def issue_clearance(dossier, criterion):
    case = dossier.case
    if not {'case.read', 'issue.read'} <= issue_source_grants(case, [criterion['reader_id']])[criterion['reader_id']]:
        return unknown_issue_clearance()
    subjects = list(Issue.objects.filter(case=case).order_by('pk').values_list('pk', 'current_id')[:MAX_ISSUES + 1])
    if len(subjects) > MAX_ISSUES:
        return unknown_issue_clearance()

    state_ids = [state_id for _, state_id in subjects if state_id is not None]
    states = public_states(case).filter(pk__in=state_ids, issue__current_id=F('pk')).order_by('pk').values(
        'pk', 'issue_id', 'issue__reference', 'status', 'severity', 'actor_id',
        'evidence_id', 'fix_id', 'root_cause_id', 'external_links')
    by_issue = {state['issue_id']: (state, issue_proof_ids(state)) for state in states}
    proof_ids = {pk for _, ids in by_issue.values() for pk in ids or ()}
    proofs = {row['pk']: row for row in public_evidence(Evidence.objects.filter(case=case, pk__in=proof_ids)).values(
        'pk', 'kind', 'created_by_id', 'version', 'sha256')}
    actors = {state['actor_id'] for state, _ in by_issue.values()} | {proof['created_by_id'] for proof in proofs.values()}
    grants = issue_source_grants(case, actors)

    issue_events = Audit.objects.filter(case=case, action='issue.updated', data__state__in=state_ids).order_by('pk')
    issue_events = list(issue_events.values_list('actor_id', 'data')[:len(state_ids) + 1])
    proof_events = Audit.objects.filter(case=case, action='evidence.added', data__evidence__in=proof_ids).order_by('pk')
    proof_events = list(proof_events.values_list('actor_id', 'data')[:len(proof_ids) + 1])
    if len(issue_events) > len(state_ids) or len(proof_events) > len(proof_ids):
        return unknown_issue_clearance()
    recorded_issues = {(actor, digest(data)) for actor, data in issue_events}
    recorded_proofs = {(actor, digest(data)) for actor, data in proof_events}
    proven = {pk: proof for pk, proof in proofs.items()
              if {'case.read', 'evidence.add'} <= grants[proof['created_by_id']]
              and (proof['created_by_id'], digest({'evidence': pk, 'kind': proof['kind'], 'version': proof['version'],
                                                   'sha256': proof['sha256']})) in recorded_proofs}

    unknown = False
    pins, blockers = [], []
    for issue_id, state_id in subjects:
        state, ids = by_issue.get(issue_id, (None, None))
        status = state['status'] if state else None
        if (not state or state['pk'] != state_id or not ids or any(pk not in proven for pk in ids)
                or not {'case.read', 'issue.read'} <= grants[state['actor_id']]
                or (state['actor_id'], digest({'issue': issue_id, 'state': state_id, 'status': status})) not in recorded_issues
                or status not in ISSUE_STATUSES):
            unknown = True
            continue
        relevant = status in criterion['blocking_statuses']
        if relevant and state['severity'] not in ISSUE_SEVERITIES:
            unknown = True
            continue
        pins.append([issue_id, state_id, state['actor_id'], status, state['severity'],
                     [[pk, proven[pk]['version'], proven[pk]['sha256'], proven[pk]['created_by_id']] for pk in ids]])
        if relevant and state['severity'] in criterion['blocking_severities']:
            blockers.append({'id': issue_id, 'reference': state['issue__reference'], 'severity': state['severity']})
    status = 'unknown' if unknown else 'not_met' if blockers else 'met'
    return {'status': status, 'source_sha256': digest(pins)}, blockers


def project_issue_clearance(actor, dossier):
    """Reveal exact blocker references only in the native issue reader's scope."""
    try:
        require(actor, dossier.case, 'delivery.read')
        config = active_component('D11.hypercare_criteria_ref', dossier.case)
        criterion = reference_values(config)[0].get('issue_clearance')
    except (ValidationError, PermissionDenied):
        return None
    if not criterion:
        return None
    try:
        for action in ('case.read', 'issue.read'):
            require(actor, dossier.case, action)
    except PermissionDenied:
        return {'status': 'unknown', 'blockers': []}
    summary, blockers = issue_clearance(dossier, criterion)
    path = reverse('issues', args=[dossier.case_id])
    return {'status': summary['status'], 'blockers': [
        {'reference': row['reference'], 'severity': row['severity'], 'url': f"{path}#issue-{row['id']}"} for row in blockers]}
