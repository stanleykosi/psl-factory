"""Generic issue evidence uses the shared public boundary, never private domain grants."""
from django.core.exceptions import ValidationError,PermissionDenied
from django.db.models import BooleanField, Exists, F, Func, JSONField, OuterRef, Q, Subquery
from apps.core.evidence_access import public_evidence, public_agent_runs
from apps.core.models import Evidence
from .issue_models import Issue, IssueState
from .services import subject


def issue_subject(case, pk, kind=None, *, metadata_only=True):
    evidence = subject(case, pk, kind, metadata_only=metadata_only)
    if not public_evidence(Evidence.objects.filter(pk=evidence.pk)).exists():
        raise ValidationError('Private source evidence requires its native scoped interface')
    return evidence


def state_public(state):
    ids = [state.evidence_id, state.fix_id, state.root_cause_id]
    ids += [link.get('evidence_id') for link in state.external_links]
    ids = set(pk for pk in ids if pk is not None)
    return ids == set(public_evidence(Evidence.objects.filter(case=state.issue.case,pk__in=ids)).values_list('pk',flat=True))


class PublicLinkedProofs(Func):
    output_field = BooleanField()
    arity = 2

    def as_postgresql(self, compiler, connection):
        links, link_params = compiler.compile(self.source_expressions[0])
        proofs, proof_params = compiler.compile(self.source_expressions[1])
        # Compare exact JSON numbers without casting legacy or untrusted link identifiers.
        return f"""CASE WHEN jsonb_typeof({links}) = 'array' THEN NOT EXISTS (
            SELECT 1 FROM jsonb_array_elements({links}) AS linked(item)
            WHERE jsonb_typeof(linked.item) IS DISTINCT FROM 'object'
               OR (linked.item ? 'evidence_id' AND linked.item->'evidence_id' <> 'null'::jsonb
                   AND linked.item->'evidence_id' NOT IN {proofs})
        ) ELSE false END""", (*link_params, *link_params, *proof_params)


def public_states(case):
    """The native public evidence boundary, applied before counts or pagination."""
    proofs = public_evidence(Evidence.objects.filter(case=case)).order_by()
    proof_ids = proofs.values('pk')
    json_ids = proofs.annotate(json_id=Func('pk', function='to_jsonb', output_field=JSONField())).values('json_id')
    return IssueState.objects.filter(issue__case=case, evidence_id__in=proof_ids).filter(
        Q(fix_id__isnull=True) | Q(fix_id__in=proof_ids),
        Q(root_cause_id__isnull=True) | Q(root_cause_id__in=proof_ids),
        PublicLinkedProofs(F('external_links'), Subquery(json_ids)),
    )


def public_current_issues(case):
    current = public_states(case).filter(pk=OuterRef('current_id'), issue_id=OuterRef('pk'))
    return Issue.objects.filter(case=case).filter(Exists(current))


def issue_projection(issue,actor=None):
    if not issue.current or not state_public(issue.current):
        return None
    issue.public_history = [state for state in issue.states.select_related('issue__case').defer('note') if state_public(state)]
    for state in issue.public_history:
        state.public_closure_entries = list(state.closure_entries.filter(evidence_id__in=public_evidence(Evidence.objects.filter(case=issue.case)).values('pk')))
    if actor is not None:
        from .issue_references import report
        try:issue.public_references=report(actor,issue)
        except (ValidationError,PermissionDenied):issue.public_references={'held':'Current source read permission or source evidence requires review'}
    return issue


def readable_runs(queryset,actor=None):
    """Legacy runs may cite several sources even when their primary source is public."""
    for run in public_agent_runs(queryset):
        if actor is not None:
            from .models import Issue
            from .issue_references import report
            try:
                for finding in run.result.get('findings',[]):
                    report(actor,Issue.objects.select_related('case','current').get(case=run.case,pk=finding['issue_id']))
            except (ValidationError,PermissionDenied,Issue.DoesNotExist):continue
        ids = set()
        for finding in run.result.get('findings', []):
            ids.add(finding.get('evidence_id'))
            ids.update(link.get('evidence_id') for link in finding.get('external_owner_refs', []))
        ids.discard(None)
        if ids == set(public_evidence(Evidence.objects.filter(case=run.case,pk__in=ids)).values_list('pk',flat=True)):
            yield run
