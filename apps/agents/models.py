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
