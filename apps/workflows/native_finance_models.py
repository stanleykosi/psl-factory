from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class NativeFinanceMapping(AppendOnly):
    plan=models.ForeignKey('workflows.ReconstitutionPlan',on_delete=models.PROTECT)
    reference=models.CharField(max_length=100)
    version=models.PositiveIntegerField()
    provider_ref=models.CharField(max_length=100)
    effect_key=models.CharField(max_length=64)
    payload=models.JSONField()
    sha256=models.CharField(max_length=64)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['plan','reference','version'],name='native_finance_mapping_version')]
    def __str__(self):return f'#{self.pk} {self.reference} v{self.version}'

class NativeFinanceObservation(AppendOnly):
    mapping=models.ForeignKey(NativeFinanceMapping,on_delete=models.PROTECT)
    operation_key=models.CharField(max_length=100)
    result=models.JSONField()
    pin=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['mapping','operation_key'],name='native_finance_observation_intent')]

class NativeFinancePacket(AppendOnly):
    mapping=models.ForeignKey(NativeFinanceMapping,on_delete=models.PROTECT)
    observation=models.ForeignKey(NativeFinanceObservation,on_delete=models.PROTECT)
    destination=models.ForeignKey('workflows.DomainObservation',on_delete=models.PROTECT)
    reference=models.CharField(max_length=100)
    version=models.PositiveIntegerField()
    payload=models.JSONField()
    sha256=models.CharField(max_length=64)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['mapping','reference','version'],name='native_finance_packet_version')]
    def __str__(self):return f'#{self.pk} {self.reference} v{self.version}'

class NativeFinanceReview(AppendOnly):
    mapping=models.ForeignKey(NativeFinanceMapping,on_delete=models.PROTECT)
    observation=models.ForeignKey(NativeFinanceObservation,null=True,on_delete=models.PROTECT)
    packet=models.ForeignKey(NativeFinancePacket,null=True,on_delete=models.PROTECT)
    operation_key=models.CharField(max_length=100)
    verdict=models.CharField(max_length=12)
    pin=models.JSONField()
    rationale=models.CharField(max_length=1000)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['mapping','operation_key'],name='native_finance_review_intent'),models.CheckConstraint(condition=models.Q(observation__isnull=True)|models.Q(packet__isnull=True),name='native_finance_review_one_subject')]

class NativeFinancePublicationJob(models.Model):
    packet=models.ForeignKey(NativeFinancePacket,on_delete=models.PROTECT)
    operation_key=models.CharField(max_length=64,unique=True)
    intent=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    status=models.CharField(max_length=12,default='pending')
    attempts=models.PositiveIntegerField(default=0)
    fence=models.PositiveIntegerField(default=0)
    lease_until=models.DateTimeField(null=True)
    receipt=models.JSONField(null=True)
    error=models.CharField(max_length=100,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
