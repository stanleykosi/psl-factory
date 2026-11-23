from django.conf import settings
from django.db import models

from apps.core.models import AppendOnly


class BidSharingDecision(AppendOnly):
    bid = models.ForeignKey('pmo.RFPCase', on_delete=models.PROTECT, related_name='sharing_decisions')
    public = models.BooleanField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class BidConversationNote(AppendOnly):
    bid = models.ForeignKey('pmo.RFPCase', on_delete=models.PROTECT, related_name='conversation_notes')
    operation = models.UUIDField(unique=True)
    body = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
