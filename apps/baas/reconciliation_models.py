from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class ReconciliationBatch(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    reference=models.CharField(max_length=100)
    version=models.PositiveIntegerField()
    kind=models.CharField(max_length=20)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    payload=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='recon_batch_revision')]
    def __str__(self):return f'{self.reference} v{self.version} / {self.kind} / #{self.pk}'

class ReconciliationAttestation(AppendOnly):
    batch=models.ForeignKey(ReconciliationBatch,on_delete=models.PROTECT)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    authority=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)

class ReconciliationRun(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    selections=models.JSONField()
    manifest=models.JSONField()
    result=models.JSONField()
    sha256=models.CharField(max_length=64)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):return f'Reconciliation #{self.pk} / {self.result.get("status","unknown")}'

class CorrectiveRequest(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    run=models.ForeignKey(ReconciliationRun,on_delete=models.PROTECT)
    reference=models.CharField(max_length=100)
    version=models.PositiveIntegerField()
    operation_key=models.CharField(max_length=100)
    payload=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    reason=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='corrective_request_revision')]
    def __str__(self):return f'{self.reference} v{self.version} / #{self.pk}'

class CorrectiveDecision(AppendOnly):
    request=models.ForeignKey(CorrectiveRequest,on_delete=models.PROTECT)
    role=models.CharField(max_length=50)
    verdict=models.CharField(max_length=10)
    snapshot=models.JSONField()
    authority=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    reason=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)

class CorrectiveJob(models.Model):
    request=models.ForeignKey(CorrectiveRequest,on_delete=models.PROTECT)
    generation=models.PositiveIntegerField()
    intent=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    tenant=models.CharField(max_length=100)
    operation_key=models.CharField(max_length=100)
    subject_key=models.CharField(max_length=64)
    status=models.CharField(max_length=20,default='pending')
    fence=models.PositiveIntegerField(default=0)
    attempts=models.PositiveIntegerField(default=0)
    lease_until=models.DateTimeField(null=True)
    error=models.CharField(max_length=400,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['request','generation'],name='corrective_job_generation'),
            models.UniqueConstraint(fields=['tenant','operation_key'],condition=models.Q(status__in=['pending','leased','unknown','held','confirmed']),name='corrective_job_active_operation'),
            models.UniqueConstraint(fields=['tenant','subject_key'],condition=models.Q(status__in=['pending','leased','unknown','held','confirmed']),name='corrective_job_active_subject')]
    def __str__(self):return f'Engineering handoff #{self.pk} / {self.status}'

class CorrectiveDelivery(AppendOnly):
    def __str__(self):return f'Engineering receipt #{self.pk} / {self.operation_key}'
    request=models.OneToOneField(CorrectiveRequest,on_delete=models.PROTECT)
    job=models.OneToOneField(CorrectiveJob,on_delete=models.PROTECT)
    tenant=models.CharField(max_length=100)
    operation_key=models.CharField(max_length=100)
    subject_key=models.CharField(max_length=64)
    recipient=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    payload=models.JSONField()
    sha256=models.CharField(max_length=64)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['tenant','operation_key'],name='corrective_delivery_operation'),models.UniqueConstraint(fields=['tenant','subject_key'],name='corrective_delivery_subject')]

class EngineeringOutcome(AppendOnly):
    def __str__(self):return f'Engineering outcome #{self.pk} / {self.payload.get("status","unknown")}'
    delivery=models.ForeignKey(CorrectiveDelivery,on_delete=models.PROTECT)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    payload=models.JSONField()
    authority=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)

class OutcomeVerification(AppendOnly):
    delivery=models.OneToOneField(CorrectiveDelivery,on_delete=models.PROTECT)
    outcome=models.OneToOneField(EngineeringOutcome,on_delete=models.PROTECT)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    authority=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
