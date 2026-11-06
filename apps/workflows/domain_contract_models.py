"""Immutable recovery companion contracts; none are activation commands."""
from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class DomainContract(AppendOnly):
    plan = models.ForeignKey('workflows.ReconstitutionPlan',on_delete=models.PROTECT)
    reference = models.CharField(max_length=100)
    version = models.PositiveIntegerField()
    kind = models.CharField(max_length=16)
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    evidence = models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['plan','reference','version'],name='domain_contract_version')]
    def __str__(self):return f'#{self.pk} {self.reference} v{self.version} ({self.kind})'


class DomainObservation(AppendOnly):
    contract = models.ForeignKey(DomainContract,on_delete=models.PROTECT)
    operation_key = models.CharField(max_length=100)
    effect_key = models.CharField(max_length=64,blank=True)
    request = models.JSONField()
    result = models.JSONField()
    pin = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['contract','operation_key'],name='domain_observation_intent')]


class DomainContractReview(AppendOnly):
    contract = models.ForeignKey(DomainContract,on_delete=models.PROTECT)
    observation = models.ForeignKey(DomainObservation,null=True,on_delete=models.PROTECT)
    operation_key = models.CharField(max_length=100)
    verdict = models.CharField(max_length=12)
    pin = models.JSONField()
    rationale = models.CharField(max_length=1000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['contract','operation_key'],name='domain_contract_review_intent')]
