from django.conf import settings
from django.db import models


class Grant(models.Model):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'user', 'action'], name='record_action_grant')]

from .intake_models import TenantAuthority,CaseIntake,AccessChange
