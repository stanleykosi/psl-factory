from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly
class MigrationPlan(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 reference=models.CharField(max_length=100)
 version=models.PositiveIntegerField()
 package=models.ForeignKey('documents.ValidationPackage',on_delete=models.PROTECT,null=True)
 payload=models.JSONField()
 sha256=models.CharField(max_length=64)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='migration_plan_version')]
class MigrationProof(AppendOnly):
 plan=models.ForeignKey(MigrationPlan,on_delete=models.PROTECT)
 tenant=models.CharField(max_length=100)
 system=models.CharField(max_length=100)
 external_ref=models.CharField(max_length=100)
 receipt_version=models.CharField(max_length=100)
 kind=models.CharField(max_length=30)
 payload=models.JSONField()
 sha256=models.CharField(max_length=64)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['tenant','system','external_ref','receipt_version'],name='migration_proof_identity')]
class MigrationObservation(AppendOnly):
 plan=models.ForeignKey(MigrationPlan,on_delete=models.PROTECT)
 payload=models.JSONField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
class MigrationAssessment(AppendOnly):
 plan=models.ForeignKey(MigrationPlan,on_delete=models.PROTECT)
 snapshot=models.JSONField()
 result=models.JSONField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
class MigrationReadinessReview(AppendOnly):
 assessment=models.ForeignKey(MigrationAssessment,on_delete=models.PROTECT)
 purpose=models.CharField(max_length=20)
 verdict=models.CharField(max_length=20)
 operation_key=models.CharField(max_length=100)
 snapshot=models.JSONField()
 authority=models.JSONField()
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 reason=models.CharField(max_length=1000)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['assessment','operation_key'],name='migration_review_operation')]
class MigrationAF13Binding(AppendOnly):
 assessment=models.ForeignKey(MigrationAssessment,on_delete=models.PROTECT)
 package=models.ForeignKey('documents.ValidationPackage',on_delete=models.PROTECT,related_name='migration_bindings')
 snapshot=models.JSONField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['assessment','package'],name='migration_package_binding')]
