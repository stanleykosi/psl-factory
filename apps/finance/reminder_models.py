from django.conf import settings
from django.db import models

from apps.core.models import AppendOnly


class PaymentReminderDraft(AppendOnly):
    issue = models.ForeignKey('finance.InvoiceIssue', on_delete=models.PROTECT, related_name='reminder_drafts')
    contact = models.ForeignKey('core.ClientContactRevision', on_delete=models.PROTECT)
    number = models.PositiveIntegerField()
    subject = models.CharField(max_length=180)
    body = models.TextField()
    balance = models.JSONField()
    sha256 = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['issue', 'number'], name='reminder_draft_number')]


class PaymentReminderDispatch(AppendOnly):
    draft = models.OneToOneField(PaymentReminderDraft, on_delete=models.PROTECT, related_name='dispatch')
    configuration = models.ForeignKey('policy.Configuration', on_delete=models.PROTECT)
    mode = models.CharField(max_length=20)
    operation_key = models.UUIDField(unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class PaymentReminderReceipt(AppendOnly):
    dispatch = models.OneToOneField(PaymentReminderDispatch, on_delete=models.PROTECT, related_name='receipt')
    reference = models.CharField(max_length=160)
    delivered = models.BooleanField()
    sha256 = models.CharField(max_length=64)
    evidence = models.ForeignKey('core.Evidence', null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class PaymentReminderSetAside(AppendOnly):
    draft = models.OneToOneField(PaymentReminderDraft, on_delete=models.PROTECT, related_name='set_aside')
    reason = models.CharField(max_length=1000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
