"""Immutable scope and human decisions for the existing Tola worker."""
from django.conf import settings
from django.db import models

from apps.core.models import AppendOnly


class RFPAnswerSuggestion(AppendOnly):
    turn = models.OneToOneField('agents.AssistantTurn', on_delete=models.PROTECT, related_name='rfp_answer')
    work = models.ForeignKey('workflows.FactoryWork', on_delete=models.PROTECT)
    source_head = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    key = models.CharField(max_length=100)
    row = models.JSONField()
    context = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class RFPAnswerReview(AppendOnly):
    suggestion = models.ForeignKey(RFPAnswerSuggestion, on_delete=models.PROTECT, related_name='reviews')
    predecessor = models.ForeignKey('self', null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    verdict = models.CharField(max_length=12)
    row = models.JSONField()
    note = models.TextField(blank=True, max_length=2000)
    source_head = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
