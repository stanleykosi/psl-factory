from django.conf import settings
from django.db import models

from apps.core.models import AppendOnly
from apps.policy.short_payment_validators import TREATMENTS


class InvoiceShortPaymentDecision(AppendOnly):
    issue = models.ForeignKey('finance.InvoiceIssue', on_delete=models.PROTECT, related_name='short_payment_decisions')
    allocation = models.ForeignKey('finance.CashAllocation', on_delete=models.PROTECT)
    position = models.JSONField()
    position_sha256 = models.CharField(max_length=64)
    treatment = models.CharField(max_length=24)
    reason = models.TextField()
    authority = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(treatment__in=list(TREATMENTS)),
                                               name='invoice_short_payment_treatment')]
