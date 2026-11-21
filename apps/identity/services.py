from contextlib import contextmanager
from contextvars import ContextVar

from django.core.exceptions import PermissionDenied
from apps.core.models import Case
from .models import Grant


_subject_actions = ContextVar('subject_actions', default=None)


@contextmanager
def subject_actions(actor, case, actions):
    """Let a checked adapter call a native service on its already-bound subject.

    Do not wrap a view or a service that accepts a caller-selected subject.
    Workspace discovery always uses persisted workspace grants.
    """
    token = _subject_actions.set((actor.pk, case.pk, frozenset(actions)))
    try:
        yield
    finally:
        _subject_actions.reset(token)


def require(actor, case, action):
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied('This record/action has no active grant')
    scope = _subject_actions.get()
    if scope and scope[:2] == (actor.pk, case.pk) and action in scope[2]:
        return
    if not Grant.objects.filter(user=actor, case=case, action=action, active=True).exists():
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
