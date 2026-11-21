from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import AppendOnly


TEAM_ROLES = ('pmo-lead', 'finance-lead', 'hr', 'admin')
STANDALONE_ROLES = ('cto', 'ceo')


class StaffTeam(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    role = models.CharField(max_length=20)
    name = models.CharField(max_length=80)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(role__in=TEAM_ROLES), name='staff_team_base_role'),
            models.UniqueConstraint(fields=['case', 'role', 'name'], name='staff_team_workspace_name'),
        ]


class StaffMembership(models.Model):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    role = models.CharField(max_length=20)
    mode = models.CharField(max_length=12)
    team = models.ForeignKey(StaffTeam, on_delete=models.PROTECT, null=True)
    invitation = models.OneToOneField('identity.StaffInvitation', on_delete=models.PROTECT)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['case', 'user'], condition=Q(active=True), name='staff_active_membership'),
            models.CheckConstraint(condition=(Q(mode__in=['member', 'lead'], role__in=TEAM_ROLES, team__isnull=False) |
                Q(mode='standalone', role__in=STANDALONE_ROLES, team__isnull=True)), name='staff_membership_scope'),
        ]


class StaffAssignment(models.Model):
    """Access to one native action or decision. Project/source access is separate."""
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    membership = models.ForeignKey(StaffMembership, on_delete=models.PROTECT)
    action = models.OneToOneField('pmo.ActionItem', on_delete=models.PROTECT, null=True)
    review_task = models.ForeignKey('workflows.HumanTask', on_delete=models.PROTECT, null=True)
    schedule = models.ForeignKey('finance.ScheduleWork', on_delete=models.PROTECT, null=True)
    hr_request = models.ForeignKey('finance.HRHandoffRecord', on_delete=models.PROTECT, null=True)
    hr_successor = models.ForeignKey('finance.HRReadSnapshot', on_delete=models.PROTECT, null=True)
    work = models.ForeignKey('workflows.FactoryWork', on_delete=models.PROTECT, null=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(
                Q(action__isnull=False, review_task__isnull=True, schedule__isnull=True, hr_request__isnull=True) |
                Q(action__isnull=True, review_task__isnull=False, schedule__isnull=True, hr_request__isnull=True, work__isnull=True) |
                Q(action__isnull=True, review_task__isnull=True, schedule__isnull=False, hr_request__isnull=True, work__isnull=True) |
                Q(action__isnull=True, review_task__isnull=True, schedule__isnull=True, hr_request__isnull=False, work__isnull=True)
            ), name='staff_assignment_subject'),
            models.CheckConstraint(condition=Q(hr_successor__isnull=True) | Q(hr_request__isnull=False),
                                   name='staff_assignment_hr_successor'),
            models.UniqueConstraint(fields=['membership', 'review_task'], name='staff_assignment_exact_review'),
            models.UniqueConstraint(fields=['membership', 'schedule'], name='staff_assignment_exact_schedule'),
            models.UniqueConstraint(fields=['membership', 'hr_request'], name='staff_assignment_exact_hr_request'),
        ]


class StaffReviewUse(AppendOnly):
    assignment = models.ForeignKey(StaffAssignment, on_delete=models.PROTECT)
    review = models.OneToOneField('documents.ControlledReview', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class StaffScheduleReviewUse(AppendOnly):
    assignment = models.ForeignKey(StaffAssignment, on_delete=models.PROTECT)
    review = models.OneToOneField('finance.ScheduleReview', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
