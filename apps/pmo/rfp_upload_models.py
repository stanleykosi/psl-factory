"""The private object reservation survives a failed bid intake transaction."""

from uuid import uuid4

from django.conf import settings
from django.db import models


class RFPStagedUpload(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    case = models.ForeignKey('core.Case', null=True, on_delete=models.PROTECT)
    case_revision = models.PositiveBigIntegerField(null=True)
    authority = models.ForeignKey('identity.TenantAuthority', null=True, on_delete=models.PROTECT)
    operation = models.CharField(max_length=64, unique=True)
    payload_sha256 = models.CharField(max_length=64)
    storage_identity = models.CharField(max_length=64)
    key = models.CharField(max_length=100, unique=True)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    intake = models.OneToOneField('RFPIntake', null=True, on_delete=models.PROTECT)
    upload = models.OneToOneField('agents.CaseUpload', null=True, on_delete=models.PROTECT)

    class Meta:
        indexes = [models.Index(fields=['actor', '-created_at', '-id'], name='rfp_upload_actor_recent')]
        constraints = [
            models.CheckConstraint(condition=(models.Q(case__isnull=False, case_revision__isnull=False,
                                                       case_revision__gte=1, authority__isnull=True)
                                              | models.Q(case__isnull=True, case_revision__isnull=True, authority__isnull=False)),
                                   name='rfp_staged_upload_one_scope'),
            models.CheckConstraint(condition=(models.Q(intake__isnull=True, upload__isnull=True)
                                              | models.Q(intake__isnull=False, upload__isnull=False)),
                                   name='rfp_staged_upload_one_binding'),
        ]
