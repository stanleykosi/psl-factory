from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case, event, bump
from apps.pmo.services import subject
from .models import SupportCase

@transaction.atomic
def support_action(actor, case_id, action, evidence_id, expected):
    case = lock_case(actor, case_id, 'support.' + action, expected)
    from .models import SupportIntake,SupportEvent
    from apps.policy.services import resolve
    if SupportIntake.objects.filter(case=case).exists() or SupportEvent.objects.filter(case=case).exists() or resolve('B14.flow_rules',case).status=='ACTIVE':
        raise ValidationError('Use the controlled support flow; legacy actions cannot bypass its review or specialist gates')
    support = SupportCase.objects.get(case=case)
    evidence = subject(case, evidence_id)
    if action == 'respond' and support.status == 'open':
        support.first_response_at = support.first_response_at or timezone.now()
    elif action == 'resolve' and support.status == 'open':
        support.status, support.resolution, support.resolved_at = 'resolved', evidence, timezone.now()
    elif action == 'reopen' and support.status == 'resolved':
        support.status, support.resolved_at = 'open', None
    else:
        raise ValidationError('Unsupported support transition')
    support.save()
    event(actor, case, 'support.' + action, evidence=evidence.pk, prior_resolution=support.resolution_id)
    bump(case)
    return support
