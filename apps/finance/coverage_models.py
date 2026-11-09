"""F31/F45 references, never an alternative customer master or invoice ledger."""
from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly

class CoverageAccess(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    reference = models.CharField(max_length=100)
    principal = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    permissions = models.JSONField()
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

class CoverageSource(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    reference = models.CharField(max_length=100)
    version = models.PositiveIntegerField()
    kind = models.CharField(max_length=20)
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['case','reference','version'], name='coverage_source_version')]
    def __str__(self): return f'Source #{self.pk} / v{self.version}'

class CoverageTerms(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    coverage = models.ForeignKey('finance.BillingCoverage', on_delete=models.PROTECT)
    register = models.ForeignKey(CoverageSource, on_delete=models.PROTECT, related_name='+')
    contract = models.ForeignKey(CoverageSource, on_delete=models.PROTECT, related_name='+')
    version = models.PositiveIntegerField()
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['coverage','version'], name='coverage_terms_version')]

class CoverageTermsEvent(AppendOnly):
    terms = models.ForeignKey(CoverageTerms, on_delete=models.PROTECT, related_name='events')
    state = models.CharField(max_length=20)
    findings = models.JSONField(default=list)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

class CoverageInvoiceReference(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    source = models.ForeignKey(CoverageSource, on_delete=models.PROTECT)
    native_issue = models.ForeignKey('finance.InvoiceIssue', null=True, on_delete=models.PROTECT)
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

class CoverageAssessment(AppendOnly):
    terms = models.ForeignKey(CoverageTerms, on_delete=models.PROTECT)
    as_of = models.DateField()
    snapshot = models.JSONField()
    result = models.JSONField()
    operation_key = models.CharField(max_length=64, unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

class CoveragePreparationRequest(AppendOnly):
    assessment = models.ForeignKey(CoverageAssessment, on_delete=models.PROTECT)
    obligation_key = models.CharField(max_length=64)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    operation_key = models.CharField(max_length=64, unique=True)
    payload = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["obligation_key"], name="coverage_preparation_obligation")]

class CoveragePreparationReceipt(AppendOnly):
    request = models.OneToOneField(CoveragePreparationRequest, on_delete=models.PROTECT)
    preparation = models.ForeignKey('finance.BillingPreparation', null=True, on_delete=models.PROTECT)
    payload = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class CoveragePreparationRoute(AppendOnly):
    request = models.ForeignKey(CoveragePreparationRequest, on_delete=models.PROTECT, related_name='routes')
    assessment = models.ForeignKey(CoverageAssessment, on_delete=models.PROTECT)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    state = models.CharField(max_length=20)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class CoverageEvidenceScope(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    evidence = models.OneToOneField('core.Evidence', on_delete=models.PROTECT)
    references = models.JSONField()
    purposes = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
