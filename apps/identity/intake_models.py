from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class TenantAuthority(AppendOnly):
    tenant=models.CharField(max_length=100)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    version=models.PositiveIntegerField()
    enabled=models.BooleanField()
    value=models.JSONField()
    expires_at=models.DateTimeField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    reason=models.CharField(max_length=1000)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=['tenant','user','version'],name='tenant_authority_version')]


class CaseIntake(AppendOnly):
    case=models.OneToOneField('core.Case',on_delete=models.PROTECT)
    tenant=models.CharField(max_length=100)
    reference=models.CharField(max_length=100)
    authority=models.ForeignKey(TenantAuthority,on_delete=models.PROTECT)
    payload=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=['tenant','reference'],name='tenant_intake_reference')]


class AccessChange(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    subject=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    action=models.CharField(max_length=100)
    enabled=models.BooleanField()
    authority=models.ForeignKey(TenantAuthority,on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    reason=models.CharField(max_length=1000)
    created_at=models.DateTimeField(auto_now_add=True)
