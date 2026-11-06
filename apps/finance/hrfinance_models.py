from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class HRFinanceNeed(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 reference=models.CharField(max_length=100)
 version=models.PositiveIntegerField()
 payload=models.JSONField()
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='hr_finance_need_version')]
 def __str__(self):return f'{self.reference} v{self.version} / #{self.pk}'

class HRDisclosure(AppendOnly):
 need=models.ForeignKey(HRFinanceNeed,on_delete=models.PROTECT)
 operation_key=models.CharField(max_length=100)
 payload=models.JSONField()
 policy_ids=models.JSONField()
 sha256=models.CharField(max_length=64)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['need','operation_key'],name='hr_disclosure_operation')]
 def __str__(self):return f'Contract #{self.pk} / need #{self.need_id}'

class HRReadSnapshot(AppendOnly):
 contract=models.ForeignKey(HRDisclosure,on_delete=models.PROTECT,related_name='snapshots')
 operation_key=models.CharField(max_length=100)
 status=models.CharField(max_length=20)
 source_sha256=models.CharField(max_length=64)
 sha256=models.CharField(max_length=64)
 payload=models.JSONField()
 manifest=models.JSONField()
 retain_until=models.DateTimeField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['contract','operation_key'],name='hr_snapshot_operation')]
 def __str__(self):return f'Snapshot #{self.pk} / {self.status}'

class HRHandoffRecord(AppendOnly):
 contract=models.ForeignKey(HRDisclosure,on_delete=models.PROTECT,related_name='records')
 snapshot=models.ForeignKey(HRReadSnapshot,null=True,on_delete=models.PROTECT)
 kind=models.CharField(max_length=20)
 operation_key=models.CharField(max_length=100)
 payload=models.JSONField()
 authority=models.JSONField()
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['contract','operation_key'],name='hr_handoff_operation')]
