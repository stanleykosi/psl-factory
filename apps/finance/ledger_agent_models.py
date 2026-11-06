from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly
class LedgerProjection(AppendOnly):
 def __str__(self):return f'Finance projection #{self.pk} / lineage #{self.lineage_id}'
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 intent_key=models.CharField(max_length=100)
 projection=models.OneToOneField('agents.EvidenceProjection',on_delete=models.PROTECT)
 lineage=models.ForeignKey('finance.LedgerLineage',on_delete=models.PROTECT)
 policy=models.ForeignKey('policy.Configuration',on_delete=models.PROTECT)
 snapshot=models.JSONField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['case','intent_key'],name='ledger_projection_intent')]
class LedgerAgentDraft(AppendOnly):
 def __str__(self):return f'Draft #{self.pk} / {self.reference} / v{self.version}'
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 reference=models.CharField(max_length=100)
 version=models.PositiveIntegerField()
 parent=models.OneToOneField('self',null=True,on_delete=models.PROTECT)
 source=models.ForeignKey(LedgerProjection,on_delete=models.PROTECT)
 result_review=models.ForeignKey('agents.EvidenceExtractionReview',on_delete=models.PROTECT)
 owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 body=models.TextField()
 sha256=models.CharField(max_length=64)
 snapshot=models.JSONField()
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='ledger_agent_draft_version')]
class LedgerAgentDraftReview(AppendOnly):
 draft=models.ForeignKey(LedgerAgentDraft,on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 verdict=models.CharField(max_length=12)
 authority=models.JSONField()
 created_at=models.DateTimeField(auto_now_add=True)
