from django.conf import settings
from django.db import models

from apps.core.models import AppendOnly


DEPARTMENTS = ['Engineering', 'QA', 'Security', 'Product', 'Infrastructure']


class PlanningDepartmentInput(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    packet = models.ForeignKey('core.Evidence', on_delete=models.PROTECT, related_name='+')
    department = models.CharField(max_length=30)
    version = models.PositiveIntegerField()
    previous = models.OneToOneField('self', null=True, on_delete=models.PROTECT, related_name='successor')
    source = models.ForeignKey('core.Evidence', on_delete=models.PROTECT, related_name='+')
    source_party = models.CharField(max_length=160)
    received_at = models.DateTimeField()
    summary = models.TextField()
    effort_state = models.CharField(max_length=20)
    person_days = models.DecimalField(max_digits=12, decimal_places=3, null=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['packet', 'department', 'version'], name='planning_department_version'),
            models.CheckConstraint(condition=models.Q(department__in=DEPARTMENTS), name='planning_department_name'),
            models.CheckConstraint(condition=(
                models.Q(effort_state='known', person_days__gte=0, person_days__isnull=False) |
                models.Q(effort_state__in=['unknown', 'not_applicable'], person_days__isnull=True)),
                name='planning_department_effort'),
        ]
