"""Explicit native loss classifications and permission-filtered debrief proof."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import F
from django.utils import timezone

from apps.core.evidence_access import public_evidence
from apps.identity.services import require
from apps.policy.models import ScopeApplication
from apps.policy.rfp_loss_validators import COMPONENT
from apps.policy.scopes import authorized
from apps.policy.services import reference_values, resolve

from .models import MeetingVersion


def catalog_source_access(actor, configuration):
    inherited = ScopeApplication.objects.select_related('source__configuration__case').filter(configuration=configuration).first()
    if inherited:
        authorized(actor, inherited.source.configuration.case, 'policy.read')


def catalog(actor, case):
    require(actor, case, 'case.read')
    require(actor, case, 'rfp.read')
    resolved = resolve(COMPONENT, case)
    if resolved.status != 'ACTIVE':
        return None, []
    configuration = resolved.configuration
    catalog_source_access(actor, configuration)
    return configuration, reference_values(configuration)[0]['reasons']


def reason_pin(actor, case, key, expected_catalog):
    if not isinstance(key, str) or len(key) > 50 or type(expected_catalog) is not int or expected_catalog < 1:
        raise ValidationError('Select a current reviewed loss reason.')
    configuration, choices = catalog(actor, case)
    if configuration is None or configuration.pk != expected_catalog:
        raise ValidationError('The loss reasons changed. Reload and review the current list.')
    choice = next((row for row in choices if row['key'] == key), None)
    if choice is None:
        raise ValidationError('Select a reason from the current reviewed loss list.')
    return {**choice, 'configuration': configuration.pk}


def debrief_versions(actor, case):
    require(actor, case, 'case.read')
    require(actor, case, 'rfp.read')
    require(actor, case, 'meeting.read')
    return MeetingVersion.objects.filter(meeting__case=case, kind='retrospective', occurred_at__lte=timezone.now(),
        evidence_id__in=public_evidence(case.evidence.all()).values('pk'))


def current_debriefs(actor, case):
    return debrief_versions(actor, case).filter(meeting__current_id=F('pk'))


def check_debrief(actor, case, version_id):
    if type(version_id) is not int or version_id < 1 or not current_debriefs(actor, case).filter(pk=version_id).exists():
        raise ValidationError('Choose a current recorded debrief with evidence in this project.')
    return version_id


def debrief_proof(actor, case, outcome):
    if outcome is None or outcome.result != 'lost' or not outcome.debrief_version_id:
        return None
    try:
        return debrief_versions(actor, case).filter(pk=outcome.debrief_version_id).values(
            'meeting__reference', 'number', 'occurred_at', 'summary', 'evidence_id', 'evidence__source').first()
    except PermissionDenied:
        return None
