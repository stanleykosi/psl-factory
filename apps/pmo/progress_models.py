"""Source observations and PM correlations, never another issue register."""
from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class DeliveryProgressSource(AppendOnly):
    dossier = models.ForeignKey('pmo.DeliveryDossier', on_delete=models.PROTECT, related_name='progress_sources')
    team = models.CharField(max_length=20)
    source_identity = models.CharField(max_length=200)
    source_ref = models.CharField(max_length=240)
    participant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    mode = models.CharField(max_length=20)
    max_age_seconds = models.PositiveIntegerField(null=True)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['dossier','source_identity','source_ref'], name='delivery_progress_source_identity')]


class DeliveryProgressObservation(AppendOnly):
    source = models.ForeignKey(DeliveryProgressSource, on_delete=models.PROTECT, related_name='observations')
    previous = models.OneToOneField('self', null=True, on_delete=models.PROTECT, related_name='successor')
    source_version = models.CharField(max_length=100)
    observed_at = models.DateTimeField()
    availability = models.CharField(max_length=20)
    fields = models.JSONField()
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    source_sha256 = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['source','source_version'], name='delivery_progress_source_version')]


class DeliveryProgressCorrelation(AppendOnly):
    observation = models.ForeignKey(DeliveryProgressObservation, on_delete=models.PROTECT, related_name='correlations')
    previous = models.OneToOneField('self', null=True, on_delete=models.PROTECT, related_name='successor')
    planning = models.ForeignKey('pmo.DeliveryRecord', on_delete=models.PROTECT)
    issue_state = models.ForeignKey('pmo.IssueState', on_delete=models.PROTECT)
    profile = models.OneToOneField('pmo.EscalationProfile', null=True, on_delete=models.PROTECT)
    impact = models.CharField(max_length=4000)
    snapshot = models.JSONField()
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
