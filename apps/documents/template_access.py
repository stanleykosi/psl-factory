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
    from apps.finance.models import FinanceDocumentBinding
    from apps.finance.statement_ppe import recipient_access
    hidden = []
    bindings = FinanceDocumentBinding.objects.filter(version__template__in=templates).select_related('run', 'version')
    if budget is not None:
        bindings = budget.take(bindings.only('id', 'run__kind', 'run__case_id', 'version__template_id'))
    for binding in bindings:
        try:
            recipient_access(binding.run, [actor.pk], budget=budget)
        except (PermissionDenied, ValidationError):
            hidden.append(binding.version.template_id)
    from apps.pmo.leadership_reporting import binding_access
    reports = Version.objects.filter(template__in=templates, minutesreportbinding__manifest__source_mode='leadership_selected_facts/v1')
    if budget is not None:
        reports = budget.take(reports.only('id', 'created_at', 'template_id'))
    for version in reports:
        try:
            binding_access(actor, version, budget=budget)
        except PermissionDenied:
            hidden.append(version.template_id)
    return templates.exclude(pk__in=hidden)


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
    if not visible_scopes(actor, scope.case).filter(pk=scope.pk).exists():
        raise PermissionDenied('Template source metadata needs its owning document-domain access')


def visible_sources(actor, case, *, source_id=None, budget=None):
    from .template_current import SOURCE_KIND
    scopes = TemplateScope.objects.filter(case=case)
    sources = case.evidence.all()
    if source_id is not None:
        sources = sources.filter(pk=source_id)
        scopes = scopes.filter(Q(evidence_id=source_id) | Q(claims__evidence_id=source_id) |
            Q(resolutions__evidence_id=source_id) | Q(claims__retraction__evidence_id=source_id))
        visible = visible_scopes(actor, case, scopes=scopes, budget=budget)
    else:
        visible = visible_scopes(actor, case, budget=budget)
    hidden = scopes.exclude(pk__in=visible)
    from apps.core.evidence_access import public_evidence
    sources = sources.filter(Q(kind=SOURCE_KIND) | Q(pk__in=public_evidence(sources.filter(kind='policy_decision')).values('pk')))
    return sources.exclude(Q(templatescope__in=hidden) | Q(templateclaim__scope__in=hidden) |
        Q(templateresolution__scope__in=hidden) | Q(templateclaimretraction__claim__scope__in=hidden)).distinct()
