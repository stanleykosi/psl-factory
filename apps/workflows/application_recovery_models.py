from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class RecoveryAttachment(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    source_ref = models.CharField(max_length=100)
    label = models.CharField(max_length=120)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ApplicationRecoveryPlan(AppendOnly):
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
        constraints = [models.UniqueConstraint(fields=['case', 'reference', 'version'], name='app_recovery_plan_version')]


class ApplicationRecoveryJob(models.Model):
    plan = models.ForeignKey(ApplicationRecoveryPlan, on_delete=models.PROTECT)
    kind = models.CharField(max_length=12)
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

    class Meta:
        constraints = [models.UniqueConstraint(fields=['plan', 'kind'], name='app_recovery_exact_kind')]


class ApplicationRecoveryReview(AppendOnly):
    plan = models.ForeignKey(ApplicationRecoveryPlan, on_delete=models.PROTECT)
    phase = models.CharField(max_length=12)
    operation_key = models.CharField(max_length=100)
    decision = models.CharField(max_length=12)
    pin = models.JSONField()
    rationale = models.CharField(max_length=1000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['plan', 'operation_key'], name='app_recovery_review_intent')]
