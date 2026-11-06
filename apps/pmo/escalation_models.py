from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class EscalationProfile(AppendOnly):
    def __str__(self):return f'{self.state.issue.reference} · profile #{self.pk} · {self.classification}'
    state = models.ForeignKey('IssueState', on_delete=models.PROTECT)
    classification = models.CharField(max_length=30)
    timeline_impact = models.BooleanField(null=True)
    trigger_at = models.DateTimeField(null=True)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    note = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class EscalationRequest(AppendOnly):
    profile = models.ForeignKey(EscalationProfile, on_delete=models.PROTECT, related_name='requests')
    direction = models.CharField(max_length=20)
    target = models.CharField(max_length=20)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    note = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['profile','direction','target','evidence'],name='escalation_request_identity')]


class EscalationDecision(AppendOnly):
    request = models.ForeignKey(EscalationRequest, on_delete=models.PROTECT, related_name='decisions')
    role = models.CharField(max_length=50)
    verdict = models.CharField(max_length=20)
    note = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    delegated = models.BooleanField(default=False)
    authority = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class EscalationDocumentBinding(AppendOnly):
    version = models.OneToOneField('documents.Version', on_delete=models.PROTECT)
    request = models.ForeignKey(EscalationRequest, on_delete=models.PROTECT)
    decision = models.ForeignKey(EscalationDecision, null=True, on_delete=models.PROTECT)


class EscalationSignal(AppendOnly):
    profile = models.ForeignKey(EscalationProfile, on_delete=models.PROTECT, related_name='signals')
    kind = models.CharField(max_length=40)
    target = models.CharField(max_length=20, null=True)
    policies = models.JSONField()
    policy_key = models.CharField(max_length=64)
    observed_at = models.DateTimeField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['profile','kind','policy_key'],name='escalation_signal_once')]


class EscalationScanCursor(models.Model):
    name = models.CharField(max_length=40, unique=True)
    after_issue_id = models.PositiveBigIntegerField(default=0)
