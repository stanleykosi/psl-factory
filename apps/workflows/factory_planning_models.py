from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class FactoryPlanningReceipt(AppendOnly):
    attempt=models.OneToOneField('workflows.FactoryAttempt',on_delete=models.PROTECT,related_name='planning_receipt')
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    valid=models.BooleanField()
    result=models.JSONField()
    output_sha256=models.CharField(max_length=64)
    binding=models.JSONField()
    created_at=models.DateTimeField(auto_now_add=True)


class FactoryPlanningRecovery(AppendOnly):
    attempt=models.ForeignKey('workflows.FactoryAttempt',on_delete=models.PROTECT)
    sequence=models.PositiveIntegerField()
    contract=models.ForeignKey('workflows.IntegrationContract',on_delete=models.PROTECT)
    reviewer=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    configuration=models.ForeignKey('policy.Configuration',on_delete=models.PROTECT)
    authority=models.JSONField()
    binding=models.JSONField()
    work_revision=models.PositiveIntegerField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    reason=models.CharField(max_length=2000)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['attempt','sequence'],name='factory_planning_recovery_sequence')]


class FactoryPlanningReceiptUse(AppendOnly):
    receipt=models.OneToOneField(FactoryPlanningReceipt,on_delete=models.PROTECT)
    recovery=models.ForeignKey(FactoryPlanningRecovery,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
