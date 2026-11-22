"""Prepare an isolated existing incident and classification sources for Trial."""
import json
import os
from urllib.parse import urlencode
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo.gates import register_candidate
from apps.policy.role_assignments import COMPONENT, draft
from apps.policy.services import active_component, reference_values, transition
from apps.workflows.factory_emergency_intake import REQUEST_GRANTS
from tests.helpers import rev, signed
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT


GUARD = 'PSL_EMERGENCY_INCIDENT_WALKTHROUGH'
TENANT = 'design-emergency-incident-walkthrough'
TITLE = 'SAMPLE project with an incident awaiting a plan'
CASE_ID = uuid5(NAMESPACE_URL, f'psl-factory:{TENANT}')
MARKER = 'sample.emergency_incident_prepared'
MODULE = 'Sample card intake'
INCIDENT = 'SAMPLE-INC-PAYMENTS'
PLAN = 'Isolate the sample card routing change and verify that the fallback path is available.'


@transaction.atomic
def prepare(viewer):
    if viewer.username != 'psl-agent-trial' or not viewer.is_active or viewer.is_staff or viewer.is_superuser:
        raise RuntimeError('The existing ordinary Trial account is required.')
    case, created = Case.objects.get_or_create(pk=CASE_ID, defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Preserve the workspace occupying this sample identifier.')
    if created:
        owner = get_user_model().objects.create_user('sample-emergency-incident-source-owner')
        Grant.objects.bulk_create([Grant(case=case, user=owner, action=action) for action in dict.fromkeys(ACTIONS)])
        Grant.objects.bulk_create([Grant(case=case, user=viewer, action=action)
                                   for action in ('case.read', 'emergency.manage', *REQUEST_GRANTS)])
        sources = signed(owner, case)
        assignment = reference_values(active_component(COMPONENT, case))
        config = draft(owner, case.pk, [*assignment, {'role': 'PM', 'user_id': viewer.pk}],
                       sources['policy_decision'].pk, timezone.now())
        transition(owner, config.pk, 'validated')
        transition(owner, config.pk, 'active')
        incident = add_evidence(owner, case.pk, 'incident',
                                f'{INCIDENT} · Sample Critical alert from card intake. Production and priority are unverified.',
                                'synthetic:emergency-incident')
        classification = add_evidence(owner, case.pk, 'incident_classification',
            'The sample duty owner confirmed that production criticality and priority one are both unknown.',
            'synthetic:emergency-incident-classification')
        candidate = register_candidate(owner, case.pk, 'SAMPLE-INCIDENT-RELEASE', sources['requirements'].pk, rev(case))
        saved = event(owner, case, MARKER, operator=viewer.pk, incident=incident.pk,
                      classification=classification.pk, candidate=candidate.pk)
    else:
        saved = Audit.objects.get(case=case, action=MARKER)
    if saved.data['operator'] != viewer.pk:
        raise RuntimeError('Preserve the original synthetic requester scope.')
    base = reverse('factory_create')
    return {**saved.data, 'case': str(case.pk), 'start': base + '?' + urlencode({
        'definition': 'pmo-emergency/v1', 'mode': 'incident', 'case': case.pk,
    }), 'module': MODULE, 'plan': PLAN, 'preserved': not created}


def run():
    actual = os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv(GUARD)
    database = os.getenv('PGDATABASE', '')
    if actual != (PREVIEW_PROJECT, 'design-acceptance', '1') or not database or database.startswith('test_'):
        raise RuntimeError('The isolated Railway preview and Emergency incident fixture guard are required.')
    viewer = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    print(GUARD + '=' + json.dumps(prepare(viewer), sort_keys=True), flush=True)
