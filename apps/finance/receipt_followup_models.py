from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class FinanceReceiptFollowup(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    request_key=models.CharField(max_length=64,unique=True)
    projection=models.JSONField()
    sha256=models.CharField(max_length=64)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):return f'Receipt follow-up #{self.pk}'

class FinanceReceiptFollowupDecision(AppendOnly):
    followup=models.ForeignKey(FinanceReceiptFollowup,on_delete=models.PROTECT)
    operation_key=models.CharField(max_length=100)
    verdict=models.CharField(max_length=30)
    job=models.ForeignKey('finance.InvoiceJob',on_delete=models.PROTECT,null=True)
    pin=models.JSONField()
    note=models.CharField(max_length=1000)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['followup','operation_key'],name='finance_receipt_followup_decision_key')]
