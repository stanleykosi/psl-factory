from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class EvidenceProjection(AppendOnly):
 def __str__(self):return f'Projection #{self.pk} / {self.process_id} / v{self.version}'
 case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
 evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
 process_id=models.CharField(max_length=10)
 purpose=models.CharField(max_length=100)
 version=models.PositiveIntegerField()
 payload=models.JSONField()
 sha256=models.CharField(max_length=64)
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['case','evidence','process_id','purpose','version'],name='agent_projection_version')]

class EvidenceProjectionReview(AppendOnly):
 projection=models.ForeignKey(EvidenceProjection,on_delete=models.PROTECT)
 verdict=models.CharField(max_length=12)
 policy=models.ForeignKey('policy.Configuration',on_delete=models.PROTECT)
 authority=models.JSONField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)

class EvidenceExtraction(models.Model):
 projection=models.ForeignKey(EvidenceProjection,on_delete=models.PROTECT)
 intent_key=models.CharField(max_length=100)
 operation_key=models.CharField(max_length=64,unique=True)
 intent=models.JSONField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 status=models.CharField(max_length=20,default='pending')
 attempts=models.PositiveIntegerField(default=0)
 fence=models.PositiveIntegerField(default=0)
 lease_until=models.DateTimeField(null=True)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta:constraints=[models.UniqueConstraint(fields=['projection','intent_key'],name='agent_extraction_intent')]

class EvidenceExtractionReceipt(AppendOnly):
 def __str__(self):return f'Private receipt #{self.pk} / job #{self.job_id}'
 job=models.OneToOneField(EvidenceExtraction,on_delete=models.PROTECT)
 valid=models.BooleanField()
 result=models.JSONField()
 output_sha256=models.CharField(max_length=64)
 created_at=models.DateTimeField(auto_now_add=True)

class EvidenceExtractionReview(AppendOnly):
 receipt=models.ForeignKey(EvidenceExtractionReceipt,on_delete=models.PROTECT)
 verdict=models.CharField(max_length=12)
 result=models.JSONField()
 authority=models.JSONField()
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
 created_at=models.DateTimeField(auto_now_add=True)
