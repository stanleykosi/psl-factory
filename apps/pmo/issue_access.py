"""Generic issue evidence uses the shared public boundary, never private domain grants."""
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.evidence_access import public_evidence, public_agent_runs
from apps.core.models import Evidence
from .services import subject


def issue_subject(case, pk, kind=None):
    evidence = subject(case, pk, kind)
    if not public_evidence(Evidence.objects.filter(pk=evidence.pk)).exists():
        raise ValidationError('Private source evidence requires its native scoped interface')
    return evidence


def state_public(state):
    ids = [state.evidence_id, state.fix_id, state.root_cause_id]
    ids += [link.get('evidence_id') for link in state.external_links]
    ids = set(pk for pk in ids if pk is not None)
    return ids == set(public_evidence(Evidence.objects.filter(case=state.issue.case,pk__in=ids)).values_list('pk',flat=True))


def issue_projection(issue,actor=None):
    if not issue.current or not state_public(issue.current):
        return None
    issue.public_history = [state for state in issue.states.select_related('issue__case') if state_public(state)]
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
