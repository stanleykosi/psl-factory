from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class AuthorityRecoveryRequest(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    outcome = models.ForeignKey('pmo.EmergencyOutcome', null=True, on_delete=models.PROTECT)
    adoption = models.ForeignKey('pmo.BaselineAdoption', null=True, on_delete=models.PROTECT)
    snapshot = models.JSONField()
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    note = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=(models.Q(outcome__isnull=False, adoption__isnull=True) |
            models.Q(outcome__isnull=True, adoption__isnull=False)), name='recovery_exact_target')]


class AuthorityRecoveryDecision(AppendOnly):
    request = models.ForeignKey(AuthorityRecoveryRequest, on_delete=models.PROTECT, related_name='decisions')
    role = models.CharField(max_length=50)
    verdict = models.CharField(max_length=20)
    authority = models.JSONField()
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    note = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class AuthorityRecoveryRecord(AppendOnly):
    request = models.OneToOneField(AuthorityRecoveryRequest, on_delete=models.PROTECT)
    decision_ids = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class EmergencyFollowup(AppendOnly):
    outcome = models.ForeignKey('pmo.EmergencyOutcome', on_delete=models.PROTECT, related_name='followups')
    version = models.OneToOneField('pmo.ChangeVersion', on_delete=models.PROTECT)
    supersedes = models.OneToOneField('self',null=True,on_delete=models.PROTECT,related_name='replacement')
    note = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class EmergencyFollowupCompletion(AppendOnly):
    followup = models.OneToOneField(EmergencyFollowup, on_delete=models.PROTECT)
    closure = models.OneToOneField('pmo.ChangeClosure', on_delete=models.PROTECT)
    note = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
