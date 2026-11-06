from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly
class SupportChannelClaim(AppendOnly):
 predecessor=models.OneToOneField('self',null=True,on_delete=models.PROTECT,related_name='successor')
 evidence=models.ForeignKey('core.Evidence',null=True,on_delete=models.PROTECT)
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 packet=models.ForeignKey('baas.SupportResponsePacket',on_delete=models.PROTECT)
 tenant=models.CharField(max_length=100)
 channel=models.CharField(max_length=100)
 account=models.CharField(max_length=100)
 external_ref=models.CharField(max_length=100)
 reference=models.CharField(max_length=100)
 payload=models.JSONField()
 sha256=models.CharField(max_length=64)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['case','reference'],name='support_channel_claim_intent'),models.UniqueConstraint(fields=['tenant','channel','account','external_ref'],condition=models.Q(predecessor__isnull=True),name='support_channel_external_identity')]
class SupportChannelCheck(models.Model):
 claim=models.ForeignKey(SupportChannelClaim,on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 intent_key=models.CharField(max_length=100)
 operation_key=models.CharField(max_length=64,unique=True)
 intent=models.JSONField()
 status=models.CharField(max_length=12,default='pending')
 fence=models.PositiveIntegerField(default=0)
 attempts=models.PositiveIntegerField(default=0)
 lease_until=models.DateTimeField(null=True)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['claim','intent_key'],name='support_channel_check_intent')]
class SupportChannelReceipt(AppendOnly):
 job=models.OneToOneField(SupportChannelCheck,on_delete=models.PROTECT)
 payload=models.JSONField()
 sha256=models.CharField(max_length=64)
 binding=models.JSONField()
 created_at=models.DateTimeField(auto_now_add=True)
class SupportChannelReview(AppendOnly):
 receipt=models.ForeignKey(SupportChannelReceipt,on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 verdict=models.CharField(max_length=12)
 authority=models.JSONField()
 created_at=models.DateTimeField(auto_now_add=True)
class SupportClockAttestation(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 receipt=models.OneToOneField(SupportChannelReceipt,on_delete=models.PROTECT)
 event=models.OneToOneField('baas.SupportEvent',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 snapshot=models.JSONField()
 created_at=models.DateTimeField(auto_now_add=True)

class SupportClockCorrection(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 predecessor=models.OneToOneField('self',null=True,on_delete=models.PROTECT,related_name='successor')
 version=models.PositiveIntegerField()
 operation_key=models.CharField(max_length=100)
 mode=models.CharField(max_length=12)
 receipt=models.ForeignKey(SupportChannelReceipt,null=True,on_delete=models.PROTECT)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 reason=models.CharField(max_length=400)
 snapshot=models.JSONField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['case','version'],name='support_clock_correction_version'),models.UniqueConstraint(fields=['case','operation_key'],name='support_clock_correction_intent')]

class SupportClockCorrectionReview(AppendOnly):
 correction=models.ForeignKey(SupportClockCorrection,on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 verdict=models.CharField(max_length=12)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 authority=models.JSONField()
 created_at=models.DateTimeField(auto_now_add=True)
