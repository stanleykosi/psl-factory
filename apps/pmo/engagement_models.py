from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class EngagementRecord(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    kind=models.CharField(max_length=20)
    operation_key=models.CharField(max_length=100)
    data=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','operation_key'],name='engagement_operation_key')]

class ProjectIdentifier(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    tenant=models.CharField(max_length=100)
    namespace=models.CharField(max_length=100)
    value=models.CharField(max_length=120)
    normalized=models.CharField(max_length=120)
    rules=models.JSONField()
    record=models.OneToOneField(EngagementRecord,on_delete=models.PROTECT)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['tenant','namespace','normalized'],name='engagement_identifier_identity')]


class EngagementDetails(AppendOnly):
    """Human-attested planning facts; never included in the public identity export."""
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    capture=models.ForeignKey(EngagementRecord,on_delete=models.PROTECT)
    reference=models.CharField(max_length=120)
    plan=models.ForeignKey('core.Evidence',on_delete=models.PROTECT,related_name='+')
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT,related_name='+')
    planned_start=models.DateField(null=True,blank=True)
    contact=models.ForeignKey('core.ClientContactRevision',on_delete=models.PROTECT,null=True,blank=True)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    operation_key=models.CharField(max_length=100)
    schema_version=models.PositiveSmallIntegerField(default=1)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','operation_key'],name='engagement_details_operation')]


class EngagementDetailsBinding(AppendOnly):
    registration=models.OneToOneField(EngagementRecord,on_delete=models.PROTECT)
    details=models.ForeignKey(EngagementDetails,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
