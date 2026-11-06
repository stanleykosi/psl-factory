from django.db import models
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
