from django.conf import settings
from django.db import models

from apps.core.models import AppendOnly


class StaffInvitation(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    username = models.CharField(max_length=150)
    name = models.CharField(max_length=150)
    email = models.EmailField()
    actions = models.JSONField()
    profile_key = models.CharField(max_length=50,blank=True,default='')
    profile_label = models.CharField(max_length=80,blank=True,default='')
    profile_sha256 = models.CharField(max_length=64,blank=True,default='')
    workspace_profiles = models.JSONField(default=list, blank=True)
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


class StaffAccountChange(AppendOnly):
    """Global session fence and exact affected workspace history; never a role grant."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    kind = models.CharField(max_length=20, choices=[('deactivated','Deactivated'),('reactivated','Reactivated')])
    operation = models.UUIDField(unique=True)
    manifest = models.JSONField()
    reason = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)


class StaffProfileChange(AppendOnly):
    case = models.ForeignKey('core.Case',on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    authority = models.ForeignKey('identity.TenantAuthority',on_delete=models.PROTECT)
    invitation = models.ForeignKey(StaffInvitation,null=True,on_delete=models.PROTECT)
    operation = models.UUIDField(unique=True)
    profile_key = models.CharField(max_length=50)
    profile_label = models.CharField(max_length=80)
    profile_sha256 = models.CharField(max_length=64)
    grant_sha256 = models.CharField(max_length=64)
    grant_audit_head = models.PositiveBigIntegerField(default=0)
    intent_sha256 = models.CharField(max_length=64)
    before_actions = models.JSONField()
    after_actions = models.JSONField()
    reason = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['invitation', 'case'], name='staff_invite_workspace_profile')]
