from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.core.models import AppendOnly


class FinanceBudget(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    reference=models.CharField(max_length=100)
    number=models.PositiveIntegerField()
    cadence=models.CharField(max_length=20)
    accounting_basis=models.CharField(max_length=100,null=True)
    effective_at=models.DateTimeField()
    completeness=models.CharField(max_length=20)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT,related_name='+')
    approval_evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT,related_name='+')
    rows=models.JSONField()
    findings=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','reference','number'],name='finance_budget_version')]
    def __str__(self):return f'{self.reference} v{self.number} / budget #{self.pk}'


class FinancePeriod(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    run=models.OneToOneField('finance.FinanceRun',on_delete=models.PROTECT)
    output_review=models.ForeignKey('finance.FinanceReview',on_delete=models.PROTECT)
    predecessor=models.OneToOneField('self',null=True,on_delete=models.PROTECT,related_name='replacement')
    restatement=models.OneToOneField('finance.FinanceRestatement',null=True,on_delete=models.PROTECT)
    manifest=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):return f"{self.manifest['entity']} / {self.manifest['period']} / sealed #{self.pk}"


class FinanceRestatement(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    original=models.ForeignKey(FinancePeriod,on_delete=models.PROTECT)
    proposed=models.ForeignKey('finance.FinanceRun',on_delete=models.PROTECT)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    rationale=models.TextField()
    impact=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):return f'Restatement #{self.pk} / sealed #{self.original_id} -> run #{self.proposed_id}'


class FinancePerformance(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    request=models.JSONField()
    snapshot=models.JSONField()
    result=models.JSONField()
    operation_key=models.CharField(max_length=64,unique=True)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):return f"Performance #{self.pk} / {self.result['year_key']} / {self.result['cutoff']}"


class FinancePerformanceDecision(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    purpose=models.CharField(max_length=30)
    budget=models.ForeignKey(FinanceBudget,null=True,on_delete=models.PROTECT)
    performance=models.ForeignKey(FinancePerformance,null=True,on_delete=models.PROTECT)
    restatement=models.ForeignKey(FinanceRestatement,null=True,on_delete=models.PROTECT)
    configuration=models.ForeignKey('policy.Configuration',null=True,on_delete=models.PROTECT)
    verdict=models.CharField(max_length=20)
    role=models.CharField(max_length=50)
    authority=models.JSONField()
    snapshot=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    note=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=(
            Q(budget__isnull=False,performance__isnull=True,restatement__isnull=True,configuration__isnull=True)|
            Q(budget__isnull=True,performance__isnull=False,restatement__isnull=True,configuration__isnull=True)|
            Q(budget__isnull=True,performance__isnull=True,restatement__isnull=False,configuration__isnull=True)|
            Q(budget__isnull=True,performance__isnull=True,restatement__isnull=True,configuration__isnull=False)),name='finance_performance_one_subject')]


class FinancePerformanceBinding(AppendOnly):
    version=models.OneToOneField('documents.Version',on_delete=models.PROTECT)
    run=models.ForeignKey(FinancePerformance,on_delete=models.PROTECT)
    snapshot=models.JSONField()
