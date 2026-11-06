from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class OperatorInventory(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    operation_key=models.CharField(max_length=100)
    manifest=models.JSONField()
    sha256=models.CharField(max_length=64)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:constraints=[models.UniqueConstraint(fields=['case','operation_key'],name='ops_inventory_intent')]

class RecoveryPlan(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    reference=models.CharField(max_length=100)
    version=models.PositiveIntegerField()
    payload=models.JSONField()
    sha256=models.CharField(max_length=64)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='ops_plan_version')]

class RecoveryProof(AppendOnly):
    plan=models.ForeignKey(RecoveryPlan,on_delete=models.PROTECT)
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
    class Meta:constraints=[models.UniqueConstraint(fields=['tenant','system','external_ref','receipt_version'],name='ops_supplied_receipt_identity')]

class RecoveryJob(models.Model):
    plan=models.ForeignKey(RecoveryPlan,on_delete=models.PROTECT)
    kind=models.CharField(max_length=20)
    generation=models.PositiveIntegerField()
    operation_key=models.CharField(max_length=64,unique=True)
    intent=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    status=models.CharField(max_length=20,default='pending')
    fence=models.PositiveIntegerField(default=0)
    attempts=models.PositiveIntegerField(default=0)
    lease_until=models.DateTimeField(null=True)
    error=models.CharField(max_length=200,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:constraints=[models.UniqueConstraint(fields=['plan','kind','generation'],name='ops_job_generation')]

class RecoveryArtifact(AppendOnly):
    job=models.OneToOneField(RecoveryJob,on_delete=models.PROTECT)
    manifest=models.JSONField()
    sha256=models.CharField(max_length=64)
    receipt=models.JSONField()
    created_at=models.DateTimeField(auto_now_add=True)

class RecoveryAssessment(AppendOnly):
    plan=models.ForeignKey(RecoveryPlan,on_delete=models.PROTECT)
    operation_key=models.CharField(max_length=100)
    snapshot=models.JSONField()
    result=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:constraints=[models.UniqueConstraint(fields=['plan','operation_key'],name='ops_assessment_intent')]

class RecoveryReview(AppendOnly):
    assessment=models.ForeignKey(RecoveryAssessment,on_delete=models.PROTECT)
    operation_key=models.CharField(max_length=100)
    verdict=models.CharField(max_length=20)
    snapshot=models.JSONField()
    authority=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:constraints=[models.UniqueConstraint(fields=['assessment','operation_key'],name='ops_review_intent')]
