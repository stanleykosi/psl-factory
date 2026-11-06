"""Immutable execution recovery decisions, separate from the original work starter."""
from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class FactoryExecutionBinding(AppendOnly):
    work=models.ForeignKey('workflows.FactoryWork',on_delete=models.PROTECT,related_name='execution_bindings')
    previous=models.OneToOneField('self',null=True,on_delete=models.PROTECT,related_name='successor')
    sequence=models.PositiveIntegerField()
    work_revision=models.PositiveIntegerField()
    principal=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    reviewer=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    configuration=models.ForeignKey('policy.Configuration',on_delete=models.PROTECT)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    rule=models.JSONField()
    reason=models.CharField(max_length=2000)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['work','sequence'],name='factory_execution_binding_sequence')]
