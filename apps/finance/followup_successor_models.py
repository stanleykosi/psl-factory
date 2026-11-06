from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class FinanceFollowupSuccessor(AppendOnly):
    followup=models.ForeignKey('finance.FinanceReceiptFollowup',on_delete=models.PROTECT)
    operation_key=models.CharField(max_length=100)
    relation=models.CharField(max_length=30)
    original=models.ForeignKey('finance.InvoiceJob',on_delete=models.PROTECT,related_name='+')
    successor=models.ForeignKey('finance.InvoiceJob',on_delete=models.PROTECT,related_name='+')
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    note=models.CharField(max_length=1000)
    pin=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['followup','operation_key'],name='finance_followup_successor_key')]

class FinanceFollowupSuccessorReview(AppendOnly):
    proposal=models.ForeignKey(FinanceFollowupSuccessor,on_delete=models.PROTECT)
    operation_key=models.CharField(max_length=100)
    verdict=models.CharField(max_length=10)
    pin=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    note=models.CharField(max_length=1000)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['proposal','operation_key'],name='finance_followup_successor_review_key')]
