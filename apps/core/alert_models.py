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
