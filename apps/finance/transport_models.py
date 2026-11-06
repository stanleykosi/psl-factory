from django.db import models
from django.conf import settings
from apps.core.models import AppendOnly

class FinanceAuthenticatedIntake(AppendOnly):
    followup=models.ForeignKey('finance.FinanceReceiptFollowup',on_delete=models.PROTECT)
    sender_ref=models.CharField(max_length=100)
    destination_ref=models.CharField(max_length=100)
    operation_key=models.CharField(max_length=64)
    envelope=models.JSONField()
    sha256=models.CharField(max_length=64)
    pin=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['sender_ref','destination_ref','operation_key'],name='finance_authenticated_intake_identity')]
