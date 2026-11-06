from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.core.models import AppendOnly
class PayrollRequest(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 reference=models.CharField(max_length=100)
 version=models.PositiveIntegerField()
 metadata=models.JSONField()
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='payroll_request_version')]
 def __str__(self):return f'{self.reference} v{self.version} / #{self.pk}'
class PayrollInput(AppendOnly):
 request=models.ForeignKey(PayrollRequest,on_delete=models.PROTECT,related_name='inputs')
 provider=models.CharField(max_length=100)
 version=models.PositiveIntegerField()
 operation_key=models.CharField(max_length=100)
 source_sha256=models.CharField(max_length=64)
 sha256=models.CharField(max_length=64)
 metadata=models.JSONField()
 payload=models.JSONField()
 retain_until=models.DateTimeField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['request','operation_key'],name='payroll_input_operation'),models.UniqueConstraint(fields=['request','provider','version'],name='payroll_input_version')]
 def __str__(self):return f'Input #{self.pk} / {self.provider} v{self.version}'
class PayrollRun(AppendOnly):
 request=models.ForeignKey(PayrollRequest,on_delete=models.PROTECT,related_name='runs')
 parent=models.ForeignKey('self',null=True,on_delete=models.PROTECT)
 hr_snapshot=models.ForeignKey('finance.HRReadSnapshot',null=True,on_delete=models.PROTECT)
 kind=models.CharField(max_length=20)
 operation_key=models.CharField(max_length=100)
 sha256=models.CharField(max_length=64)
 metadata=models.JSONField()
 result=models.JSONField()
 retain_until=models.DateTimeField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['request','operation_key'],name='payroll_run_operation')]
 def __str__(self):return f'{self.kind} #{self.pk} / {self.metadata.get("status")}'
class PayrollReview(AppendOnly):
 request=models.ForeignKey(PayrollRequest,on_delete=models.PROTECT)
 input=models.ForeignKey(PayrollInput,null=True,on_delete=models.PROTECT,related_name='reviews')
 run=models.ForeignKey(PayrollRun,null=True,on_delete=models.PROTECT,related_name='reviews')
 operation_key=models.CharField(max_length=100)
 verdict=models.CharField(max_length=20)
 authority=models.JSONField()
 subject_sha256=models.CharField(max_length=64)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['request','operation_key'],name='payroll_review_operation'),models.CheckConstraint(condition=Q(input__isnull=False,run__isnull=True)|Q(input__isnull=True,run__isnull=False),name='payroll_review_one_subject')]
class PayrollPublication(AppendOnly):
 request=models.ForeignKey(PayrollRequest,on_delete=models.PROTECT)
 run=models.ForeignKey(PayrollRun,on_delete=models.PROTECT)
 review=models.ForeignKey(PayrollReview,on_delete=models.PROTECT)
 version=models.PositiveIntegerField()
 operation_key=models.CharField(max_length=100)
 payload=models.JSONField()
 policy_ids=models.JSONField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['request','operation_key'],name='payroll_publication_operation'),models.UniqueConstraint(fields=['request','version'],name='payroll_publication_version')]
class PayrollReportReceipt(AppendOnly):
 publication=models.ForeignKey(PayrollPublication,on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['publication','actor'],name='payroll_report_receipt_person')]
class PayrollHRFollowup(AppendOnly):
 run=models.ForeignKey(PayrollRun,on_delete=models.PROTECT)
 record=models.OneToOneField('finance.HRHandoffRecord',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
