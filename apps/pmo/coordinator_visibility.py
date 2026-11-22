"""A recipient can acknowledge the exact current project view without storing its contents."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.core.models import Audit, Case
from apps.core.services import event
from apps.documents.contracts import digest
from apps.identity.services import require
from apps.policy.project_view_validators import COMPONENT
from apps.policy.services import active_component, reference_values
from apps.workflows.native_station_contracts import Observation, Route
from . import project_view
from .coordinator_delivery import lines


RECEIVED = "project.audience_view_received"


def view_digest(actor, value):
    return digest([actor.pk, value["case_id"], value["configuration_id"], value["audience"], value["groups"]])


@transaction.atomic
def acknowledge(actor, case_id, audience, expected):
    case = Case.objects.select_for_update().get(pk=case_id)
    value = project_view.projection(actor, case.pk, audience)
    signature = view_digest(actor, value)
    if signature != expected:
        raise ValidationError("The project view changed. Read the current view before acknowledging it.")
    data = {"configuration": value["configuration_id"], "audience": audience, "digest": signature}
    existing = Audit.objects.filter(case=case, actor=actor, action=RECEIVED, data=data).first()
    return existing or event(actor, case, RECEIVED, **data)


def disclosure_owner(state):
    from django.contrib.auth import get_user_model
    return get_user_model().objects.get(pk=reference_values(state.configuration)[0]["discloser_id"])


def disclosure(state, actor):
    config = state.configuration
    case = config.case
    require(actor, case, "case.read")
    require(actor, case, "project.share")
    if active_component(COMPONENT, case).pk != config.pk or disclosure_owner(state).pk != actor.pk:
        raise PermissionDenied("The current configured project discloser is required.")
    value = reference_values(config)[0]
    source = case.evidence.get(pk=int(config.envelope["human_decision_ref"].removeprefix("evidence:")), kind="policy_decision")
    receipt = None
    for item in Audit.objects.filter(case=case, action=RECEIVED, data__configuration=config.pk).select_related("actor").order_by("-pk")[:32]:
        try:
            current = project_view.projection(item.actor, case.pk, item.data["audience"])
        except (PermissionDenied, ValidationError):
            continue
        if view_digest(item.actor, current) == item.data["digest"]:
            receipt = item
            break
    return Observation(case, source, lines(f"Project visibility configuration revision {config.revision}.",
            f"The disclosure specifies {len(value['profiles'])} audience profiles.",
            "A receipt identifies only the recipient and view that were acknowledged."), receipt)


ROUTES = [Route("P05", "policy.PolicyState",
          lambda row: row.state == "active" and row.configuration.component == COMPONENT,
          disclosure_owner, disclosure)]
