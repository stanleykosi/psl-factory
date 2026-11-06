from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class CostingRule(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    reference=models.CharField(max_length=100)
    version=models.PositiveIntegerField()
    payload=models.JSONField()
    sha256=models.CharField(max_length=64)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='p14_rule_version')]

class CostingOracle(AppendOnly):
    rule=models.ForeignKey(CostingRule,on_delete=models.PROTECT)
    reference=models.CharField(max_length=100)
    version=models.PositiveIntegerField()
    payload=models.JSONField()
    sha256=models.CharField(max_length=64)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:constraints=[models.UniqueConstraint(fields=['rule','reference','version'],name='p14_oracle_version')]

class CostingReview(AppendOnly):
    rule=models.ForeignKey(CostingRule,on_delete=models.PROTECT)
    oracle=models.ForeignKey(CostingOracle,null=True,on_delete=models.PROTECT)
    verdict=models.CharField(max_length=20)
    operation_key=models.CharField(max_length=100)
    authority=models.JSONField()
    snapshot=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:constraints=[models.UniqueConstraint(fields=['rule','operation_key'],name='p14_review_intent')]

class CostingRun(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    rule=models.ForeignKey(CostingRule,on_delete=models.PROTECT)
    operation_key=models.CharField(max_length=100)
    snapshot=models.JSONField()
    inputs=models.JSONField()
    result=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:constraints=[models.UniqueConstraint(fields=['case','operation_key'],name='p14_run_intent')]

class CostingBinding(AppendOnly):
    run=models.OneToOneField(CostingRun,on_delete=models.PROTECT)
    costing=models.OneToOneField('core.Evidence',on_delete=models.PROTECT)
    snapshot=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)

class CostingAF13Binding(AppendOnly):
    run=models.ForeignKey(CostingRun,on_delete=models.PROTECT)
    package=models.ForeignKey('documents.ValidationPackage',on_delete=models.PROTECT)
    snapshot=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:constraints=[models.UniqueConstraint(fields=['run','package'],name='p14_af13_binding')]
