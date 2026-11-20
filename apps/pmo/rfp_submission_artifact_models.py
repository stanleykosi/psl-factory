from django.db import models

from apps.core.models import AppendOnly


class RFPSubmissionArtifact(AppendOnly):
    """Private immutable bytes for one exact client document and pack draft."""

    binding = models.OneToOneField('pmo.RFPDocumentBinding', on_delete=models.PROTECT)
    payload_sha256 = models.CharField(max_length=64)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    content = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)
