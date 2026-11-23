import uuid

from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class AssistantConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    persona = models.CharField(max_length=12)
    scope = models.CharField(max_length=12, choices=[('project', 'Project'), ('department', 'Department')],
                             default='project')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['actor', '-updated_at'], name='assistant_owner_activity')]


class AssistantTurn(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(AssistantConversation, related_name='turns', on_delete=models.PROTECT)
    question = models.TextField(max_length=4000)
    focus = models.CharField(max_length=64, blank=True)
    selected_sources = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=12, default='queued', db_index=True)
    answer = models.TextField(blank=True)
    sources = models.JSONField(default=list)
    context_hash = models.CharField(max_length=64, blank=True)
    next_work = models.CharField(max_length=80, blank=True)
    started_work = models.ForeignKey('workflows.FactoryWork', null=True, on_delete=models.PROTECT)
    started_draft = models.ForeignKey('AssistantDraftVersion', null=True, related_name='+', on_delete=models.PROTECT)
    transferred_to = models.ForeignKey(AssistantConversation, null=True, related_name='+', on_delete=models.PROTECT)
    started_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AssistantDraftVersion(AppendOnly):
    turn = models.ForeignKey(AssistantTurn, on_delete=models.PROTECT, related_name='draft_versions')
    number = models.PositiveIntegerField()
    case_revision = models.PositiveIntegerField()
    payload = models.JSONField()
    saved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['turn', 'number'], name='assistant_draft_version')]
