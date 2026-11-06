from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class EmergencyProfile(AppendOnly):
    def __str__(self):return f'#{self.pk} · {self.version.change.reference} v{self.version.number}'
    version=models.ForeignKey('pmo.ChangeVersion',on_delete=models.PROTECT,related_name='emergency_profiles')
    candidate=models.ForeignKey('pmo.DeliveryCandidate',on_delete=models.PROTECT)
    critical_production=models.BooleanField(null=True)
    p1=models.BooleanField(null=True)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    note=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)


class EmergencyDecision(AppendOnly):
    profile=models.ForeignKey(EmergencyProfile,on_delete=models.PROTECT,related_name='decisions')
    role=models.CharField(max_length=60)
    authority_role=models.CharField(max_length=50)
    verdict=models.CharField(max_length=20)
    policies=models.JSONField()
    authority=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    note=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)


class EmergencyAuthorization(AppendOnly):
    def __str__(self):return f'#{self.pk} · profile #{self.profile_id} · {self.created_at}'
    profile=models.OneToOneField(EmergencyProfile,on_delete=models.PROTECT)
    snapshot=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)


class EmergencyOutcome(AppendOnly):
    def __str__(self):return f'#{self.pk} · {self.profile.version.change.reference} · implemented {self.implemented_at}'
    profile=models.ForeignKey(EmergencyProfile,on_delete=models.PROTECT,related_name='outcomes')
    authorization=models.OneToOneField(EmergencyAuthorization,null=True,on_delete=models.PROTECT)
    implemented_at=models.DateTimeField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    note=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['profile'],name='emergency_outcome_once')]


class EmergencyReview(AppendOnly):
    outcome=models.ForeignKey(EmergencyOutcome,on_delete=models.PROTECT,related_name='reviews')
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    note=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)


class EmergencyRetrospectiveDecision(AppendOnly):
    review=models.ForeignKey(EmergencyReview,on_delete=models.PROTECT,related_name='decisions')
    role=models.CharField(max_length=50)
    verdict=models.CharField(max_length=20)
    authority=models.JSONField()
    timing=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    note=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)


class EmergencyRetrospectiveRecord(AppendOnly):
    outcome=models.OneToOneField(EmergencyOutcome,on_delete=models.PROTECT)
    snapshot=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)


class EmergencyDocumentBinding(AppendOnly):
    version=models.OneToOneField('documents.Version',on_delete=models.PROTECT)
    outcome=models.ForeignKey(EmergencyOutcome,on_delete=models.PROTECT)
    manifest=models.JSONField()


class EmergencyDeadlineSignal(AppendOnly):
    outcome=models.ForeignKey(EmergencyOutcome,on_delete=models.PROTECT)
    kind=models.CharField(max_length=50)
    source_key=models.CharField(max_length=64)
    snapshot=models.JSONField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['outcome','kind','source_key'],name='emergency_signal_once')]


class EmergencyScanCursor(models.Model):
    name=models.CharField(max_length=40,unique=True)
    last_outcome_id=models.BigIntegerField(default=0)
