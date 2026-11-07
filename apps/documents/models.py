from django.db import models
from django.conf import settings
from apps.core.models import AppendOnly
from .validation_models import DiscoverySource,ValidationExample,ValidationPackage,ValidationReview,ValidationReplay,ValidationFollowup

class Review(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    verdict = models.CharField(max_length=20)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Template(AppendOnly):
    def __str__(self):
        return f"{self.name} · v{self.version}"

    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    version = models.PositiveIntegerField()
    definition = models.JSONField()
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['case','name','version'],name='document_template_version')]


class Document(models.Model):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    title = models.CharField(max_length=240)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    current = models.ForeignKey('Version', null=True, on_delete=models.PROTECT, related_name='+')


class Version(AppendOnly):
    def __str__(self):
        return f"{self.document.title} · v{self.number} · {self.audience}"

    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name='versions')
    number = models.PositiveIntegerField()
    template = models.ForeignKey(Template, on_delete=models.PROTECT, related_name='documents')
    audience = models.CharField(max_length=20)
    fields = models.JSONField()
    source_manifest = models.JSONField()
    baseline_manifest = models.JSONField()
    template_current_manifest = models.JSONField(default=dict)
    payload = models.JSONField()
    payload_sha256 = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['document','number'],name='controlled_document_version')]


class ControlledReview(AppendOnly):
    version = models.ForeignKey(Version, on_delete=models.PROTECT, related_name='reviews')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    verdict = models.CharField(max_length=20)
    note = models.TextField()
    authority = models.JSONField()
    delegated = models.BooleanField(default=False)
    payload_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)


class Publication(AppendOnly):
    version = models.OneToOneField(Version, on_delete=models.PROTECT)
    review = models.ForeignKey(ControlledReview, null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    policies = models.JSONField()
    recipient_ids = models.JSONField()
    retention_days = models.PositiveIntegerField()
    operation_key = models.CharField(max_length=200, unique=True)
    factory_work = models.ForeignKey('workflows.FactoryWork',null=True,on_delete=models.PROTECT,related_name='document_publications')
    factory_policy = models.ForeignKey('policy.Configuration',null=True,on_delete=models.PROTECT,related_name='+')
    factory_source = models.ForeignKey('core.Evidence',null=True,on_delete=models.PROTECT,related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)


class PublicationJob(models.Model):
    publication = models.OneToOneField(Publication,on_delete=models.PROTECT,related_name='job')
    status = models.CharField(max_length=20,default='pending')
    lease_until = models.DateTimeField(null=True)
    fence = models.PositiveIntegerField(default=0)
    attempts = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=400,blank=True)


class PublicationReceipt(AppendOnly):
    publication = models.ForeignKey(Publication,on_delete=models.PROTECT)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    operation_key = models.CharField(max_length=220,unique=True)
    payload = models.JSONField()
    payload_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['publication','recipient'],name='publication_recipient_once')]

from .protection_models import PrivateProtectionPacket

from .migration_models import MigrationPlan,MigrationProof,MigrationObservation,MigrationAssessment,MigrationReadinessReview,MigrationAF13Binding

from .template_models import TemplateScope, TemplateClaim, TemplateClaimRetraction, TemplateResolution
