"""Claim metadata inherits existing document-domain restrictions, never case-only access."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from apps.identity.services import require
from apps.identity.models import Grant
from .models import Template, Version, TemplateClaim, TemplateScope


def visible_templates(actor, case, *, candidate_ids=None, budget=None):
    require(actor, case, 'document.read')
    templates = Template.objects.filter(case=case).exclude(definition__document_type='accepted_finance_metadata')
    if candidate_ids is not None:
        templates = templates.filter(pk__in=candidate_ids)
    if not Grant.objects.filter(case=case, user=actor, action='finance.read', active=True).exists():
        templates = templates.exclude(definition__document_type__in=['finance_report', 'finance_group_report'])
        templates = templates.exclude(pk__in=Version.objects.filter(document__case=case, forecastbinding__isnull=False).values('template_id'))
    if budget is not None:
        return _bounded_bindings(actor, templates, budget)
    from apps.finance.models import FinanceDocumentBinding
    from apps.finance.statement_ppe import recipient_access
    hidden = []
    bindings = FinanceDocumentBinding.objects.filter(version__template__in=templates).select_related('run', 'version')
    for binding in bindings:
        try:
            recipient_access(binding.run, [actor.pk])
        except (PermissionDenied, ValidationError):
            hidden.append(binding.version.template_id)
    from apps.pmo.leadership_reporting import binding_access
    reports = Version.objects.filter(template__in=templates, minutesreportbinding__manifest__source_mode='leadership_selected_facts/v1')
    for version in reports:
        try:
            binding_access(actor, version)
        except PermissionDenied:
            hidden.append(version.template_id)
    return templates.exclude(pk__in=hidden)


def _bounded_bindings(actor, templates, budget):
    from apps.finance.models import FinanceDocumentBinding, FinanceRun
    from apps.finance.statement_ppe import denied_statement_runs
    from apps.pmo.leadership_reporting import MODE, denied_binding_templates
    from apps.pmo.models import MinutesReportBinding

    finance = FinanceDocumentBinding.objects.filter(version__template__in=templates)
    runs = FinanceRun.objects.filter(pk__in=finance.values('run_id'), kind='statement').only('kind', 'case_id')
    denied_runs = denied_statement_runs(actor, budget.take(runs), budget)
    reports = MinutesReportBinding.objects.filter(
        version__template__in=templates, manifest__source_mode=MODE,
    ).select_related('report__case', 'version').only('report__case__id', 'version__created_at', 'version__template_id')
    hidden = denied_binding_templates(actor, budget.take(reports), budget)
    return templates.exclude(
        pk__in=finance.filter(run_id__in=denied_runs).values('version__template_id'),
    ).exclude(pk__in=hidden)


def visible_scopes(actor, case, *, scopes=None, budget=None):
    if scopes is None:
        scopes = TemplateScope.objects.filter(case=case)
        templates = visible_templates(actor, case, budget=budget)
    else:
        # Check every historical claim, including retracted claims, but only
        # evaluate domain bindings for templates that can hide a selected scope.
        scopes = scopes.filter(case=case)
        candidates = TemplateClaim.objects.filter(scope__in=scopes).values('template_id')
        templates = visible_templates(actor, case, candidate_ids=candidates, budget=budget)
    if not Grant.objects.filter(case=case, user=actor, action='finance.read', active=True).exists():
        scopes = scopes.exclude(document_type__in=['finance_report', 'finance_group_report'])
    return scopes.exclude(claims__template__in=Template.objects.filter(case=case).exclude(pk__in=templates)).distinct()


def require_scope(actor, scope):
    if not visible_scopes(actor, scope.case, scopes=TemplateScope.objects.filter(pk=scope.pk)).exists():
        raise PermissionDenied('Template source metadata needs its owning document-domain access')


def visible_sources(actor, case, *, source_id=None, source_ids=None, budget=None):
    from .template_current import SOURCE_KIND
    scopes = TemplateScope.objects.filter(case=case)
    sources = case.evidence.all()
    if source_id is not None:
        source_ids = [source_id]
    if source_ids is not None:
        sources = sources.filter(pk__in=source_ids)
        scopes = scopes.filter(Q(evidence_id__in=source_ids) | Q(claims__evidence_id__in=source_ids) |
            Q(resolutions__evidence_id__in=source_ids) | Q(claims__retraction__evidence_id__in=source_ids))
        visible = visible_scopes(actor, case, scopes=scopes, budget=budget)
    else:
        visible = visible_scopes(actor, case, budget=budget)
    hidden = scopes.exclude(pk__in=visible)
    from apps.core.evidence_access import public_evidence
    sources = sources.filter(Q(kind=SOURCE_KIND) | Q(pk__in=public_evidence(sources.filter(kind='policy_decision')).values('pk')))
    return sources.exclude(Q(templatescope__in=hidden) | Q(templateclaim__scope__in=hidden) |
        Q(templateresolution__scope__in=hidden) | Q(templateclaimretraction__claim__scope__in=hidden)).distinct()
