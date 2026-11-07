"""Explicit cross-case identity overlay. Existing invoice keys are never rewritten."""
from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class ObligationNamespace(AppendOnly):
    tenant = models.CharField(max_length=100)
    synthetic = models.BooleanField()
    name = models.CharField(max_length=100)
    key_contract = models.JSONField()
    source = models.ForeignKey('policy.ScopeVersion', on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['tenant', 'synthetic', 'name'], name='obligation_namespace_scope')]


class ObligationClaim(AppendOnly):
    namespace = models.ForeignKey(ObligationNamespace, on_delete=models.PROTECT)
    key = models.CharField(max_length=100)
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['namespace', 'key'], name='obligation_canonical_claim')]


class ObligationLocalKey(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    legacy_key = models.CharField(max_length=64)
    claim = models.ForeignKey(ObligationClaim, on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'legacy_key'], name='obligation_local_identity')]


class ObligationAlias(AppendOnly):
    version = models.PositiveIntegerField()
    namespace = models.ForeignKey(ObligationNamespace, on_delete=models.PROTECT)
    key = models.CharField(max_length=100)
    claim = models.ForeignKey(ObligationClaim, on_delete=models.PROTECT)
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    policy = models.ForeignKey('policy.Configuration', on_delete=models.PROTECT)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    authority = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['namespace', 'key', 'version'], name='obligation_alias_identity')]


class ObligationBinding(AppendOnly):
    invoice = models.ForeignKey('finance.Invoice', on_delete=models.PROTECT)
    local_key = models.ForeignKey(ObligationLocalKey, on_delete=models.PROTECT)
    policy = models.ForeignKey('policy.Configuration', on_delete=models.PROTECT)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    alias = models.ForeignKey(ObligationAlias, null=True, on_delete=models.PROTECT)
    predecessor = models.ForeignKey('self', null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ObligationEffect(AppendOnly):
    """Permanent claim-to-invoice ownership, not permission to dispatch."""
    claim = models.OneToOneField(ObligationClaim, on_delete=models.PROTECT)
    invoice = models.OneToOneField('finance.Invoice', on_delete=models.PROTECT)
    binding = models.ForeignKey(ObligationBinding, on_delete=models.PROTECT)
    job = models.OneToOneField('finance.InvoiceJob', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ObligationLegacyAttempt(AppendOnly):
    """Migration-frozen original attempts, never authority for another send."""
    job = models.OneToOneField('finance.InvoiceJob', on_delete=models.PROTECT)
    snapshot = models.JSONField()


class ObligationLegacyObservation(AppendOnly):
    attempt = models.OneToOneField(ObligationLegacyAttempt, on_delete=models.PROTECT)
    proof = models.JSONField()
    fence = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
