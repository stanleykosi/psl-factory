from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class FinanceFollowupReadback(AppendOnly):
    packet=models.ForeignKey('workflows.NativeFinancePacket',on_delete=models.PROTECT)
    operation_key=models.CharField(max_length=100)
    projection=models.JSONField()
    result=models.JSONField()
    pin=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['packet','operation_key'],name='finance_followup_readback_key')]

class FinanceFollowupReadbackReview(AppendOnly):
    observation=models.ForeignKey(FinanceFollowupReadback,on_delete=models.PROTECT)
    operation_key=models.CharField(max_length=100)
    verdict=models.CharField(max_length=12)
    pin=models.JSONField()
    rationale=models.CharField(max_length=1000)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['observation','operation_key'],name='finance_followup_readback_review_key')]
