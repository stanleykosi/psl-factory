from django.conf import settings
from django.db import models

from apps.core.models import AppendOnly


class ArchiveCopyPlan(AppendOnly):
    work = models.ForeignKey('workflows.FactoryWork', on_delete=models.PROTECT, related_name='file_archives')
    archive = models.ForeignKey('pmo.DeliveryRecord', on_delete=models.PROTECT)
    configuration = models.ForeignKey('policy.Configuration', on_delete=models.PROTECT)
    manifest = models.JSONField()
    sha256 = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ArchiveCopyFile(AppendOnly):
    plan = models.ForeignKey(ArchiveCopyPlan, on_delete=models.PROTECT, related_name='files')
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    upload = models.ForeignKey('agents.CaseUpload', null=True, on_delete=models.PROTECT)
    name = models.CharField(max_length=200)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['plan', 'evidence'], condition=models.Q(upload__isnull=True),
                                    name='archive_evidence_copy_once'),
            models.UniqueConstraint(fields=['plan', 'upload'], condition=models.Q(upload__isnull=False),
                                    name='archive_attachment_copy_once'),
        ]


class ArchiveCopyJob(models.Model):
    file = models.OneToOneField(ArchiveCopyFile, on_delete=models.PROTECT, related_name='job')
    status = models.CharField(max_length=12, default='pending', db_index=True)
    revision = models.PositiveIntegerField(default=1)
    lease_token = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    finding = models.CharField(max_length=240, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=models.Q(status__in=['pending', 'leased', 'unknown', 'missing', 'confirmed', 'held']),
            name='archive_copy_job_status',
        )]


class ArchiveCopyAttempt(AppendOnly):
    job = models.ForeignKey(ArchiveCopyJob, on_delete=models.PROTECT, related_name='attempts')
    token = models.UUIDField(unique=True)
    operation = models.CharField(max_length=12)
    outcome = models.CharField(max_length=12)
    created_at = models.DateTimeField(auto_now_add=True)


class ArchiveCopyReceipt(AppendOnly):
    file = models.OneToOneField(ArchiveCopyFile, on_delete=models.PROTECT, related_name='receipt')
    attempt = models.OneToOneField(ArchiveCopyAttempt, on_delete=models.PROTECT)
    object_key = models.CharField(max_length=240, unique=True)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class SyntheticArchiveObject(AppendOnly):
    file = models.OneToOneField(ArchiveCopyFile, on_delete=models.PROTECT)
    data = models.BinaryField()
    sha256 = models.CharField(max_length=64)
