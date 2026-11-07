"""Append-only human evidence of separate SOW and PRD signatures, never e-signing."""
from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class CommercialSignaturePacket(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    revision = models.ForeignKey('pmo.CommercialRevision', null=True, on_delete=models.PROTECT, related_name='signature_packets')
    predecessor = models.OneToOneField('self', null=True, on_delete=models.PROTECT, related_name='successor')
    sources = models.JSONField()
    signatures = models.JSONField()
    policy = models.ForeignKey('policy.Configuration', null=True, on_delete=models.PROTECT, related_name='+')
    authority = models.ForeignKey('policy.Configuration', on_delete=models.PROTECT, related_name='+')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    note = models.TextField()
    operation_key = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'operation_key'], name='commercial_signature_packet_key')]


class CommercialSignatureUse(AppendOnly):
    packet = models.OneToOneField(CommercialSignaturePacket, on_delete=models.PROTECT)
    adoption = models.OneToOneField('pmo.BaselineAdoption', null=True, on_delete=models.PROTECT, related_name='signature_use')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class CommercialSignatureReaffirmation(AppendOnly):
    use = models.ForeignKey(CommercialSignatureUse, on_delete=models.PROTECT, related_name='reaffirmations')
    packet = models.OneToOneField(CommercialSignaturePacket, on_delete=models.PROTECT)
    previous = models.OneToOneField('self', null=True, on_delete=models.PROTECT, related_name='successor')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class BaselineSignatureExemption(AppendOnly):
    """Explicit owner-backed unsigned internal baseline assurance, never a signature."""
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    sources = models.JSONField()
    approval_refs = models.JSONField()
    scope_evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    policy = models.ForeignKey('policy.Configuration', on_delete=models.PROTECT, related_name='+')
    authority = models.ForeignKey('policy.Configuration', on_delete=models.PROTECT, related_name='+')
    predecessor = models.OneToOneField('self', null=True, on_delete=models.PROTECT, related_name='successor')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    note = models.TextField()
    operation_key = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'operation_key'], name='baseline_signature_exemption_key')]
