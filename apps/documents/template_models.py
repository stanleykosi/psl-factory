"""P10 source claims are evidence, not implicit owner decisions."""
from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class TemplateScope(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    document_type = models.CharField(max_length=40)
    audience = models.CharField(max_length=20)
    purpose = models.CharField(max_length=160)
    context = models.CharField(max_length=160)
    source_owner = models.CharField(max_length=160)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'document_type', 'audience', 'purpose', 'context', 'source_owner'], name='template_exact_applicability')]

    def __str__(self):
        return f'{self.purpose} / {self.context} / {self.source_owner} / {self.audience}'


class TemplateClaim(AppendOnly):
    scope = models.ForeignKey(TemplateScope, on_delete=models.PROTECT, related_name='claims')
    template = models.ForeignKey('documents.Template', on_delete=models.PROTECT)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    note = models.CharField(max_length=4000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    owner_policy = models.ForeignKey('policy.Configuration', null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class TemplateClaimRetraction(AppendOnly):
    claim = models.OneToOneField(TemplateClaim, on_delete=models.PROTECT, related_name='retraction')
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    note = models.CharField(max_length=4000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    owner_policy = models.ForeignKey('policy.Configuration', null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class TemplateResolution(AppendOnly):
    scope = models.ForeignKey(TemplateScope, on_delete=models.PROTECT, related_name='resolutions')
    selected_claim = models.ForeignKey(TemplateClaim, on_delete=models.PROTECT)
    claim_ids = models.JSONField()
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    note = models.CharField(max_length=4000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    owner_policy = models.ForeignKey('policy.Configuration', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
