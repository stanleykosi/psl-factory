from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class ComplaintSummaryRequest(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    reference=models.CharField(max_length=100)
    version=models.PositiveIntegerField()
    operation_key=models.CharField(max_length=100)
    payload=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='complaint_request_version'),models.UniqueConstraint(fields=['case','operation_key'],name='complaint_request_operation')]

class ComplaintSummaryVersion(AppendOnly):
    request=models.ForeignKey(ComplaintSummaryRequest,on_delete=models.PROTECT)
    version=models.PositiveIntegerField()
    operation_key=models.CharField(max_length=100)
    pin=models.JSONField()
    result=models.JSONField()
    sha256=models.CharField(max_length=64)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['request','version'],name='complaint_summary_version'),models.UniqueConstraint(fields=['request','operation_key'],name='complaint_summary_operation')]

class ComplaintSummaryReview(AppendOnly):
    version=models.ForeignKey(ComplaintSummaryVersion,on_delete=models.PROTECT,related_name='reviews')
    verdict=models.CharField(max_length=20)
    operation_key=models.CharField(max_length=100)
    pin=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['version','operation_key'],name='complaint_summary_review_key')]
