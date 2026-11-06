from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class Configuration(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    component = models.CharField(max_length=150)
    revision = models.PositiveIntegerField()
    envelope = models.JSONField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'component', 'revision'], name='policy_version')]


class PolicyState(AppendOnly):
    configuration = models.ForeignKey(Configuration, on_delete=models.PROTECT, related_name='states')
    state = models.CharField(max_length=20)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class RegisteredReference(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    ref = models.CharField(max_length=150)
    schema_ref = models.CharField(max_length=200)
    version = models.PositiveIntegerField(default=1)
    content = models.JSONField()
    sha256 = models.CharField(max_length=64)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'ref', 'version'], name='registered_reference_version')]


class ScopeVersion(AppendOnly):
    configuration = models.OneToOneField(Configuration, on_delete=models.PROTECT, related_name='scope_source')
    kind = models.CharField(max_length=20, choices=[(x, x) for x in ['organization', 'project', 'contract', 'service']])
    ref = models.CharField(max_length=150)
    revision = models.PositiveIntegerField()
    binding_paths = models.JSONField(default=list)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ScopeState(AppendOnly):
    source = models.ForeignKey(ScopeVersion, on_delete=models.PROTECT, related_name='states')
    state = models.CharField(max_length=20, choices=[(x, x) for x in ['draft', 'validated', 'active', 'superseded', 'revoked']])
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ScopeApplication(AppendOnly):
    configuration = models.OneToOneField(Configuration, on_delete=models.PROTECT, related_name='scope_application')
    source = models.ForeignKey(ScopeVersion, on_delete=models.PROTECT, related_name='applications')
    bindings = models.JSONField(default=list)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ImpactAssessment(AppendOnly):
    previous = models.ForeignKey(Configuration, on_delete=models.PROTECT, related_name='impact_predecessors')
    successor = models.ForeignKey(Configuration, on_delete=models.PROTECT, related_name='impact_successors')
    adapters = models.JSONField()
    observation = models.JSONField()
    sha256 = models.CharField(max_length=64)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    reason = models.CharField(max_length=2000)
    operation_key = models.CharField(max_length=64, unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ImpactReview(AppendOnly):
    assessment = models.OneToOneField(ImpactAssessment, on_delete=models.PROTECT, related_name='review')
    verdict = models.CharField(max_length=20, choices=[(x,x) for x in ['accept','reject','defer']])
    observed_sha256 = models.CharField(max_length=64)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    reason = models.CharField(max_length=2000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class PilotContract(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'version'], name='pilot_contract_version')]


class PilotObservation(AppendOnly):
    contract = models.ForeignKey(PilotContract, on_delete=models.PROTECT)
    snapshot = models.JSONField()
    sha256 = models.CharField(max_length=64)
    operation_key = models.CharField(max_length=64, unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class PilotBinding(AppendOnly):
    contract = models.OneToOneField(PilotContract,on_delete=models.PROTECT)
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class PilotBindingReview(AppendOnly):
    binding = models.OneToOneField(PilotBinding,on_delete=models.PROTECT)
    verdict = models.CharField(max_length=10)
    sha256 = models.CharField(max_length=64)
    reason = models.CharField(max_length=2000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class PilotRuntimeReceipt(AppendOnly):
    binding = models.ForeignKey(PilotBinding,on_delete=models.PROTECT)
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64)
    signature = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
