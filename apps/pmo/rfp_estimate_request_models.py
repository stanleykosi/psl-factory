from uuid import uuid4

from django.conf import settings
from django.db import models

from apps.core.models import AppendOnly


class RFPEstimateRequest(AppendOnly):
    work = models.ForeignKey('workflows.FactoryWork', on_delete=models.PROTECT, related_name='estimate_requests')
    intake = models.ForeignKey('pmo.RFPIntake', on_delete=models.PROTECT)
    draft = models.ForeignKey('agents.AgentRun', on_delete=models.PROTECT)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    configuration = models.ForeignKey('policy.Configuration', on_delete=models.PROTECT)
    attachment = models.ForeignKey('agents.CaseUpload', null=True, on_delete=models.PROTECT)
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class RFPEstimateDispatch(AppendOnly):
    request = models.OneToOneField(RFPEstimateRequest, on_delete=models.PROTECT, related_name='dispatch')
    operation = models.UUIDField(default=uuid4, unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class RFPEstimateMailbox(AppendOnly):
    dispatch = models.OneToOneField(RFPEstimateDispatch, on_delete=models.PROTECT, related_name='mailbox')
    reference = models.CharField(max_length=160)
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)


class RFPEstimateReceipt(AppendOnly):
    dispatch = models.OneToOneField(RFPEstimateDispatch, on_delete=models.PROTECT, related_name='receipt')
    reference = models.CharField(max_length=160)
    delivered = models.BooleanField()
    evidence = models.ForeignKey('core.Evidence', null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
