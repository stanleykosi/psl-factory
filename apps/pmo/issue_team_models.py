"""External issue owners and their actual human recorders retain separate identities."""
from django.conf import settings
from django.db import models

from apps.core.models import AppendOnly


class IssueTeamAssignment(AppendOnly):
    issue = models.ForeignKey('pmo.Issue', on_delete=models.PROTECT, related_name='team_assignments')
    state = models.OneToOneField('pmo.IssueState', on_delete=models.PROTECT)
    number = models.PositiveIntegerField()
    mode = models.CharField(max_length=10, choices=[('team', 'External team'), ('internal', 'Factory account')])
    team_key = models.CharField(max_length=100, blank=True)
    team_label = models.CharField(max_length=100, blank=True)
    recorder = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    recorder_role = models.CharField(max_length=30, blank=True)
    policy = models.ForeignKey('policy.Configuration', null=True, on_delete=models.PROTECT)
    authority = models.JSONField(default=dict)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    reason = models.CharField(max_length=2000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    auto_work = models.ForeignKey('workflows.FactoryWork', null=True, on_delete=models.PROTECT)
    requested_source = models.ForeignKey('core.Evidence', null=True, on_delete=models.PROTECT, related_name='+')
    work_input = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['issue', 'number'], name='issue_team_assignment_version')]


class IssueTeamReply(AppendOnly):
    assignment = models.ForeignKey(IssueTeamAssignment, on_delete=models.PROTECT, related_name='replies')
    state = models.OneToOneField('pmo.IssueState', on_delete=models.PROTECT)
    operation_key = models.UUIDField(unique=True)
    intent_sha256 = models.CharField(max_length=64)
    operation = models.CharField(max_length=20)
    party = models.CharField(max_length=200)
    channel = models.CharField(max_length=30)
    responded_at = models.DateTimeField()
    source_ref = models.CharField(max_length=240)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    proof_sha256 = models.CharField(max_length=64)
    authority = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
