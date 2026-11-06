from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class BillingCoverage(AppendOnly):
    case = models.ForeignKey('core.Case',on_delete=models.PROTECT)
    reference = models.CharField(max_length=100)
    version = models.PositiveIntegerField()
    customer = models.CharField(max_length=100)
    service = models.CharField(max_length=100)
    contract = models.CharField(max_length=100)
    currency = models.CharField(max_length=3)
    amount_basis = models.CharField(max_length=100)
    from_period = models.CharField(max_length=7)
    to_period = models.CharField(max_length=7)
    completeness = models.CharField(max_length=20)
    evidence = models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='billing_coverage_version')]
    def __str__(self):return f'{self.reference} v{self.version} / {self.customer} / {self.service} / #{self.pk}'

class BillingUsage(AppendOnly):
    coverage = models.ForeignKey(BillingCoverage,on_delete=models.PROTECT)
    evidence = models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    source_sha256 = models.CharField(max_length=64)
    source_context = models.JSONField(null=True)
    rows = models.JSONField()
    findings = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['coverage','source_sha256'],name='billing_usage_content')]
    def __str__(self):return f'Usage #{self.pk} / {self.coverage}'

class BillingPreparation(AppendOnly):
    case = models.ForeignKey('core.Case',on_delete=models.PROTECT)
    coverage = models.ForeignKey(BillingCoverage,on_delete=models.PROTECT)
    usage = models.ForeignKey(BillingUsage,null=True,on_delete=models.PROTECT)
    handoff = models.ForeignKey('finance.Handoff',null=True,on_delete=models.PROTECT)
    kind = models.CharField(max_length=30)
    snapshot = models.JSONField()
    result = models.JSONField()
    operation_key = models.CharField(max_length=64,unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):return f'{self.kind} #{self.pk} / {self.result.get("status")}'
