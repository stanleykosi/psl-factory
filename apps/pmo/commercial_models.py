from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class CommercialCase(models.Model):
    case = models.OneToOneField('core.Case', on_delete=models.PROTECT)
    current = models.ForeignKey('CommercialRevision', null=True, on_delete=models.PROTECT, related_name='+')


class CommercialRevision(AppendOnly):
    dossier = models.ForeignKey(CommercialCase, on_delete=models.PROTECT, related_name='revisions')
    number = models.PositiveIntegerField()
    sources = models.JSONField()
    base_manifest = models.JSONField()
    reason = models.TextField()
    context = models.ForeignKey('core.Evidence', on_delete=models.PROTECT, related_name='+')
    previous = models.ForeignKey('self', null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['dossier', 'number'], name='commercial_revision_number')]


class CommercialDecision(AppendOnly):
    revision = models.ForeignKey(CommercialRevision, on_delete=models.PROTECT, related_name='decisions')
    role = models.CharField(max_length=50)
    verdict = models.CharField(max_length=20)
    note = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    authority = models.JSONField()
    delegated = models.BooleanField(default=False)
    inherited = models.ForeignKey('self', null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class CommercialDocumentBinding(AppendOnly):
    version = models.OneToOneField('documents.Version', on_delete=models.PROTECT)
    revision = models.ForeignKey(CommercialRevision, on_delete=models.PROTECT)
    decision_ids = models.JSONField()


class ClientResponse(AppendOnly):
    revision = models.ForeignKey(CommercialRevision, on_delete=models.PROTECT, related_name='responses')
    receipt = models.ForeignKey('documents.PublicationReceipt', on_delete=models.PROTECT)
    kind = models.CharField(max_length=20)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    note = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class BaselineAdoption(AppendOnly):
    revision = models.OneToOneField(CommercialRevision, on_delete=models.PROTECT)
    response = models.OneToOneField(ClientResponse, on_delete=models.PROTECT)
    before = models.JSONField()
    after = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
