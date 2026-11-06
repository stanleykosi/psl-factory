from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class InvoiceCorrection(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    issue=models.ForeignKey('finance.InvoiceIssue',on_delete=models.PROTECT)
    reference=models.CharField(max_length=100)
    version=models.PositiveIntegerField()
    kind=models.CharField(max_length=10)
    amount=models.DecimalField(max_digits=32,decimal_places=8,null=True)
    payload=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT,related_name='+')
    allocation_evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT,null=True,related_name='+')
    reason=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='invoice_correction_document_version'),models.CheckConstraint(condition=models.Q(amount__gte=0)|models.Q(amount__isnull=True),name='invoice_correction_nonnegative')]
    def __str__(self):return f'{self.kind} {self.reference} v{self.version} / #{self.pk}'

class CashSuccessor(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    parent=models.ForeignKey('finance.CashVerification',on_delete=models.PROTECT)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT,related_name='+')
    verification_evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT,related_name='+')
    legal_evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT,related_name='+')
    payload=models.JSONField()
    reason=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):return f'Cash successor #{self.pk} / parent lot {self.parent_id}'

class FinancialCorrectionReview(AppendOnly):
    correction=models.ForeignKey(InvoiceCorrection,on_delete=models.PROTECT,null=True)
    successor=models.ForeignKey(CashSuccessor,on_delete=models.PROTECT,null=True)
    snapshot=models.JSONField()
    role=models.CharField(max_length=50)
    verdict=models.CharField(max_length=20)
    authority=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    note=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(correction__isnull=False,successor__isnull=True)|models.Q(correction__isnull=True,successor__isnull=False),name='financial_review_exact_subject')]

class InvoiceCorrectionAcceptance(AppendOnly):
    correction=models.OneToOneField(InvoiceCorrection,on_delete=models.PROTECT)
    job=models.OneToOneField('finance.InvoiceJob',on_delete=models.PROTECT)
    payload=models.JSONField()
    sha256=models.CharField(max_length=64)
    created_at=models.DateTimeField(auto_now_add=True)

class InvoiceCorrectionDelivery(AppendOnly):
    correction=models.OneToOneField(InvoiceCorrection,on_delete=models.PROTECT)
    job=models.OneToOneField('finance.InvoiceJob',on_delete=models.PROTECT)
    recipient=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    payload=models.JSONField()
    sha256=models.CharField(max_length=64)
    created_at=models.DateTimeField(auto_now_add=True)

class CashSuccessorAcceptance(AppendOnly):
    request=models.OneToOneField(CashSuccessor,on_delete=models.PROTECT)
    parent=models.OneToOneField('finance.CashVerification',on_delete=models.PROTECT,related_name='accepted_successor')
    lot=models.OneToOneField('finance.CashVerification',on_delete=models.PROTECT,related_name='successor_acceptance')
    review=models.ForeignKey(FinancialCorrectionReview,on_delete=models.PROTECT)
    authority=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
