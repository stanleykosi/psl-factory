from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class Invoice(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    preparation=models.ForeignKey('finance.BillingPreparation',on_delete=models.PROTECT)
    obligation_key=models.CharField(max_length=64)
    version=models.PositiveIntegerField()
    reference=models.CharField(max_length=100)
    due_date=models.DateField(null=True)
    amount=models.DecimalField(max_digits=32,decimal_places=8)
    currency=models.CharField(max_length=3)
    amount_basis=models.CharField(max_length=100)
    payload=models.JSONField()
    sha256=models.CharField(max_length=64)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','reference','version'],name='invoice_reference_version'),models.CheckConstraint(condition=models.Q(amount__gt=0),name='invoice_positive_amount')]
    def __str__(self):return f'{self.reference} v{self.version} / #{self.pk}'

class InvoiceReview(AppendOnly):
    invoice=models.ForeignKey(Invoice,on_delete=models.PROTECT)
    verdict=models.CharField(max_length=20)
    role=models.CharField(max_length=50)
    authority=models.JSONField()
    publication_packet=models.JSONField(default=dict)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    note=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)

class InvoiceJob(models.Model):
    def __str__(self):return f'Job #{self.pk} / {self.invoice.reference} / {self.kind} / {self.status}'
    invoice=models.ForeignKey(Invoice,on_delete=models.PROTECT)
    kind=models.CharField(max_length=20)
    generation=models.PositiveIntegerField(default=1)
    intent=models.JSONField()
    operation_key=models.CharField(max_length=100,unique=True)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    status=models.CharField(max_length=20,default='pending')
    fence=models.PositiveIntegerField(default=0)
    attempts=models.PositiveIntegerField(default=0)
    lease_until=models.DateTimeField(null=True)
    error=models.CharField(max_length=400,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['invoice','kind','generation'],name='invoice_effect_generation')]

class InvoiceIssue(AppendOnly):
    def __str__(self):return f'Issued {self.invoice.reference} / #{self.pk}'
    obligation_key=models.CharField(max_length=64,unique=True)
    invoice=models.OneToOneField(Invoice,on_delete=models.PROTECT)
    job=models.OneToOneField(InvoiceJob,on_delete=models.PROTECT)
    operation_key=models.CharField(max_length=100,unique=True)
    payload=models.JSONField()
    sha256=models.CharField(max_length=64)
    created_at=models.DateTimeField(auto_now_add=True)

class InvoiceDelivery(AppendOnly):
    invoice=models.OneToOneField(Invoice,on_delete=models.PROTECT)
    job=models.OneToOneField(InvoiceJob,on_delete=models.PROTECT)
    recipient=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    payload=models.JSONField()
    sha256=models.CharField(max_length=64)
    created_at=models.DateTimeField(auto_now_add=True)

class CashReceipt(AppendOnly):
    tenant=models.CharField(max_length=100)
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    source=models.CharField(max_length=100)
    transaction_ref=models.CharField(max_length=100)
    payload=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['tenant','source','transaction_ref'],name='cash_tenant_transaction_identity')]
    def __str__(self):return f'{self.source} / {self.transaction_ref} / #{self.pk}'

class CashVerification(AppendOnly):
    receipt=models.ForeignKey(CashReceipt,on_delete=models.PROTECT)
    successor=models.OneToOneField('finance.CashSuccessor',on_delete=models.PROTECT,null=True)
    amount=models.DecimalField(max_digits=32,decimal_places=8)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    authority=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(amount__gt=0),name='cash_lot_positive_amount'),models.UniqueConstraint(fields=['receipt'],condition=models.Q(successor__isnull=True),name='one_original_cash_lot')]

    def __str__(self):return f'Cash lot #{self.pk} / {self.receipt.source} / {self.receipt.transaction_ref} / {self.amount}'

class CashAssignment(AppendOnly):
    receipt=models.ForeignKey(CashReceipt,on_delete=models.PROTECT)
    coverage=models.ForeignKey('finance.BillingCoverage',on_delete=models.PROTECT,null=True)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    authority=models.JSONField()
    reason=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)

class CashAllocation(AppendOnly):
    lot=models.ForeignKey(CashVerification,on_delete=models.PROTECT)
    issue=models.ForeignKey(InvoiceIssue,on_delete=models.PROTECT)
    amount=models.DecimalField(max_digits=32,decimal_places=8)
    operation_key=models.CharField(max_length=100)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    authority=models.JSONField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['lot','operation_key'],name='cash_allocation_semantic_key'),models.CheckConstraint(condition=models.Q(amount__gt=0),name='allocation_positive_amount')]

    def __str__(self):return f'Allocation #{self.pk} / lot {self.lot_id} / invoice {self.issue.invoice.reference} / {self.amount}'

class CashReversal(AppendOnly):
    lot=models.OneToOneField(CashVerification,on_delete=models.PROTECT,null=True)
    allocation=models.OneToOneField(CashAllocation,on_delete=models.PROTECT,null=True)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    authority=models.JSONField()
    reason=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=(models.Q(lot__isnull=False,allocation__isnull=True)|models.Q(lot__isnull=True,allocation__isnull=False)),name='reversal_exactly_one_subject')]

class ReceivableSnapshot(AppendOnly):
    def __str__(self):return f'Receivables #{self.pk} / {self.as_of}'
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    as_of=models.DateField()
    manifest=models.JSONField()
    result=models.JSONField()
    sha256=models.CharField(max_length=64)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
