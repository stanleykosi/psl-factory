from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly
class ApprovalRequest(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 candidate=models.ForeignKey('pmo.DeliveryCandidate',on_delete=models.PROTECT)
 reference=models.CharField(max_length=100)
 version=models.PositiveIntegerField()
 kind=models.CharField(max_length=100)
 gate_kind=models.CharField(max_length=40,null=True)
 subject=models.JSONField()
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='approval_request_version')]
class ApprovalContractReview(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 kind=models.CharField(max_length=100)
 verdict=models.CharField(max_length=20)
 snapshot=models.JSONField()
 authority=models.JSONField()
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
class ApprovalRouteJob(models.Model):
 request=models.ForeignKey(ApprovalRequest,on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 generation=models.PositiveIntegerField()
 purpose=models.CharField(max_length=20)
 operation_key=models.CharField(max_length=64,unique=True)
 intent=models.JSONField()
 status=models.CharField(max_length=20,default='pending')
 attempts=models.PositiveIntegerField(default=0)
 fence=models.PositiveIntegerField(default=0)
 lease_until=models.DateTimeField(null=True)
 error=models.CharField(max_length=400,blank=True)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['request','generation'],name='approval_route_generation')]
class ApprovalRouteReceipt(AppendOnly):
 job=models.OneToOneField(ApprovalRouteJob,on_delete=models.PROTECT)
 recipient=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 operation_key=models.CharField(max_length=64,unique=True)
 payload=models.JSONField()
 created_at=models.DateTimeField(auto_now_add=True)
class ApprovalSourceReceipt(AppendOnly):
 request=models.ForeignKey(ApprovalRequest,on_delete=models.PROTECT,related_name='source_receipts')
 tenant=models.CharField(max_length=100)
 system=models.CharField(max_length=100)
 external_ref=models.CharField(max_length=100)
 source_version=models.CharField(max_length=100)
 payload=models.JSONField()
 sha256=models.CharField(max_length=64)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['tenant','system','external_ref','source_version'],name='approval_incumbent_source_identity')]
class ApprovalObservation(AppendOnly):
 receipt=models.ForeignKey(ApprovalSourceReceipt,on_delete=models.PROTECT,related_name='observations')
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 payload=models.JSONField()
 snapshot=models.JSONField()
 status=models.CharField(max_length=30)
 created_at=models.DateTimeField(auto_now_add=True)
class ApprovalGateBinding(AppendOnly):
 observation=models.OneToOneField(ApprovalObservation,on_delete=models.PROTECT)
 verification=models.OneToOneField('pmo.GateVerification',on_delete=models.PROTECT,related_name='approval_binding')
 created_at=models.DateTimeField(auto_now_add=True)
