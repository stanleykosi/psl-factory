from django.core.exceptions import PermissionDenied
from apps.core.models import Case
from .models import Grant


def require(actor, case, action):
    if not actor.is_authenticated or not actor.is_active or not Grant.objects.filter(
            user=actor, case=case, action=action, active=True).exists():
        raise PermissionDenied('This record/action has no active grant')


def visible_cases(actor):
    return Case.objects.filter(grant__user=actor, grant__active=True, grant__action='case.read').distinct()
