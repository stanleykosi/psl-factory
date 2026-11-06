from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class StandardPreapproval(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    catalogue_key = models.CharField(max_length=80)
    policies = models.JSONField()
    role = models.CharField(max_length=50)
    verdict = models.CharField(max_length=20)
    authority = models.JSONField()
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    note = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class StandardBinding(AppendOnly):
    version = models.ForeignKey('pmo.ChangeVersion', on_delete=models.PROTECT, related_name='standard_bindings')
    catalogue_key = models.CharField(max_length=80)
    policies = models.JSONField()
    authority = models.JSONField()
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    note = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
