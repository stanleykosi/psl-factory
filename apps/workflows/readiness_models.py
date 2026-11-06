from django.db import models
from django.conf import settings
from apps.core.models import AppendOnly

class IntegrationContract(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 reference=models.CharField(max_length=100)
 version=models.PositiveIntegerField()
 payload=models.JSONField()
 sha256=models.CharField(max_length=64)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='integration_contract_version')]

class IntegrationProbe(models.Model):
 contract=models.ForeignKey(IntegrationContract,on_delete=models.PROTECT)
 operation_key=models.CharField(max_length=64,unique=True)
 intent_key=models.CharField(max_length=100)
 intent=models.JSONField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 status=models.CharField(max_length=20,default='pending')
 attempts=models.PositiveIntegerField(default=0)
 fence=models.PositiveIntegerField(default=0)
 lease_until=models.DateTimeField(null=True)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['contract','intent_key'],name='integration_probe_intent')]

class IntegrationObservation(AppendOnly):
 contract=models.ForeignKey(IntegrationContract,on_delete=models.PROTECT)
 job=models.OneToOneField(IntegrationProbe,null=True,on_delete=models.PROTECT)
 external_key=models.CharField(max_length=100)
 payload=models.JSONField()
 sha256=models.CharField(max_length=64)
 evidence=models.ForeignKey('core.Evidence',null=True,on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['contract','external_key'],name='integration_observation_identity')]

class IntegrationAssessment(AppendOnly):
 contract=models.ForeignKey(IntegrationContract,on_delete=models.PROTECT)
 operation_key=models.CharField(max_length=100)
 snapshot=models.JSONField()
 result=models.JSONField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['contract','operation_key'],name='integration_assessment_intent')]

class IntegrationReview(AppendOnly):
 assessment=models.ForeignKey(IntegrationAssessment,on_delete=models.PROTECT)
 operation_key=models.CharField(max_length=100)
 verdict=models.CharField(max_length=20)
 authority=models.JSONField()
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['assessment','operation_key'],name='integration_review_intent')]

class PrivateProtectionReadiness(AppendOnly):
 contract=models.OneToOneField(IntegrationContract,on_delete=models.PROTECT,related_name='private_protection_readiness')
 job=models.ForeignKey('workflows.RecoveryJob',on_delete=models.PROTECT)
 snapshot=models.JSONField()
 sha256=models.CharField(max_length=64)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)

class AcceptedProtectionReadiness(AppendOnly):
 contract=models.OneToOneField(IntegrationContract,on_delete=models.PROTECT,related_name='accepted_protection_readiness')
 job=models.ForeignKey('workflows.RecoveryJob',on_delete=models.PROTECT)
 snapshot=models.JSONField()
 sha256=models.CharField(max_length=64)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)

class IntegrationSelection(AppendOnly):
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 family=models.CharField(max_length=30)
 version=models.PositiveIntegerField()
 contract=models.ForeignKey(IntegrationContract,on_delete=models.PROTECT)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['case','family','version'],name='integration_selection_version')]

class PrivateFileReadiness(AppendOnly):
 contract=models.OneToOneField(IntegrationContract,on_delete=models.PROTECT,related_name='private_file_readiness')
 job=models.ForeignKey('workflows.RecoveryJob',on_delete=models.PROTECT)
 snapshot=models.JSONField()
 sha256=models.CharField(max_length=64)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
