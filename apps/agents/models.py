from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly
from .boundary_models import EvidenceProjection,EvidenceProjectionReview,EvidenceExtraction,EvidenceExtractionReceipt,EvidenceExtractionReview

class AgentRun(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    provider = models.CharField(max_length=100)
    process_id = models.CharField(max_length=10)
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class CaseUpload(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    key = models.CharField(max_length=100, unique=True)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()


class AgentJob(models.Model):
    upload = models.ForeignKey(CaseUpload, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    role = models.CharField(max_length=3)
    status = models.CharField(max_length=12, default='queued', db_index=True)
    result = models.JSONField(default=dict)
    started_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['upload', 'actor', 'role'], name='unique_upload_agent_job')]
