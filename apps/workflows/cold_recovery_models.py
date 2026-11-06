from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class ColdControlIdentity(AppendOnly):
    reference = models.CharField(max_length=100, primary_key=True)
    secret_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)


class ColdRecoveryPlan(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    reference = models.CharField(max_length=100)
    version = models.PositiveIntegerField()
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'#{self.pk} / {self.reference} v{self.version}'

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'reference', 'version'], name='cold_plan_version')]


class ColdRecoveryReview(AppendOnly):
    plan = models.ForeignKey(ColdRecoveryPlan, on_delete=models.PROTECT)
    phase = models.CharField(max_length=12)
    decision = models.CharField(max_length=12)
    operation_key = models.CharField(max_length=100)
    pin = models.JSONField()
    rationale = models.CharField(max_length=1000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['plan', 'operation_key'], name='cold_review_intent')]


class ColdRecoveryJob(models.Model):
    plan = models.OneToOneField(ColdRecoveryPlan, on_delete=models.PROTECT)
    operation_key = models.CharField(max_length=64, unique=True)
    intent = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, default='pending')
    fence = models.PositiveIntegerField(default=0)
    attempts = models.PositiveIntegerField(default=0)
    lease_until = models.DateTimeField(null=True)
    receipt = models.JSONField(null=True)
    error = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
