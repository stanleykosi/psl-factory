from django.conf import settings
from django.db import models

from apps.core.models import AppendOnly


class GoLiveClientReply(AppendOnly):
    dossier = models.ForeignKey('pmo.DeliveryDossier', on_delete=models.PROTECT, related_name='client_replies')
    receipt = models.ForeignKey('documents.PublicationReceipt', on_delete=models.PROTECT)
    previous = models.OneToOneField('self', null=True, on_delete=models.PROTECT, related_name='successor')
    number = models.PositiveIntegerField()
    outcome = models.CharField(max_length=24)
    party = models.CharField(max_length=160)
    responded_at = models.DateTimeField()
    channel = models.CharField(max_length=30)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    note = models.TextField()
    role = models.CharField(max_length=40)
    authority = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['receipt', 'number'], name='go_live_reply_revision'),
            models.CheckConstraint(condition=models.Q(outcome__in=['changes_requested', 'declined', 'withdrawn']), name='go_live_reply_outcome'),
        ]


class GoLiveReplyIssue(AppendOnly):
    reply = models.OneToOneField(GoLiveClientReply, on_delete=models.PROTECT, related_name='issue_link')
    issue = models.ForeignKey('pmo.Issue', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class GoLiveRemediation(AppendOnly):
    reply = models.ForeignKey(GoLiveClientReply, on_delete=models.PROTECT, related_name='remediation_reviews')
    previous = models.OneToOneField('self', null=True, on_delete=models.PROTECT, related_name='successor')
    number = models.PositiveIntegerField()
    destination = models.ForeignKey('pmo.DeliveryDossier', on_delete=models.PROTECT)
    issue_state = models.ForeignKey('pmo.IssueState', on_delete=models.PROTECT)
    configuration = models.ForeignKey('policy.Configuration', on_delete=models.PROTECT)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    role = models.CharField(max_length=40)
    authority = models.JSONField()
    note = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['reply', 'number'], name='go_live_remediation_revision')]
