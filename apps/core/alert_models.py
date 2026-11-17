import uuid

from django.conf import settings
from django.db import models


class AlertRead(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    key = models.CharField(max_length=64)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['actor', 'key'], name='factory_alert_read_once')]


class AlertPreference(models.Model):
    actor = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    email_requested = models.BooleanField(default=False)
    whatsapp_requested = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)


class AccountDelivery(models.Model):
    class State(models.TextChoices):
        QUEUED = 'queued', 'Waiting to send'
        UNCERTAIN = 'uncertain', 'Checking the original send'
        DELIVERED = 'delivered', 'Delivery verified'
        HELD = 'held', 'Delivery on hold'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    purpose = models.CharField(max_length=10, choices=[('alert', 'Alert'), ('recovery', 'Password recovery')])
    channel = models.CharField(max_length=10, choices=[('email', 'Email'), ('whatsapp', 'WhatsApp')])
    source = models.CharField(max_length=64)
    route_pin = models.CharField(max_length=64)
    relay_pin = models.CharField(max_length=64, blank=True)
    state = models.CharField(max_length=10, choices=State.choices, default=State.QUEUED)
    fingerprint = models.CharField(max_length=64, blank=True)
    receipt = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    next_check = models.DateTimeField(db_index=True)
    delivered_at = models.DateTimeField(null=True)
    consumed_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['actor', 'purpose', 'channel', 'source'],
                                               name='factory_account_delivery_once')]
        indexes = [models.Index(fields=['state', 'next_check'], name='factory_account_delivery_due')]


class RecoveryAttempt(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    until = models.DateTimeField(db_index=True)


class SampleAccountInbox(models.Model):
    delivery = models.OneToOneField(AccountDelivery, on_delete=models.PROTECT, primary_key=True)
    fingerprint = models.CharField(max_length=64)
    received_at = models.DateTimeField(auto_now_add=True)
