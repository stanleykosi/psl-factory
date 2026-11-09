"""F30 generation history. No invoice issue, posting or delivery identity."""
import uuid
from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class DraftGeneration(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    preparation = models.ForeignKey('finance.BillingPreparation', on_delete=models.PROTECT)
    source = models.ForeignKey('finance.BillingEvidenceSource', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    tenant = models.CharField(max_length=100)
    operation_key = models.CharField(max_length=100)
    business_key = models.CharField(max_length=64)
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['tenant', 'operation_key'], name='draft_generation_operation'),
                       models.UniqueConstraint(fields=['tenant', 'business_key'], name='draft_generation_business')]

class DraftGenerationAttempt(AppendOnly):
    generation = models.ForeignKey(DraftGeneration, on_delete=models.PROTECT, related_name='attempts')
    action = models.CharField(max_length=20)
    sequence = models.PositiveIntegerField()
    fence = models.UUIDField(default=uuid.uuid4, unique=True)
    intent_sha256 = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['generation', 'sequence'], name='draft_generation_attempt_sequence'),
                       models.UniqueConstraint(fields=['generation'], condition=models.Q(action='generate'), name='draft_generation_once')]

class DraftGenerationObservation(AppendOnly):
    attempt = models.ForeignKey(DraftGenerationAttempt, on_delete=models.PROTECT, related_name='observations')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fence = models.UUIDField()
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    accepted = models.BooleanField()
    finding = models.CharField(max_length=240)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['attempt', 'sha256'], name='draft_generation_observation_retry')]

class DraftGenerationCancellation(AppendOnly):
    generation = models.OneToOneField(DraftGeneration, on_delete=models.PROTECT, related_name='cancellation')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
