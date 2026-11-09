from django.db import models
from django.conf import settings
from apps.core.models import AppendOnly

class FinanceStatementInput(AppendOnly):
    statement=models.ForeignKey('finance.FinanceRun',on_delete=models.PROTECT,related_name='statement_inputs')
    source_run=models.ForeignKey('finance.FinanceRun',on_delete=models.PROTECT,related_name='+')
    source_review=models.ForeignKey('finance.FinanceReview',on_delete=models.PROTECT)
    destination=models.CharField(max_length=100)
    metric=models.CharField(max_length=100)
    contract=models.ForeignKey('policy.Configuration',on_delete=models.PROTECT)
    declaration=models.JSONField()
    class Meta:
        constraints=[models.UniqueConstraint(fields=['statement','destination'],name='finance_statement_destination')]


class FinanceStatementPPEInput(AppendOnly):
    statement=models.ForeignKey('finance.FinanceRun',on_delete=models.PROTECT,related_name='statement_ppe_inputs')
    schedule=models.ForeignKey('finance.ScheduleWork',on_delete=models.PROTECT,related_name='+')
    schedule_review=models.ForeignKey('finance.ScheduleReview',on_delete=models.PROTECT,related_name='+')
    destination=models.CharField(max_length=100)
    metric=models.CharField(max_length=100)
    contract=models.ForeignKey('policy.Configuration',on_delete=models.PROTECT,related_name='+')
    declaration=models.JSONField()
    class Meta:
        constraints=[models.UniqueConstraint(fields=['statement','destination'],name='finance_statement_ppe_destination')]


class FinanceStatementPPEProjection(AppendOnly):
    run=models.ForeignKey('finance.FinanceRun',on_delete=models.PROTECT,related_name='ppe_projections')
    evidence=models.OneToOneField('core.Evidence',on_delete=models.PROTECT,related_name='ppe_statement_projection')
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    snapshot=models.JSONField()
    projection=models.JSONField()
    payload_hash=models.CharField(max_length=64)
    created_at=models.DateTimeField(auto_now_add=True)
