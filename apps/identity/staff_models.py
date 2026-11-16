from django.conf import settings
from django.db import models

from apps.core.models import AppendOnly


class StaffInvitation(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    username = models.CharField(max_length=150)
    name = models.CharField(max_length=150)
    email = models.EmailField()
    actions = models.JSONField()
    number = models.PositiveIntegerField()
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    authority = models.ForeignKey('identity.TenantAuthority', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case','username','number'], name='staff_invite_version')]


class StaffAdmission(AppendOnly):
    invitation = models.OneToOneField(StaffInvitation, on_delete=models.PROTECT, related_name='admission')
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class StaffDeparture(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    authority = models.ForeignKey('identity.TenantAuthority', on_delete=models.PROTECT)
    reason = models.CharField(max_length=1000)
    actions = models.JSONField()
    account_disabled = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
