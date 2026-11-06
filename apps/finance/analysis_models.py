from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.core.models import AppendOnly

class FinanceSource(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    batch=models.ForeignKey('finance.FinancialImport',on_delete=models.PROTECT,related_name='contexts')
    entity=models.CharField(max_length=100)
    accounting_basis=models.CharField(max_length=100)
    extracted_at=models.DateTimeField()
    completeness=models.CharField(max_length=20)
    control_total=models.CharField(max_length=64,null=True)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):return f'Source #{self.pk} / import #{self.batch_id} / {self.entity}'

class FinanceAdjustment(AppendOnly):
    source=models.ForeignKey(FinanceSource,on_delete=models.PROTECT)
    reference=models.CharField(max_length=100)
    number=models.PositiveIntegerField()
    kind=models.CharField(max_length=30)
    lines=models.JSONField()
    note=models.TextField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['source','reference','number'],name='finance_adjustment_revision')]

class FinanceRun(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    source=models.ForeignKey(FinanceSource,on_delete=models.PROTECT)
    parent=models.ForeignKey('self',null=True,on_delete=models.PROTECT)
    kind=models.CharField(max_length=20)
    request=models.JSONField()
    snapshot=models.JSONField()
    result=models.JSONField()
    operation_key=models.CharField(max_length=64,unique=True)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):return f'{self.kind.title()} #{self.pk} / source #{self.source_id}'

class FinanceReview(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    purpose=models.CharField(max_length=30)
    source=models.ForeignKey(FinanceSource,null=True,on_delete=models.PROTECT)
    configuration=models.ForeignKey('policy.Configuration',null=True,on_delete=models.PROTECT)
    adjustment=models.ForeignKey(FinanceAdjustment,null=True,on_delete=models.PROTECT)
    run=models.ForeignKey(FinanceRun,null=True,on_delete=models.PROTECT)
    verdict=models.CharField(max_length=20)
    role=models.CharField(max_length=50)
    authority=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    note=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=(Q(source__isnull=False,configuration__isnull=True,adjustment__isnull=True,run__isnull=True)|
            Q(source__isnull=True,configuration__isnull=False,adjustment__isnull=True,run__isnull=True)|Q(source__isnull=True,configuration__isnull=True,adjustment__isnull=False,run__isnull=True)|
            Q(source__isnull=True,configuration__isnull=True,adjustment__isnull=True,run__isnull=False)),name='finance_review_one_subject')]

class FinanceDocumentBinding(AppendOnly):
    version=models.OneToOneField('documents.Version',on_delete=models.PROTECT)
    run=models.ForeignKey(FinanceRun,on_delete=models.PROTECT)
    snapshot=models.JSONField()
