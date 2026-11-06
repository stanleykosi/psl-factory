"""Native coordination links; domain decisions and effects remain in their native tables."""
from django.conf import settings
from django.db import models
from django.db.models import Q,F
from apps.core.models import AppendOnly


class FactoryWork(models.Model):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    execution_binding=models.ForeignKey('workflows.FactoryExecutionBinding',null=True,on_delete=models.PROTECT,related_name='+')
    key=models.CharField(max_length=100)
    definition=models.CharField(max_length=80,default='pmo-finance/v1')
    request=models.JSONField()
    request_hash=models.CharField(max_length=64)
    business_key=models.CharField(max_length=64)
    status=models.CharField(max_length=32,default='ready')
    finding=models.CharField(max_length=300,blank=True)
    revision=models.PositiveIntegerField(default=1)
    fence=models.PositiveIntegerField(default=0)
    lease_until=models.DateTimeField(null=True)
    cancel_requested=models.BooleanField(default=False)
    policy=models.ForeignKey('policy.Configuration',null=True,on_delete=models.PROTECT)
    budget_limit=models.PositiveIntegerField(default=0)
    budget_used=models.PositiveIntegerField(default=0)
    observation_hash=models.CharField(max_length=64,blank=True)
    plan_revision=models.PositiveIntegerField(default=0)
    preparation=models.ForeignKey('finance.BillingPreparation',null=True,on_delete=models.PROTECT)
    invoice=models.ForeignKey('finance.Invoice',null=True,on_delete=models.PROTECT)
    source_head=models.ForeignKey('core.Evidence',null=True,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    @property
    def execution_actor(self):
        from .factory_execution import execution_actor
        return execution_actor(self)
    @property
    def execution_actor_id(self):return self.execution_actor.pk
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','key'],name='factory_work_identity'),models.UniqueConstraint(fields=['case','definition','business_key'],name='factory_business_identity'),models.CheckConstraint(condition=Q(budget_used__lte=F('budget_limit')),name='factory_shared_budget')]


class FactoryActivity(models.Model):
    work=models.ForeignKey(FactoryWork,on_delete=models.PROTECT,related_name='activities')
    parent=models.ForeignKey('self',null=True,on_delete=models.PROTECT)
    kind=models.CharField(max_length=8)
    key=models.CharField(max_length=64)
    plan_revision=models.PositiveIntegerField()
    status=models.CharField(max_length=24,default='queued')
    class Meta:
        constraints=[models.UniqueConstraint(fields=['work','key'],name='factory_activity_identity')]


class FactoryAttempt(AppendOnly):
    activity=models.ForeignKey(FactoryActivity,on_delete=models.PROTECT,related_name='attempts')
    number=models.PositiveIntegerField()
    phase=models.CharField(max_length=20)
    fence=models.PositiveIntegerField()
    observation=models.JSONField()
    result=models.JSONField(default=dict)
    agent_run=models.ForeignKey('agents.AgentRun',null=True,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['activity','number','phase'],name='factory_attempt_event_identity')]
