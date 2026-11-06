from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class ChangeRequest(models.Model):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    reference = models.CharField(max_length=160)
    current = models.ForeignKey('ChangeVersion', null=True, on_delete=models.PROTECT, related_name='+')
    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'reference'], name='change_reference_identity')]


class ChangeVersion(AppendOnly):
    change = models.ForeignKey(ChangeRequest, on_delete=models.PROTECT, related_name='versions')
    number = models.PositiveIntegerField()
    category = models.CharField(max_length=20)
    module = models.CharField(max_length=160)
    description = models.TextField()
    reason = models.TextField()
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    incident = models.ForeignKey('core.Evidence', null=True, on_delete=models.PROTECT, related_name='+')
    base_manifest = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['change', 'number'], name='change_version_identity')]


class ChangeAssessment(AppendOnly):
    impact_details = models.JSONField(default=dict)
    version = models.ForeignKey(ChangeVersion, on_delete=models.PROTECT, related_name='assessments')
    contributor = models.CharField(max_length=40)
    cost_impact = models.BooleanField(null=True)
    timeline_impact = models.BooleanField(null=True)
    client_facing = models.BooleanField(null=True)
    note = models.TextField()
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ChangeDecision(AppendOnly):
    version = models.ForeignKey(ChangeVersion, on_delete=models.PROTECT, related_name='decisions')
    role = models.CharField(max_length=50)
    verdict = models.CharField(max_length=20)
    assessment_ids = models.JSONField()
    authority = models.JSONField()
    note = models.TextField()
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ChangeAuthorization(AppendOnly):
    version = models.ForeignKey(ChangeVersion, on_delete=models.PROTECT)
    commercial = models.OneToOneField('CommercialRevision', null=True, on_delete=models.PROTECT)
    assessment_ids = models.JSONField()
    decision_ids = models.JSONField()
    preapproval_snapshot = models.JSONField(default=dict)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ChangeDocumentBinding(AppendOnly):
    version = models.OneToOneField('documents.Version', on_delete=models.PROTECT)
    authorization = models.ForeignKey(ChangeAuthorization, on_delete=models.PROTECT)
    purpose = models.CharField(max_length=20)
    execution_ids = models.JSONField(default=list)
    authority_recovery = models.ForeignKey('pmo.AuthorityRecoveryRecord',null=True,on_delete=models.PROTECT)


class ChangeExecutionEvent(AppendOnly):
    impact_details = models.JSONField(default=dict)
    authorization = models.ForeignKey(ChangeAuthorization, on_delete=models.PROTECT, related_name='execution')
    kind = models.CharField(max_length=30)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    note = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ChangeClosure(AppendOnly):
    authorization = models.OneToOneField(ChangeAuthorization, on_delete=models.PROTECT)
    receipt = models.ForeignKey('documents.PublicationReceipt', on_delete=models.PROTECT)
    pm_signature = models.ForeignKey('core.Evidence', on_delete=models.PROTECT, related_name='+')
    client_signature = models.ForeignKey('core.Evidence', on_delete=models.PROTECT, related_name='+')
    execution_ids = models.JSONField()
    note = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
