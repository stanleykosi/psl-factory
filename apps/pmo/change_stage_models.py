from django.conf import settings
from django.db import models

from apps.core.models import AppendOnly


class ChangeMilestoneLink(AppendOnly):
    class Stage(models.TextChoices):
        UAT = 'uat', 'User acceptance testing'
        COMPLETION = 'completion', 'Completion'

    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    version = models.OneToOneField('pmo.ChangeVersion', on_delete=models.PROTECT)
    plan_event = models.ForeignKey('pmo.ChangeExecutionEvent', on_delete=models.PROTECT)
    original_plan = models.ForeignKey('core.Evidence', on_delete=models.PROTECT, related_name='+')
    signed = models.ForeignKey('core.Evidence', on_delete=models.PROTECT, related_name='+')
    coverage = models.ForeignKey('finance.BillingCoverage', on_delete=models.PROTECT)
    terms = models.ForeignKey('policy.Configuration', on_delete=models.PROTECT)
    stage = models.CharField(max_length=20, choices=Stage.choices)
    scope_note = models.CharField(max_length=240)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(stage__in=['uat', 'completion']),
                                              name='change_milestone_billing_stage')]
