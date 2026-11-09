"""Bounded evidence and authority reads for an already selected report batch."""
from collections import defaultdict

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import F, Q, Window
from django.db.models.functions import RowNumber

from apps.core.evidence_access import public_evidence
from apps.core.models import Evidence
from apps.core.read_budget import ReadLimit
from apps.identity.models import Grant
from . import issue_references as refs
from .models import Issue, IssueReferenceObservation, IssueReferenceRevision, IssueState


MAX_KEYS = 400
MAX_LEGACY_HISTORY = 2000
PER_ISSUE_HISTORY = 100
LINK_BYTES = 64 * 1024


def _positive_pk(value):
    return type(value) is int and 0 < value < 2**63


def _pairs(pairs, first, second):
    grouped = defaultdict(set)
    for left, right in pairs:
        grouped[left].add(right)
    condition = Q(pk__in=[])
    for left, rights in grouped.items():
        condition |= Q(**{first: left, f'{second}__in': rights})
    return condition


class IncidentAccess:
    """Native incident validators over exact, batch-local dependency rows."""

    @staticmethod
    def supports(pin):
        return (
            isinstance(pin, dict) and isinstance(pin.get('reference'), dict)
            and _positive_pk(pin.get('issue_id')) and _positive_pk(pin['reference'].get('evidence_id'))
            and all(key in pin and (pin[key] is None or _positive_pk(pin[key]))
                    for key in ('revision_id', 'observation_id'))
        )

    def __init__(self, actor, selected, budget):
        revision_keys, observation_keys, evidence = set(), set(), set()
        for case_id, pin in selected:
            if not self.supports(pin):
                continue
            evidence.add((case_id, pin['reference']['evidence_id']))
            if pin['revision_id'] is not None:
                revision_keys.add((case_id, pin['issue_id'], pin['revision_id']))
            if pin['observation_id'] is not None:
                observation_keys.add((case_id, pin['observation_id']))
            if max(len(revision_keys), len(observation_keys), len(evidence)) > MAX_KEYS:
                raise ReadLimit

        revision_rows = IssueReferenceRevision.objects.filter(_pairs(
            {(case_id, pk) for case_id, _, pk in revision_keys}, 'issue__case_id', 'pk',
        )).select_related('issue', 'actor').only('issue__case_id', 'actor__is_active', 'evidence_id')
        self.revisions = {
            key: row for row in revision_rows
            if (key := (row.issue.case_id, row.issue_id, row.pk)) in revision_keys
        }
        budget.load_many(list(self.revisions.values()), 'references', ceiling=LINK_BYTES)

        observation_rows = IssueReferenceObservation.objects.filter(_pairs(
            observation_keys, 'issue__case_id', 'pk',
        )).select_related('issue', 'actor', 'contract__case', 'contract__actor', 'evidence__created_by').only(
            'issue__case_id', 'actor__is_active', 'contract__case__id', 'contract__kind',
            'contract__actor__is_active', 'contract__evidence_id', 'evidence__created_by__is_active',
            'evidence__kind', 'evidence__sha256', 'source_ref', 'source_sha256',
        )
        self.observations = {(row.issue.case_id, row.pk): row for row in observation_rows}

        principals = set()
        actions = {'case.read', 'issue.read', 'issue.manage', 'issue.reference.configure',
                   'issue.reference.observe', 'evidence.add'}
        for case_id, _ in evidence:
            principals.add((case_id, actor.pk))
        for (case_id, _, _), row in self.revisions.items():
            principals.add((case_id, row.actor_id))
            evidence.add((case_id, row.evidence_id))
        for (case_id, _), row in self.observations.items():
            contract = row.contract
            principals.update(((contract.case_id, actor.pk), (contract.case_id, contract.actor_id),
                               (case_id, row.actor_id), (case_id, row.evidence.created_by_id)))
            evidence.add((contract.case_id, contract.evidence_id))
            actions.add('issue.reference.' + contract.kind + '.read')
        self.grants = set(Grant.objects.filter(
            _pairs(principals, 'case_id', 'user_id'), user__is_active=True, active=True, action__in=actions,
        ).values_list('case_id', 'user_id', 'action'))
        self.public = set(public_evidence(Evidence.objects.filter(
            _pairs(evidence, 'case_id', 'pk'),
        )).values_list('case_id', 'pk'))

    def require(self, actor, case, action):
        if not actor.is_authenticated or not actor.is_active or (case.pk, actor.pk, action) not in self.grants:
            raise PermissionDenied('This record/action has no active grant')

    def subject(self, case, pk, *, metadata_only=False):
        if (case.pk, pk) not in self.public:
            raise ValidationError('Exact retained incident source is unavailable or private')

    def revision(self, case, pin):
        return self.revisions.get((case.pk, pin['issue_id'], pin['revision_id']))

    def observation(self, actor, case, pk):
        return refs.check_observation(actor, case, self.observations.get((case.pk, pk)),
                                      metadata_only=True, require_action=self.require, check_subject=self.subject)


class LegacyHistory:
    """Exact per-issue history through each requested version cutoff."""

    def __init__(self, selected, budget):
        cutoffs = {}
        state_keys = set()
        for case_id, manifest, cutoff in selected:
            for issue_id, state_id, _ in manifest['issues']:
                if type(issue_id) is not int or type(state_id) is not int:
                    continue
                key = (case_id, issue_id)
                cutoffs[key] = max(cutoff, cutoffs.get(key, cutoff))
                state_keys.add((case_id, issue_id, state_id, cutoff))
                if len(state_keys) > MAX_KEYS:
                    raise ReadLimit

        revisions = Q(pk__in=[])
        for (case_id, issue_id), cutoff in cutoffs.items():
            revisions |= Q(issue__case_id=case_id, issue_id=issue_id, created_at__lte=cutoff)
        rows = IssueReferenceRevision.objects.filter(revisions).annotate(
            position=Window(RowNumber(), partition_by=[F('issue_id')], order_by=F('number').desc()),
        ).filter(position__lte=PER_ISSUE_HISTORY + 1).only(
            'issue_id', 'number', 'created_at',
        ).order_by('issue_id', '-number')
        self.histories = defaultdict(list)
        rows = budget.take(rows, limit=MAX_LEGACY_HISTORY)
        for row in rows:
            history = self.histories[row.issue_id]
            history.append(row)
            if len(history) > PER_ISSUE_HISTORY:
                raise ReadLimit
        budget.load_many(rows, 'references', ceiling=LINK_BYTES)
        self.issues = set(Issue.objects.filter(_pairs(cutoffs, 'case_id', 'pk')).values_list('case_id', 'pk'))
        self.states = {
            (row.issue.case_id, row.issue_id, row.pk): row for row in
            IssueState.objects.filter(_pairs({(c, state) for c, _, state, _ in state_keys}, 'issue__case_id', 'pk'))
            .select_related('issue').only('issue__case_id')
        }
        fallbacks = {
            (case_id, issue_id, state_id) for case_id, issue_id, state_id, cutoff in state_keys
            if not any(row.created_at <= cutoff for row in self.histories[issue_id])
        }
        budget.load_many([row for key, row in self.states.items() if key in fallbacks],
                         'external_links', ceiling=LINK_BYTES)

    def legacy_history(self, case, issue_id, state_id, cutoff):
        if (case.pk, issue_id) not in self.issues:
            raise Issue.DoesNotExist('Exact retained issue is missing')
        state = self.states.get((case.pk, issue_id, state_id))
        if state is None:
            raise IssueState.DoesNotExist('Exact retained issue state is missing')
        return [row for row in self.histories[issue_id] if row.created_at <= cutoff], state
