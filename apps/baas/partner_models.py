from django.db import models
from django.conf import settings
from apps.core.models import AppendOnly

class PartnerRecord(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    reference=models.CharField(max_length=100)
    kind=models.CharField(max_length=20)
    version=models.PositiveIntegerField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    payload=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='partner_record_version')]
    def __str__(self):return f'{self.reference} v{self.version} / {self.kind} / #{self.pk}'

class PartnerDecision(AppendOnly):
    record=models.ForeignKey(PartnerRecord,on_delete=models.PROTECT)
    purpose=models.CharField(max_length=40)
    verdict=models.CharField(max_length=40)
    role=models.CharField(max_length=100)
    snapshot=models.JSONField()
    authority=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    reason=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)

class OnboardingEvent(AppendOnly):
    record=models.ForeignKey(PartnerRecord,on_delete=models.PROTECT)
    previous=models.OneToOneField('self',null=True,on_delete=models.PROTECT)
    sequence=models.PositiveIntegerField()
    operation=models.CharField(max_length=20)
    stage=models.CharField(max_length=100)
    occurred_at=models.DateTimeField()
    role=models.CharField(max_length=100)
    policy=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['record','sequence'],name='onboarding_event_sequence')]

class PartnerReport(AppendOnly):
    record=models.ForeignKey(PartnerRecord,on_delete=models.PROTECT)
    snapshot=models.JSONField()
    result=models.JSONField()
    sha256=models.CharField(max_length=64)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):return f'Activity report #{self.pk} / {self.result.get("status")}'

class PartnerReportReview(AppendOnly):
    report=models.ForeignKey(PartnerReport,on_delete=models.PROTECT)
    verdict=models.CharField(max_length=20)
    role=models.CharField(max_length=100)
    snapshot=models.JSONField()
    authority=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)

class PartnerFollowup(AppendOnly):
    record=models.ForeignKey(PartnerRecord,on_delete=models.PROTECT)
    source_key=models.CharField(max_length=100)
    snapshot=models.JSONField()
    action=models.OneToOneField('pmo.ActionItem',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['record','source_key'],name='partner_followup_source')]

class PartnerFinanceJob(models.Model):
    report=models.ForeignKey(PartnerReport,on_delete=models.PROTECT)
    generation=models.PositiveIntegerField(default=1)
    intent=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    status=models.CharField(max_length=20,default='pending')
    fence=models.PositiveIntegerField(default=0)
    attempts=models.PositiveIntegerField(default=0)
    lease_until=models.DateTimeField(null=True)
    error=models.CharField(max_length=400,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['report','generation'],name='partner_finance_generation')]
    def __str__(self):return f'Finance handoff #{self.pk} / {self.status}'

class PartnerFinanceReceipt(AppendOnly):
    def __str__(self):return f'Finance activity receipt #{self.pk} / report #{self.report_id}'
    report=models.OneToOneField(PartnerReport,on_delete=models.PROTECT)
    job=models.OneToOneField(PartnerFinanceJob,on_delete=models.PROTECT)
    recipient=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    payload=models.JSONField()
    sha256=models.CharField(max_length=64)
    created_at=models.DateTimeField(auto_now_add=True)

class PartnerBillingImport(AppendOnly):
    receipt=models.OneToOneField(PartnerFinanceReceipt,on_delete=models.PROTECT)
    usage=models.OneToOneField('finance.BillingUsage',on_delete=models.PROTECT)
    policy=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)

class PartnerMeterClaim(AppendOnly):
    identity=models.CharField(max_length=64,unique=True)
    receipt=models.ForeignKey(PartnerFinanceReceipt,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
