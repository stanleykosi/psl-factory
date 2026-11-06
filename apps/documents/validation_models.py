from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class DiscoverySource(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    reference=models.CharField(max_length=100)
    version=models.PositiveIntegerField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    metadata=models.JSONField()
    sha256=models.CharField(max_length=64)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='discovery_source_version')]
    def __str__(self):return f'{self.reference} v{self.version} / #{self.pk}'

class ValidationExample(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    reference=models.CharField(max_length=100)
    version=models.PositiveIntegerField()
    process_ids=models.JSONField()
    scenario=models.CharField(max_length=20)
    expected=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='validation_example_version')]
    def __str__(self):return f'{self.reference} v{self.version} / {self.scenario} / #{self.pk}'

class ValidationPackage(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    reference=models.CharField(max_length=100)
    version=models.PositiveIntegerField()
    payload=models.JSONField()
    manifest=models.JSONField()
    sha256=models.CharField(max_length=64)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='validation_package_version')]
    def __str__(self):return f'{self.reference} v{self.version} / {self.payload.get("level")} / #{self.pk}'

class ValidationReview(AppendOnly):
    package=models.ForeignKey(ValidationPackage,on_delete=models.PROTECT,related_name='reviews')
    kind=models.CharField(max_length=20)
    verdict=models.CharField(max_length=20)
    operation_key=models.CharField(max_length=100)
    authority=models.JSONField()
    snapshot=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    reason=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['package','operation_key'],name='validation_review_operation')]

class ValidationReplay(AppendOnly):
    package=models.ForeignKey(ValidationPackage,on_delete=models.PROTECT)
    example=models.ForeignKey(ValidationExample,on_delete=models.PROTECT)
    expectation_review=models.ForeignKey(ValidationReview,on_delete=models.PROTECT)
    operation_key=models.CharField(max_length=100)
    actual=models.JSONField()
    provenance=models.JSONField()
    result=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['package','operation_key'],name='validation_replay_operation')]

class ValidationFollowup(AppendOnly):
    package=models.ForeignKey(ValidationPackage,on_delete=models.PROTECT)
    gap_key=models.CharField(max_length=100)
    action=models.OneToOneField('pmo.ActionItem',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['package','gap_key'],name='validation_gap_followup')]
