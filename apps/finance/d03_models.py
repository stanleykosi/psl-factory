from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly
class BillingEvidenceSource(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 reference=models.CharField(max_length=100)
 version=models.PositiveIntegerField()
 kind=models.CharField(max_length=30)
 tenant=models.CharField(max_length=100)
 system=models.CharField(max_length=100)
 external_ref=models.CharField(max_length=100)
 source_version=models.CharField(max_length=100)
 payload=models.JSONField()
 sha256=models.CharField(max_length=64)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='d03_source_version'),models.UniqueConstraint(fields=['tenant','system','external_ref','source_version'],name='d03_source_identity')]
class BillingEvidenceReview(AppendOnly):
 source=models.ForeignKey(BillingEvidenceSource,on_delete=models.PROTECT)
 verdict=models.CharField(max_length=20)
 meaning=models.CharField(max_length=30)
 operation_key=models.CharField(max_length=100)
 authority=models.JSONField()
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['source','operation_key'],name='d03_source_review_intent')]
class BillingReleaseProfile(AppendOnly):
 coverage=models.OneToOneField('finance.BillingCoverage',on_delete=models.PROTECT)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
class BillingControlReceipt(AppendOnly):
 invoice=models.ForeignKey('finance.Invoice',on_delete=models.PROTECT)
 effect=models.CharField(max_length=20)
 control_key=models.CharField(max_length=100)
 tenant=models.CharField(max_length=100)
 system=models.CharField(max_length=100)
 external_ref=models.CharField(max_length=100)
 source_version=models.CharField(max_length=100)
 payload=models.JSONField()
 sha256=models.CharField(max_length=64)
 snapshot=models.JSONField()
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['tenant','system','external_ref','source_version'],name='d03_control_identity')]
class BillingReleaseAssessment(AppendOnly):
 invoice=models.ForeignKey('finance.Invoice',on_delete=models.PROTECT)
 effect=models.CharField(max_length=20)
 snapshot=models.JSONField()
 result=models.JSONField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
class BillingReleaseBinding(AppendOnly):
 assessment=models.OneToOneField(BillingReleaseAssessment,on_delete=models.PROTECT)
 snapshot=models.JSONField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
