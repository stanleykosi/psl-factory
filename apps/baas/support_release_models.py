from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly
class SupportResponsePacket(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 reference=models.CharField(max_length=100)
 draft=models.ForeignKey('baas.SupportAgentDraft',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 payload=models.JSONField()
 sha256=models.CharField(max_length=64)
 snapshot=models.JSONField()
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['case','reference'],name='support_response_packet_intent')]
class SupportResponseDecision(AppendOnly):
 packet=models.ForeignKey(SupportResponsePacket,on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 verdict=models.CharField(max_length=12)
 snapshot=models.JSONField()
 created_at=models.DateTimeField(auto_now_add=True)
class SupportResponseJob(models.Model):
 @property
 def operation_key(self):return 'support-response:'+str(self.packet.case_id)+':'+str(self.packet_id)
 packet=models.OneToOneField(SupportResponsePacket,on_delete=models.PROTECT)
 decision=models.OneToOneField(SupportResponseDecision,on_delete=models.PROTECT)
 status=models.CharField(max_length=12,default='pending')
 fence=models.PositiveIntegerField(default=0)
 attempts=models.PositiveIntegerField(default=0)
 lease_until=models.DateTimeField(null=True)
 error=models.CharField(max_length=400,blank=True)
class SupportResponseReceipt(AppendOnly):
 job=models.OneToOneField(SupportResponseJob,on_delete=models.PROTECT)
 operation_key=models.CharField(max_length=160,unique=True)
 recipient=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 payload=models.JSONField()
 sha256=models.CharField(max_length=64)
 classification=models.CharField(max_length=60)
 created_at=models.DateTimeField(auto_now_add=True)
