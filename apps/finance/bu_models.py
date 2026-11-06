from django.db import models
from django.conf import settings
from apps.core.models import AppendOnly
class BUWork(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 reference=models.CharField(max_length=100)
 kind=models.CharField(max_length=20)
 version=models.PositiveIntegerField()
 operation_key=models.CharField(max_length=100)
 parent=models.ForeignKey('self',null=True,on_delete=models.PROTECT)
 payroll=models.ForeignKey('finance.PayrollRun',null=True,on_delete=models.PROTECT)
 metadata=models.JSONField()
 payload=models.JSONField()
 sha256=models.CharField(max_length=64)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['case','operation_key'],name='bu_work_operation'),models.UniqueConstraint(fields=['case','reference','kind','version'],name='bu_work_version')]
 def __str__(self):return f'{self.kind} #{self.pk} / v{self.version} / {self.metadata.get("status")}'
class BUReview(AppendOnly):
 work=models.ForeignKey(BUWork,on_delete=models.PROTECT,related_name='reviews')
 purpose=models.CharField(max_length=20)
 verdict=models.CharField(max_length=20)
 operation_key=models.CharField(max_length=100)
 authority=models.JSONField()
 subject_sha256=models.CharField(max_length=64)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['work','operation_key'],name='bu_review_operation')]
class BUReport(AppendOnly):
 work=models.ForeignKey(BUWork,on_delete=models.PROTECT)
 review=models.ForeignKey(BUReview,on_delete=models.PROTECT)
 version=models.PositiveIntegerField()
 operation_key=models.CharField(max_length=100)
 payload=models.JSONField()
 policy_ids=models.JSONField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['work','operation_key'],name='bu_report_operation'),models.UniqueConstraint(fields=['work','version'],name='bu_report_version')]
class BUReceipt(AppendOnly):
 report=models.ForeignKey(BUReport,on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['report','actor'],name='bu_receipt_person')]
class BUEventClaim(AppendOnly):
 tenant=models.CharField(max_length=100)
 source=models.CharField(max_length=100)
 event_id=models.CharField(max_length=100)
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 reference=models.CharField(max_length=100)
 class Meta:constraints=[models.UniqueConstraint(fields=['tenant','source','event_id'],name='bu_event_identity')]
