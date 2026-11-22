"""Explicit organization-scoped calculator reuse through existing policy sources."""
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from apps.core.models import Case
from apps.identity.models import Grant
from apps.policy.models import ScopeVersion
from apps.policy.services import reference_values
from apps.policy.scopes import source_health


def selected(case, source_id):
    from apps.policy.costing_validators import COMPONENT

    source = ScopeVersion.objects.select_related('configuration__case').filter(
        pk=source_id, kind='organization', ref=case.tenant,
        configuration__component=COMPONENT,
        configuration__case__tenant=case.tenant,
        configuration__case__synthetic=case.synthetic).first()
    if source is None:
        raise ValidationError('Choose a current reviewed studio calculator source for this organization.')
    value = reference_values(source.configuration)[0]
    if 'studio_source_id' in value:
        raise ValidationError('A studio calculator must identify its original rule and examples.')
    if source_health(source) != 'ACTIVE':
        raise ValidationError('Choose a current reviewed studio calculator source for this organization.')
    return source, value


def source_case(actor, case, value):
    from . import costing

    source, expected = selected(case, value['studio_source_id'])
    if {key: item for key, item in value.items() if key != 'studio_source_id'} != expected:
        raise ValidationError('The project must pin the exact reviewed studio calculator and examples.')
    owner_case = source.configuration.case
    if connection.in_atomic_block:
        owner_case = Case.objects.select_for_update().get(pk=owner_case.pk)
        list(Grant.objects.select_for_update().filter(case=owner_case).order_by('pk'))
        if source_health(source) != 'ACTIVE':
            raise ValidationError('The studio calculator changed. Reassess its exact version.')
    if actor is not None:
        costing.readable(actor, owner_case, True)
    return owner_case


@transaction.atomic
def draft_application(actor, case_id, source_id, evidence_id, effective_from):
    from . import costing
    from apps.policy.costing_drafts import draft_costing_policy

    case = costing.locked(actor, case_id, 'policy.configure')
    source, value = selected(case, source_id)
    costing.readable(actor, source.configuration.case, True)
    return draft_costing_policy(actor, case.pk, dict(value, studio_source_id=source.pk),
                                evidence_id, effective_from)
