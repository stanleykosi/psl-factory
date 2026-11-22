from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import AppendOnly


class NativeStation(models.Model):
    """Outbox entry created by the source transaction, including while policy is undecided."""

    process = models.CharField(max_length=3)
    projection_version = models.PositiveSmallIntegerField(default=1)
    subject_model = models.CharField(max_length=100)
    subject_pk = models.CharField(max_length=100)
    available_at = models.DateTimeField(default=timezone.now)
    work = models.OneToOneField("workflows.FactoryWork", on_delete=models.PROTECT, null=True, related_name="native_station")
    finding = models.CharField(max_length=120, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["process", "subject_model", "subject_pk"], name="native_station_subject"),
            models.CheckConstraint(condition=models.Q(projection_version=1) | models.Q(process="F02", projection_version=2),
                                   name="native_station_projection_version"),
        ]
        indexes = [models.Index(fields=["available_at"], condition=models.Q(work__isnull=True), name="native_station_due")]


class NativeStationAdvice(AppendOnly):
    """Exact source packet passed to the business station ahead of receipt verification."""

    station = models.ForeignKey(NativeStation, on_delete=models.PROTECT, related_name="handoffs")
    packet = models.OneToOneField("agents.SpecialistPacket", on_delete=models.PROTECT)
    projection_sha256 = models.CharField(max_length=64)
    packet_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)


class NativeStationReceipt(AppendOnly):
    handoff = models.OneToOneField(NativeStationAdvice, on_delete=models.PROTECT, related_name="receipt")
    receiver_model = models.CharField(max_length=100)
    receiver_pk = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)


class NativeStationUse(AppendOnly):
    """The receiving command checked this exact advice in its own transaction."""

    handoff = models.ForeignKey(NativeStationAdvice, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["handoff", "actor"], name="native_station_recipient_use")]
