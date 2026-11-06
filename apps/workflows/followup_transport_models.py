from django.db import models
from django.conf import settings

class FinanceFollowupDispatch(models.Model):
    packet=models.ForeignKey('workflows.NativeFinancePacket',on_delete=models.PROTECT)
    operation_key=models.CharField(max_length=64,unique=True)
    intent=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    status=models.CharField(max_length=12,default='pending')
    attempts=models.PositiveIntegerField(default=0)
    fence=models.PositiveIntegerField(default=0)
    lease_until=models.DateTimeField(null=True)
    receipt=models.JSONField(null=True)
    error=models.CharField(max_length=100,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
