"""Finance-owned supplied collective usage. No provider authenticity or new counterparty."""
from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class UsageIntakeSource(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    provider_namespace = models.CharField(max_length=100)
    provider_ref = models.CharField(max_length=100)
    report_ref = models.CharField(max_length=100)
    period = models.CharField(max_length=7)
    source_version = models.CharField(max_length=100)
    version = models.PositiveIntegerField()
    predecessor = models.OneToOneField('self', null=True, on_delete=models.PROTECT)
    payload = models.JSONField()
    controls = models.JSONField()
    sha256 = models.CharField(max_length=64)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT, related_name='+')
    control_evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT, related_name='+')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'provider_namespace', 'provider_ref', 'report_ref', 'period', 'source_version'], name='usage_intake_source_identity')]

    def __str__(self):
        return f'{self.report_ref} / {self.period} / v{self.version} (#{self.pk})'


class UsageIntakeReceipt(AppendOnly):
    source = models.ForeignKey(UsageIntakeSource, on_delete=models.PROTECT, related_name='receipts')
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    operation_key = models.CharField(max_length=100)
    delivery_key = models.CharField(max_length=64)
    delivery_ref = models.CharField(max_length=100)
    intent_sha256 = models.CharField(max_length=64)
    duplicate_of = models.ForeignKey('self', null=True, on_delete=models.PROTECT)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT, related_name='+')
    control_evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT, related_name='+')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'operation_key'], name='usage_intake_operation'), models.UniqueConstraint(fields=['case', 'delivery_key'], name='usage_intake_delivery')]


class UsageIntakeAcceptance(AppendOnly):
    source = models.OneToOneField(UsageIntakeSource, on_delete=models.PROTECT, related_name='acceptance')
    receipt = models.OneToOneField(UsageIntakeReceipt, on_delete=models.PROTECT)
    result = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class UsageIntakeWithdrawal(AppendOnly):
    source = models.OneToOneField(UsageIntakeSource, on_delete=models.PROTECT)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    reason = models.CharField(max_length=1000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
