from django.conf import settings
from django.db import models


class FinanceDocument(models.Model):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    uploader = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    name = models.CharField(max_length=160)
    key = models.CharField(max_length=100, unique=True)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    status = models.CharField(max_length=20, default='queued')
    attempt = models.UUIDField(null=True)
    updated_at = models.DateTimeField(auto_now=True)
    model = models.CharField(max_length=200, blank=True)
    draft = models.JSONField(default=dict)
    message = models.TextField(blank=True)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='+')
    reviewed_at = models.DateTimeField(null=True)
    approved = models.JSONField(default=dict)
    receipt = models.ForeignKey('core.Audit', null=True, on_delete=models.PROTECT)

    @property
    def status_label(self):
        return {'queued': 'Waiting for Chidi', 'reading': 'Chidi is reading', 'held': 'Reading needs attention',
                'review': 'Ready for Finance review', 'returned': 'Returned by Finance', 'approved': 'Approved by Finance'}[self.status]

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'sha256'], name='finance_document_exact_file')]


class ReviewedFinanceFigure(models.Model):
    document = models.ForeignKey(FinanceDocument, on_delete=models.PROTECT, related_name='figures')
    account = models.CharField(max_length=180)
    amount = models.DecimalField(max_digits=26, decimal_places=8)
    currency = models.CharField(max_length=3)
    period = models.CharField(max_length=7)
    citation = models.CharField(max_length=500)
