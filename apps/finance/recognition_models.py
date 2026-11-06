from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class ProgressPacket(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 reference=models.CharField(max_length=100)
 version=models.PositiveIntegerField()
 payload=models.JSONField()
 manifest=models.JSONField()
 sha256=models.CharField(max_length=64)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='progress_packet_version')]
 def __str__(self):return f'{self.reference} v{self.version} / #{self.pk}'

class RecognitionRecord(AppendOnly):
 packet=models.ForeignKey(ProgressPacket,on_delete=models.PROTECT,related_name='records')
 kind=models.CharField(max_length=30)
 operation_key=models.CharField(max_length=100)
 payload=models.JSONField()
 authority=models.JSONField()
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['packet','operation_key'],name='recognition_record_operation')]
