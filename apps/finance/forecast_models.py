from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class ForecastScenario(AppendOnly):
    def __str__(self):return f'{self.reference} v{self.number} / #{self.pk}'
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    reference=models.CharField(max_length=100)
    number=models.PositiveIntegerField()
    root=models.ForeignKey('self',null=True,on_delete=models.PROTECT)
    parent=models.ForeignKey('finance.ForecastRun',null=True,on_delete=models.PROTECT)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    payload=models.JSONField()
    reason=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','reference','number'],name='forecast_scenario_revision')]


class ForecastRun(AppendOnly):
    def __str__(self):return f'Forecast #{self.pk} / {self.scenario.reference} / {self.result.get("status","unknown")}'
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    scenario=models.ForeignKey(ForecastScenario,on_delete=models.PROTECT)
    manifest=models.JSONField()
    result=models.JSONField()
    sha256=models.CharField(max_length=64)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)


class ForecastReview(AppendOnly):
    run=models.ForeignKey(ForecastRun,on_delete=models.PROTECT)
    snapshot=models.JSONField()
    role=models.CharField(max_length=50)
    verdict=models.CharField(max_length=10)
    authority=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    reason=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)


class ForecastActual(AppendOnly):
    def __str__(self):return f'Actual #{self.pk} / {self.source} / {self.transaction} / {self.payload.get("amount") or "Unknown"}'
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    source=models.CharField(max_length=100)
    transaction=models.CharField(max_length=100)
    lot=models.OneToOneField('finance.CashVerification',null=True,on_delete=models.PROTECT)
    supersedes=models.OneToOneField('self',null=True,on_delete=models.PROTECT)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    payload=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','source','transaction'],condition=models.Q(supersedes__isnull=True),name='forecast_actual_source_transaction')]


class ForecastActualVerification(AppendOnly):
    actual=models.OneToOneField(ForecastActual,on_delete=models.PROTECT)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    authority=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)


class ForecastMatch(AppendOnly):
    def __str__(self):return f'Match #{self.pk} / {self.item_key} / actual #{self.actual_id} / {self.amount}'
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    root=models.ForeignKey(ForecastScenario,on_delete=models.PROTECT)
    item_key=models.CharField(max_length=100)
    actual=models.ForeignKey(ForecastActual,on_delete=models.PROTECT)
    amount=models.DecimalField(max_digits=32,decimal_places=8)
    operation_key=models.CharField(max_length=100)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    authority=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','operation_key'],name='forecast_match_operation'),models.CheckConstraint(condition=models.Q(amount__gt=0),name='forecast_match_positive')]


class ForecastBinding(AppendOnly):
    version=models.OneToOneField('documents.Version',on_delete=models.PROTECT)
    run=models.ForeignKey(ForecastRun,on_delete=models.PROTECT)
    snapshot=models.JSONField()


class ForecastMatchReversal(AppendOnly):
    match=models.OneToOneField(ForecastMatch,on_delete=models.PROTECT,related_name='reversal')
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    authority=models.JSONField()
    reason=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)


class ForecastPriority(AppendOnly):
    review=models.ForeignKey(ForecastReview,on_delete=models.PROTECT)
    action=models.OneToOneField('pmo.ActionItem',on_delete=models.PROTECT)
    authority=models.JSONField()
