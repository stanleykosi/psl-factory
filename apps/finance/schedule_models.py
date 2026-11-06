from django.db import models
from django.conf import settings
from apps.core.models import AppendOnly

class ScheduleWork(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 reference=models.CharField(max_length=100)
 version=models.PositiveIntegerField()
 kind=models.CharField(max_length=20)
 parent=models.ForeignKey('finance.FinanceRun',null=True,on_delete=models.PROTECT)
 payload=models.JSONField()
 snapshot=models.JSONField()
 result=models.JSONField()
 sha256=models.CharField(max_length=64)
 operation_key=models.CharField(max_length=64,unique=True)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['case','reference','kind','version'],name='schedule_work_version'),models.CheckConstraint(condition=models.Q(kind='income',parent__isnull=False)|models.Q(kind='inventory',parent__isnull=True)|models.Q(kind='ppe_register',parent__isnull=True)|models.Q(kind='ppe_schedule'),name='schedule_work_parent_kind')]
 def __str__(self):return f'{self.kind} #{self.pk} v{self.version}'

class ScheduleReview(AppendOnly):
 work=models.ForeignKey(ScheduleWork,on_delete=models.PROTECT,related_name='reviews')
 verdict=models.CharField(max_length=20)
 authority=models.JSONField()
 snapshot=models.JSONField()
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 note=models.TextField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)

class ScheduleAdjustment(AppendOnly):
 work=models.ForeignKey(ScheduleWork,on_delete=models.PROTECT)
 review=models.ForeignKey(ScheduleReview,on_delete=models.PROTECT)
 kind=models.CharField(max_length=20)
 adjustment=models.OneToOneField('finance.FinanceAdjustment',on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['work','kind'],name='schedule_adjustment_once')]
