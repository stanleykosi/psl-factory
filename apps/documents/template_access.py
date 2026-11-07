"""Claim metadata inherits existing document-domain restrictions, never case-only access."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from apps.identity.services import require
from apps.identity.models import Grant
from .models import Template, Version, TemplateScope


def visible_templates(actor, case):
    require(actor, case, 'document.read')
    templates = Template.objects.filter(case=case).exclude(definition__document_type='accepted_finance_metadata')
    if not Grant.objects.filter(case=case, user=actor, action='finance.read', active=True).exists():
        templates = templates.exclude(definition__document_type__in=['finance_report', 'finance_group_report'])
        templates = templates.exclude(pk__in=Version.objects.filter(document__case=case, forecastbinding__isnull=False).values('template_id'))
    from apps.finance.models import FinanceDocumentBinding
    from apps.finance.statement_ppe import recipient_access
    hidden = []
    for binding in FinanceDocumentBinding.objects.filter(version__template__in=templates).select_related('run', 'version'):
        try:
            recipient_access(binding.run, [actor.pk])
        except (PermissionDenied, ValidationError):
            hidden.append(binding.version.template_id)
    from apps.pmo.leadership_reporting import binding_access
    for version in Version.objects.filter(template__in=templates, minutesreportbinding__manifest__source_mode='leadership_selected_facts/v1'):
        try:
            binding_access(actor, version)
        except PermissionDenied:
            hidden.append(version.template_id)
    return templates.exclude(pk__in=hidden)


def visible_scopes(actor, case):
    templates = visible_templates(actor, case)
    scopes = TemplateScope.objects.filter(case=case)
    if not Grant.objects.filter(case=case, user=actor, action='finance.read', active=True).exists():
        scopes = scopes.exclude(document_type__in=['finance_report', 'finance_group_report'])
    return scopes.exclude(claims__template__in=Template.objects.filter(case=case).exclude(pk__in=templates)).distinct()


def require_scope(actor, scope):
    if not visible_scopes(actor, scope.case).filter(pk=scope.pk).exists():
        raise PermissionDenied('Template source metadata needs its owning document-domain access')


def visible_sources(actor, case):
    from .template_current import SOURCE_KIND
    hidden = TemplateScope.objects.filter(case=case).exclude(pk__in=visible_scopes(actor, case))
    from apps.core.evidence_access import public_evidence
    sources = case.evidence.filter(Q(kind=SOURCE_KIND) | Q(pk__in=public_evidence(case.evidence.filter(kind='policy_decision')).values('pk')))
    return sources.exclude(Q(templatescope__in=hidden) | Q(templateclaim__scope__in=hidden) |
        Q(templateresolution__scope__in=hidden) | Q(templateclaimretraction__claim__scope__in=hidden)).distinct()
