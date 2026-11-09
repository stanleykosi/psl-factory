"""Native confirmation receipt, not a second change register or coordinator."""
from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class ChangeIntakeConfirmation(AppendOnly):
    receipt=models.OneToOneField('core.Audit',on_delete=models.PROTECT,related_name='change_confirmation')
    extraction=models.ForeignKey('agents.AgentRun',null=True,on_delete=models.PROTECT)
    version=models.OneToOneField('pmo.ChangeVersion',on_delete=models.PROTECT,related_name='intake_confirmation')
    work=models.OneToOneField('workflows.FactoryWork',null=True,on_delete=models.PROTECT,related_name='change_intake_confirmation')
    payload=models.JSONField()
    sha256=models.CharField(max_length=64)
    authority=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
