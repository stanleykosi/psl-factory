"""Reviewed owner messages retain the exact source and original delivery operation."""
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import AppendOnly


class IssueMessageDraft(AppendOnly):
    issue = models.ForeignKey('pmo.Issue',on_delete=models.PROTECT,related_name='message_drafts')
    state = models.ForeignKey('pmo.IssueState',on_delete=models.PROTECT)
    assignment = models.ForeignKey('pmo.IssueTeamAssignment',on_delete=models.PROTECT)
    number = models.PositiveIntegerField()
    previous = models.ForeignKey('self',null=True,on_delete=models.PROTECT)
    previous_release = models.ForeignKey('pmo.IssueMessageDispatch',null=True,on_delete=models.PROTECT,related_name='+')
    operation_key = models.UUIDField(unique=True)
    intent_sha256 = models.CharField(max_length=64)
    kind = models.CharField(max_length=10)
    body = models.TextField()
    source = models.JSONField()
    sha256 = models.CharField(max_length=64)
    evidence = models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    reason = models.CharField(max_length=2000)
    run = models.ForeignKey('agents.AgentRun',null=True,on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=['issue','number'],name='issue_message_draft_version')]


class IssueMessageReview(AppendOnly):
    draft = models.OneToOneField(IssueMessageDraft,on_delete=models.PROTECT,related_name='review')
    configuration = models.ForeignKey('policy.Configuration',on_delete=models.PROTECT)
    role = models.CharField(max_length=30)
    verdict = models.CharField(max_length=10)
    authority = models.JSONField()
    evidence = models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    note = models.CharField(max_length=2000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class IssueMessageDispatch(AppendOnly):
    review = models.OneToOneField(IssueMessageReview,on_delete=models.PROTECT,related_name='dispatch')
    operation = models.UUIDField(default=uuid4,unique=True)
    intent_sha256 = models.CharField(max_length=64)
    configuration = models.ForeignKey('policy.Configuration',on_delete=models.PROTECT)
    role = models.CharField(max_length=30)
    authority = models.JSONField()
    route = models.JSONField()
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    not_before = models.DateTimeField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class IssueMessageAttempt(AppendOnly):
    dispatch = models.OneToOneField(IssueMessageDispatch,on_delete=models.PROTECT,related_name='attempt')
    created_at = models.DateTimeField(auto_now_add=True)


class IssueMessageReceipt(AppendOnly):
    dispatch = models.OneToOneField(IssueMessageDispatch,on_delete=models.PROTECT,related_name='receipt')
    reference = models.CharField(max_length=160)
    delivered = models.BooleanField()
    delivered_at = models.DateTimeField(null=True)
    clock_source = models.CharField(max_length=30)
    evidence = models.ForeignKey('core.Evidence',null=True,on_delete=models.PROTECT)
    source_evidence = models.ForeignKey('core.Evidence',null=True,on_delete=models.PROTECT,related_name='+')
    source_sha256 = models.CharField(max_length=64,blank=True,default='')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class IssueMessageCancellation(AppendOnly):
    dispatch = models.OneToOneField(IssueMessageDispatch,on_delete=models.PROTECT,related_name='cancellation')
    reason = models.CharField(max_length=2000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class SyntheticIssueMessage(AppendOnly):
    dispatch = models.OneToOneField(IssueMessageDispatch,on_delete=models.PROTECT,related_name='sample_message')
    reference = models.CharField(max_length=160)
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    delivered = models.BooleanField(default=True)
    delivered_at = models.DateTimeField(null=True)
    observed_at = models.DateTimeField(default=timezone.now)


class IssueMessageCursor(models.Model):
    name = models.CharField(max_length=60,unique=True)
    last_dispatch_id = models.PositiveBigIntegerField(default=0)
