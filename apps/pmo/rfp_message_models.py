from uuid import uuid4

from django.conf import settings
from django.db import models

from apps.core.models import AppendOnly


class RFPFollowupDispatch(AppendOnly):
    review = models.OneToOneField('core.Audit', on_delete=models.PROTECT, related_name='+')
    outcome = models.ForeignKey('pmo.RFPOutcome', on_delete=models.PROTECT, related_name='followup_deliveries')
    configuration = models.ForeignKey('policy.Configuration', on_delete=models.PROTECT)
    contact = models.ForeignKey('core.ClientContactRevision', on_delete=models.PROTECT)
    source = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    operation = models.UUIDField(default=uuid4, unique=True)
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    route = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class RFPFollowupAttempt(AppendOnly):
    dispatch = models.OneToOneField(RFPFollowupDispatch, on_delete=models.PROTECT, related_name='attempt')
    created_at = models.DateTimeField(auto_now_add=True)


class RFPFollowupMailbox(AppendOnly):
    dispatch = models.OneToOneField(RFPFollowupDispatch, on_delete=models.PROTECT, related_name='mailbox')
    reference = models.CharField(max_length=160)
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)


class RFPFollowupReceipt(AppendOnly):
    dispatch = models.OneToOneField(RFPFollowupDispatch, on_delete=models.PROTECT, related_name='receipt')
    reference = models.CharField(max_length=160)
    delivered = models.BooleanField()
    evidence = models.ForeignKey('core.Evidence', null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class RFPFollowupCursor(models.Model):
    name = models.CharField(max_length=40, unique=True)
    last_dispatch_id = models.BigIntegerField(default=0)
