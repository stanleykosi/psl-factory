from apps.core.evidence_access import public_evidence,restricted
import uuid
from django.conf import settings
from django.db import models


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


class Audit(AppendOnly):
    case = models.ForeignKey(Case, on_delete=models.PROTECT, related_name='audit')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=100)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
