from django.core.exceptions import PermissionDenied
from apps.core.models import Case
from .models import Grant


def require(actor, case, action):
    if not actor.is_authenticated or not actor.is_active or not Grant.objects.filter(
            user=actor, case=case, action=action, active=True).exists():
        raise PermissionDenied('This record/action has no active grant')


def visible_cases(actor):
    return Case.objects.filter(grant__user=actor, grant__active=True, grant__action='case.read').distinct()


def active_case_grants(actor, case_ids, *, actions=None):
    """Current (case, action) pairs for the selected cases only."""
    if not actor.is_authenticated or not actor.is_active or not case_ids:
        return set()
    grants = Grant.objects.filter(user=actor, user__is_active=True, case_id__in=case_ids, active=True)
    if actions is not None:
        grants = grants.filter(action__in=actions)
    return set(grants.values_list('case_id', 'action'))
