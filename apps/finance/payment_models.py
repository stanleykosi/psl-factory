from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class PaymentAssessment(AppendOnly):
    case=models.ForeignKey('core.Case',on_delete=models.PROTECT)
    dossier=models.ForeignKey('pmo.DeliveryDossier',on_delete=models.PROTECT)
    coverage=models.ForeignKey('finance.BillingCoverage',on_delete=models.PROTECT)
    manifest=models.JSONField()
    result=models.JSONField()
    sha256=models.CharField(max_length=64)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):return f'Assessment #{self.pk} / {self.result.get("status")}'

class PaymentException(AppendOnly):
    assessment=models.ForeignKey(PaymentAssessment,on_delete=models.PROTECT)
    operation_key=models.CharField(max_length=100)
    reason=models.TextField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    valid_from=models.DateTimeField()
    valid_until=models.DateTimeField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['assessment','operation_key'],name='payment_exception_operation'),models.CheckConstraint(condition=models.Q(valid_until__gt=models.F('valid_from')),name='payment_exception_window')]
    def __str__(self):return f'Exception request #{self.pk}'

class PaymentDecision(AppendOnly):
    request=models.ForeignKey(PaymentException,on_delete=models.PROTECT,related_name='decisions')
    verdict=models.CharField(max_length=20)
    authority=models.JSONField()
    reason=models.TextField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)

class PaymentReleaseReservation(AppendOnly):
    assessment=models.ForeignKey(PaymentAssessment,on_delete=models.PROTECT)
    decision=models.ForeignKey(PaymentDecision,on_delete=models.PROTECT,null=True)
    operation_key=models.CharField(max_length=100,unique=True)
    manifest=models.JSONField()
    sha256=models.CharField(max_length=64)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):return f'Local release control reservation #{self.pk}'
