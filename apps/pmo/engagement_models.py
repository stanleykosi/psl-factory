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
