from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly
class SupportIntake(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 tenant=models.CharField(max_length=100)
 channel=models.CharField(max_length=100)
 message_ref=models.CharField(max_length=100)
 payload=models.JSONField()
 sha256=models.CharField(max_length=64)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['tenant','channel','message_ref'],name='support_channel_message_identity')]
class SupportLink(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 intake=models.OneToOneField(SupportIntake,on_delete=models.PROTECT)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
class SupportEvent(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 version=models.PositiveIntegerField()
 action=models.CharField(max_length=40)
 state=models.CharField(max_length=100)
 owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 occurred_at=models.DateTimeField()
 snapshot=models.JSONField()
 payload=models.JSONField()
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['case','version'],name='support_event_version')]
class SupportResult(AppendOnly):
 pending=models.ForeignKey(SupportEvent,on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 payload=models.JSONField()
 authority=models.JSONField()
 created_at=models.DateTimeField(auto_now_add=True)
class SupportReport(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 snapshot=models.JSONField()
 result=models.JSONField()
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
class SupportReview(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 purpose=models.CharField(max_length=20)
 report=models.ForeignKey(SupportReport,null=True,on_delete=models.PROTECT,related_name='reviews')
 verdict=models.CharField(max_length=20)
 snapshot=models.JSONField()
 authority=models.JSONField()
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
class SupportMerge(AppendOnly):
 source=models.OneToOneField('core.Case',on_delete=models.PROTECT,related_name='support_merge_source')
 target=models.ForeignKey('core.Case',on_delete=models.PROTECT,related_name='support_merge_targets')
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 snapshot=models.JSONField()
 created_at=models.DateTimeField(auto_now_add=True)
