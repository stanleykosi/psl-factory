from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class FinanceHandoff(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 reference=models.CharField(max_length=100)
 version=models.PositiveIntegerField()
 parent=models.OneToOneField('self',null=True,on_delete=models.PROTECT)
 draft=models.ForeignKey('finance.LedgerAgentDraft',on_delete=models.PROTECT)
 package=models.ForeignKey('documents.ValidationPackage',on_delete=models.PROTECT,related_name='finance_handoffs')
 policy=models.ForeignKey('policy.Configuration',on_delete=models.PROTECT)
 recipient=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
 acceptor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
 snapshot=models.JSONField()
 sha256=models.CharField(max_length=64)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='finance_handoff_version')]

class FinanceHandoffDecision(AppendOnly):
 handoff=models.ForeignKey(FinanceHandoff,on_delete=models.PROTECT,related_name='decisions')
 operation_key=models.CharField(max_length=100)
 phase=models.CharField(max_length=12)
 verdict=models.CharField(max_length=12)
 reason=models.TextField()
 snapshot=models.JSONField()
 authority=models.JSONField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['handoff','operation_key'],name='finance_handoff_decision_intent'),models.CheckConstraint(condition=models.Q(phase__in=['receive','validate','accept']),name='finance_handoff_phase'),models.CheckConstraint(condition=models.Q(verdict__in=['confirm','return','withdraw']),name='finance_handoff_verdict')]


class AcceptedFinanceDocument(AppendOnly):
    version = models.OneToOneField('documents.Version',on_delete=models.PROTECT,related_name='accepted_finance_binding')
    handoff = models.ForeignKey(FinanceHandoff,on_delete=models.PROTECT)
    policy = models.ForeignKey('policy.Configuration',on_delete=models.PROTECT)
    snapshot = models.JSONField()
    sha256 = models.CharField(max_length=64)


class FinancePublicationReadiness(AppendOnly):
    contract = models.OneToOneField('workflows.IntegrationContract',on_delete=models.PROTECT,related_name='finance_publication_readiness')
    job = models.ForeignKey('documents.PublicationJob',on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    snapshot = models.JSONField()
    sha256 = models.CharField(max_length=64)


class PrivateReadinessPacket(AppendOnly):
    case = models.ForeignKey('core.Case',on_delete=models.PROTECT)
    reference = models.CharField(max_length=100)
    version = models.PositiveIntegerField()
    parent = models.OneToOneField('self',null=True,on_delete=models.PROTECT)
    package = models.OneToOneField('documents.ValidationPackage',on_delete=models.PROTECT,related_name='private_readiness_packet')
    assessment = models.ForeignKey('workflows.IntegrationAssessment',on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    snapshot = models.JSONField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['case','reference','version'],name='private_readiness_packet_version')]
