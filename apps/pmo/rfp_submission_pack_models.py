from django.conf import settings
from django.db import models

from apps.core.models import AppendOnly


class RFPSubmissionPack(AppendOnly):
    """One draft declaration and cover note for an exact native response."""

    response = models.ForeignKey('pmo.RFPResponse', on_delete=models.PROTECT)
    number = models.PositiveIntegerField()
    supersedes = models.OneToOneField('self', null=True, on_delete=models.PROTECT)
    source = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    cover_note = models.CharField(max_length=4000, blank=True)
    file_extension = models.CharField(max_length=16, blank=True)
    file_count = models.PositiveIntegerField(null=True, blank=True)
    file_size_rule = models.CharField(max_length=12, blank=True)
    file_size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['response', 'number'], name='rfp_submission_pack_revision'),
        ]
