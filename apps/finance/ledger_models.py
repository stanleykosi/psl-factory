from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly
class LedgerLineage(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 predecessor=models.ForeignKey('self',null=True,on_delete=models.PROTECT)
 identity=models.CharField(max_length=64,db_index=True)
 payload=models.JSONField()
 created_at=models.DateTimeField(auto_now_add=True)
class LedgerCheck(AppendOnly):
 lineage=models.ForeignKey(LedgerLineage,on_delete=models.PROTECT,related_name='checks')
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 payload=models.JSONField()
 snapshot=models.JSONField()
 status=models.CharField(max_length=30)
 created_at=models.DateTimeField(auto_now_add=True)
class LedgerDecision(AppendOnly):
 verification=models.ForeignKey(LedgerCheck,on_delete=models.PROTECT,related_name='decisions')
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 verdict=models.CharField(max_length=10)
 authority=models.JSONField()
 created_at=models.DateTimeField(auto_now_add=True)

class LedgerResolution(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 reference=models.CharField(max_length=100)
 version=models.PositiveIntegerField()
 predecessor=models.OneToOneField('self',null=True,on_delete=models.PROTECT)
 selected=models.ForeignKey(LedgerLineage,on_delete=models.PROTECT)
 mode=models.CharField(max_length=30)
 snapshot=models.JSONField()
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 reason=models.CharField(max_length=400)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='ledger_resolution_version')]

class LedgerResolutionMember(AppendOnly):
 resolution=models.ForeignKey(LedgerResolution,on_delete=models.PROTECT,related_name='members')
 lineage=models.ForeignKey(LedgerLineage,on_delete=models.PROTECT)
 verification=models.ForeignKey(LedgerCheck,on_delete=models.PROTECT)
 disposition=models.CharField(max_length=10)
 class Meta:constraints=[models.UniqueConstraint(fields=['resolution','lineage'],name='ledger_resolution_member')]

class LedgerResolutionReview(AppendOnly):
 resolution=models.ForeignKey(LedgerResolution,on_delete=models.PROTECT,related_name='reviews')
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 verdict=models.CharField(max_length=10)
 authority=models.JSONField()
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
