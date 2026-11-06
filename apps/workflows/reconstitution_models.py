from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class ReconstitutionPlan(AppendOnly):
    case = models.ForeignKey('core.Case',on_delete=models.PROTECT)
    recovery = models.ForeignKey('workflows.ColdRecoveryJob',on_delete=models.PROTECT)
    reference = models.CharField(max_length=100)
    version = models.PositiveIntegerField()
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'#{self.pk} / {self.reference} v{self.version}'

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case','reference','version'],name='reconstitution_plan_version')]


class ReconstitutionJob(models.Model):
    plan = models.ForeignKey(ReconstitutionPlan,on_delete=models.PROTECT)
    kind = models.CharField(max_length=12)
    effect_key = models.CharField(max_length=64)
    operation_key = models.CharField(max_length=64,unique=True)
    intent = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    status = models.CharField(max_length=12,default='pending')
    fence = models.PositiveIntegerField(default=0)
    attempts = models.PositiveIntegerField(default=0)
    lease_until = models.DateTimeField(null=True)
    receipt = models.JSONField(null=True)
    error = models.CharField(max_length=100,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ReconstitutionDisposition(AppendOnly):
    plan = models.ForeignKey(ReconstitutionPlan,on_delete=models.PROTECT)
    effect_key = models.CharField(max_length=64)
    version = models.PositiveIntegerField()
    verdict = models.CharField(max_length=24)
    probe = models.ForeignKey(ReconstitutionJob,null=True,on_delete=models.PROTECT)
    operation_key = models.CharField(max_length=100)
    pin = models.JSONField()
    rationale = models.CharField(max_length=1000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['plan','effect_key','version'],name='reconstitution_disposition_version'),
                       models.UniqueConstraint(fields=['plan','operation_key'],name='reconstitution_disposition_intent')]


class ReconstitutionReview(AppendOnly):
    plan = models.ForeignKey(ReconstitutionPlan,on_delete=models.PROTECT)
    verdict = models.CharField(max_length=12)
    operation_key = models.CharField(max_length=100)
    pin = models.JSONField()
    rationale = models.CharField(max_length=1000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['plan','operation_key'],name='reconstitution_review_intent')]
