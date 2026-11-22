from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class CostingProposal(AppendOnly):
    base = models.ForeignKey('pmo.CostingRule', on_delete=models.PROTECT)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    reason = models.TextField(max_length=2000)
    operation_key = models.CharField(max_length=100)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=['base', 'operation_key'], name='costing_proposal_intent')]


class CostingProposalDecision(AppendOnly):
    proposal = models.OneToOneField(CostingProposal, on_delete=models.PROTECT, related_name='decision')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    verdict = models.CharField(max_length=12)
    note = models.TextField(max_length=2000)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    authority = models.JSONField()
    rule = models.OneToOneField('pmo.CostingRule', on_delete=models.PROTECT, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
