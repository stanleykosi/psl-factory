from apps.core.evidence_access import public_evidence,restricted
import uuid
from django.conf import settings
from django.db import models
from .alert_models import AccountDelivery, AlertPreference, AlertRead, RecoveryAttempt, SampleAccountInbox


class Case(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.CharField(max_length=100)
    title = models.CharField(max_length=240)
    kind = models.CharField(max_length=30, choices=[('project', 'PMO project'), ('support', 'BaaS support')])
    synthetic = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)


class AppendOnly(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('History is append-only; create a new version')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('History is append-only')


class Evidence(AppendOnly):
    def __str__(self):
        if restricted(self):return f"#{self.pk} / restricted source evidence / v{self.version}"
        return f"#{self.pk} · {self.kind.replace('_', ' ')} · v{self.version} · {self.source}"

    case = models.ForeignKey(Case, on_delete=models.PROTECT, related_name='evidence')
    kind = models.CharField(max_length=50)
    version = models.PositiveIntegerField()
    body = models.TextField()
    source = models.CharField(max_length=500)
    sha256 = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'kind', 'version'], name='evidence_version')]


class ClientContactRevision(AppendOnly):
    case = models.ForeignKey(Case, on_delete=models.PROTECT)
    purpose = models.CharField(max_length=12, choices=[('project', 'Project'), ('billing', 'Billing')])
    customer = models.CharField(max_length=100, blank=True)
    client_name = models.CharField(max_length=160)
    name = models.CharField(max_length=160)
    email = models.EmailField(blank=True)
    role = models.CharField(max_length=100, blank=True)
    number = models.PositiveIntegerField()
    evidence = models.ForeignKey(Evidence, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'purpose', 'customer', 'number'], name='client_contact_version')]


class ClientProjectPersonRevision(AppendOnly):
    case = models.ForeignKey(Case, on_delete=models.PROTECT)
    person_key = models.UUIDField(default=uuid.uuid4, editable=False)
    number = models.PositiveIntegerField()
    previous = models.OneToOneField('self', null=True, on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    role = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    evidence = models.ForeignKey(Evidence, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'person_key', 'number'], name='client_project_person_version')]


class ClientBillingIdentityRevision(AppendOnly):
    case = models.ForeignKey(Case, on_delete=models.PROTECT)
    coverage = models.ForeignKey('finance.BillingCoverage', on_delete=models.PROTECT)
    customer_ref = models.CharField(max_length=100)
    number = models.PositiveIntegerField()
    previous = models.OneToOneField('self', null=True, on_delete=models.PROTECT)
    legal_name = models.CharField(max_length=160, null=True)
    billing_address = models.CharField(max_length=600, null=True)
    tax_reference = models.CharField(max_length=100, null=True)
    evidence = models.ForeignKey(Evidence, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'customer_ref', 'number'], name='client_billing_identity_version')]


class ClientWorkspaceLink(AppendOnly):
    case = models.ForeignKey(Case, on_delete=models.PROTECT)
    coverage = models.ForeignKey('finance.BillingCoverage', null=True, on_delete=models.PROTECT)
    number = models.PositiveIntegerField()
    previous = models.OneToOneField('self', null=True, on_delete=models.PROTECT)
    tenant = models.CharField(max_length=100)
    group_key = models.CharField(max_length=64, blank=True, db_index=True)
    client_label = models.CharField(max_length=160, blank=True)
    evidence = models.OneToOneField(Evidence, on_delete=models.PROTECT)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'number'], name='client_workspace_link_version')]


class Audit(AppendOnly):
    case = models.ForeignKey(Case, on_delete=models.PROTECT, related_name='audit')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=100)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
