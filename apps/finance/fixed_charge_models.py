"""Source-backed fixed charges; acknowledgement and pricing are distinct history."""
from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class CoverageFixedCharge(AppendOnly):
    request = models.ForeignKey('finance.CoveragePreparationRequest', on_delete=models.PROTECT)
    assessment = models.ForeignKey('finance.CoverageAssessment', on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['request', 'version'], name='coverage_fixed_charge_version')]


class CoverageNativePreparation(AppendOnly):
    receipt = models.ForeignKey('finance.CoveragePreparationReceipt', on_delete=models.PROTECT)
    preparation = models.OneToOneField('finance.BillingPreparation', on_delete=models.PROTECT)
    payload = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class CoveragePreparationContinuation(AppendOnly):
    """Explicit current authority; never replacement acknowledgement or approval."""
    receipt = models.ForeignKey('finance.CoveragePreparationReceipt', on_delete=models.PROTECT, related_name='continuations')
    assessment = models.ForeignKey('finance.CoverageAssessment', on_delete=models.PROTECT)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    previous = models.OneToOneField('self', null=True, on_delete=models.PROTECT, related_name='+')
    version = models.PositiveIntegerField()
    payload = models.JSONField()
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['receipt', 'version'], name='coverage_continuation_version')]
