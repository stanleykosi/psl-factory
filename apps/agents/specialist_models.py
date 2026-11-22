from django.conf import settings
from django.db import models
from django.utils import timezone


class SpecialistReading(models.Model):
    """Private model call and its immutable source binding. No generic evidence export."""

    work = models.ForeignKey("workflows.FactoryWork", on_delete=models.PROTECT)
    child = models.ForeignKey("workflows.FactoryActivity", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    source = models.ForeignKey("core.Evidence", on_delete=models.PROTECT)
    identity = models.CharField(max_length=64, unique=True)
    source_hash = models.CharField(max_length=64)
    projection_sha256 = models.CharField(max_length=64, blank=True)
    policy = models.ForeignKey("policy.Configuration", on_delete=models.PROTECT)
    permission = models.ForeignKey(
        "policy.Configuration", null=True, related_name="+", on_delete=models.PROTECT
    )
    process = models.CharField(max_length=3)
    role = models.CharField(max_length=3)
    model = models.CharField(max_length=160)
    token_limit = models.PositiveIntegerField()
    status = models.CharField(max_length=16, default="queued")
    finding = models.CharField(max_length=160, blank=True)
    claim = models.UUIDField(null=True)
    available_at = models.DateTimeField(default=timezone.now)
    citation_lines = models.JSONField(default=list)
    disposition = models.CharField(max_length=16, blank=True)
    anchors = models.JSONField(default=list)
    staged = models.TextField(blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    size = models.PositiveIntegerField(default=0)
    storage_attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def key(self):
        return f"specialist/{self.work.case_id}/{self.identity}/{self.sha256}.txt"

    class Meta:
        indexes = [models.Index(fields=["status", "available_at"], name="specialist_reading_due")]


class SpecialistPacket(models.Model):
    """O01's exact contributions for one handoff. Reuse only identical inputs."""

    work = models.ForeignKey("workflows.FactoryWork", on_delete=models.PROTECT)
    child = models.ForeignKey("workflows.FactoryActivity", on_delete=models.PROTECT)
    identity = models.CharField(max_length=64, unique=True)
    process = models.CharField(max_length=3)
    members = models.ManyToManyField(SpecialistReading)
    consumed_at = models.DateTimeField(null=True)
    superseded_by = models.ForeignKey("self", null=True, on_delete=models.PROTECT)
    reviewed_hash = models.CharField(max_length=64, blank=True)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    review_reason = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True)
    coordinator_model = models.CharField(max_length=160, blank=True)


class SpecialistCoordination(models.Model):
    """One leased coordinator call over a particular packet and stage."""

    packet = models.ForeignKey(SpecialistPacket, on_delete=models.PROTECT, related_name="coordination")
    phase = models.CharField(max_length=8, choices=[("route", "Route"), ("review", "Review")])
    input_sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=10, default="queued")
    attempts = models.PositiveSmallIntegerField(default=1)
    claim = models.UUIDField(null=True)
    available_at = models.DateTimeField(default=timezone.now)
    result = models.JSONField(default=dict)
    output_sha256 = models.CharField(max_length=64, blank=True)
    finding = models.CharField(max_length=180, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["packet", "phase"], name="specialist_coordination_phase"),
        ]
        indexes = [
            models.Index(fields=["status", "available_at"], name="specialist_coordination_due"),
        ]
