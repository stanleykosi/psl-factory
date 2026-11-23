"""Use the explicitly appointed Finance recipient only on its exact HR disclosure."""
from contextlib import contextmanager

from apps.identity.factory_access import department_cases
from apps.identity.services import subject_actions
from apps.policy.hrfinance_validators import DISCLOSURE
from apps.policy.services import active_component, reference_values


@contextmanager
def recipient_scope(actor, case, named_recipients):
    """Bind existing project, recipient, HR authority and role policy for one record."""
    if actor.pk not in named_recipients or not department_cases(actor, "finance-lead").filter(pk=case.pk).exists():
        yield
        return
    from .hrfinance import authority
    from django.core.exceptions import PermissionDenied

    rule = reference_values(active_component(DISCLOSURE, case))[0]
    if actor.pk not in rule["recipient_ids"]:
        raise PermissionDenied("The current HR disclosure excludes this recipient.")
    authority(actor, case, "receive")
    with subject_actions(actor, case, ("hrfinance.read", "hrfinance.snapshot.read", "hrfinance.receive")):
        yield
