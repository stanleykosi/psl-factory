"""Prepare a named synthetic emergency awaiting its independent technology decision."""
import json
import os
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import emergencies as native
from apps.pmo.models import EmergencyAuthorization, EmergencyOutcome
from apps.policy.change_drafts import draft_standard_policy
from apps.policy.role_assignments import COMPONENT as ASSIGNMENTS, draft as roles
from apps.policy.services import active_component, reference_values, transition
from apps.workflows import factory_emergency
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT, prepare_emergency


GUARD = 'PSL_EMERGENCY_CTO_WALKTHROUGH'
TENANT = 'design-emergency-cto-walkthrough'
TITLE = 'SAMPLE emergency change awaiting its technology decision'
CASE_ID = uuid5(NAMESPACE_URL, f'psl-factory:{TENANT}')
MARKER = 'sample.emergency_cto_prepared'
TRIAL_GRANTS = ('case.read', 'factory.read', 'emergency.read', 'emergency.decide')


def grant(case, user, actions):
    Grant.objects.bulk_create([Grant(case=case, user=user, action=action) for action in dict.fromkeys(actions)])


def activate(actor, config):
    transition(actor, config.pk, 'validated')
    return transition(actor, config.pk, 'active')


@transaction.atomic
def prepare(viewer):
    if viewer.username != 'psl-agent-trial' or not viewer.is_active or viewer.is_staff or viewer.is_superuser:
        raise RuntimeError('The current ordinary Trial account must hold the separate technology decision.')
    case, created = Case.objects.get_or_create(pk=CASE_ID, defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Preserve the workspace occupying the emergency sample identifier.')
    if created:
        user_model = get_user_model()
        owner = user_model.objects.create_user('sample-emergency-cto-owner', first_name='Sample Emergency Owner')
        incident = user_model.objects.create_user('sample-emergency-cto-incident', first_name='Sample Incident Lead')
        engineering = user_model.objects.create_user('sample-emergency-cto-engineering', first_name='Sample Engineering Lead')
        grant(case, owner, ACTIONS)
        grant(case, viewer, TRIAL_GRANTS)
        for participant in (incident, engineering):
            grant(case, participant, ('case.read', 'emergency.read', 'emergency.decide', 'evidence.add'))
        work = prepare_emergency(owner, case, verified_sources=True, refusal=True)
        profile, _ = factory_emergency.source(work, owner)
        proof = add_evidence(owner, case.pk, 'policy_decision',
                             'Separate incident, Engineering and technology roles for synthetic browser acceptance.',
                             'synthetic:emergency-cto-roles')

        assignment_roles = {'Security Lead': incident.pk, 'Engineering Lead': engineering.pk, 'CTO': viewer.pk}
        existing = reference_values(active_component(ASSIGNMENTS, case))
        activate(owner, roles(owner, case.pk, [dict(item, user_id=assignment_roles[item['role']])
            if item['role'] in assignment_roles else item for item in existing], proof.pk, timezone.now()))
        value, _ = native.emergency_policy(case)
        replacement = dict(value, incident_lead_role='Security Lead', incident_engineering_overlap='distinct_people')
        activate(owner, draft_standard_policy(owner, case.pk, 'D01.emergency_glpi_relationship',
                                             replacement, proof.pk, timezone.now()))
        earlier = []
        for actor, role, authority in ((incident, 'Incident Lead', 'Security Lead'),
                                       (engineering, 'Engineering Lead', 'Engineering Lead')):
            evidence = add_evidence(actor, case.pk, 'emergency_decision', f'Sample {role} approval after checking the exact change.',
                                    'synthetic:emergency-cto-prior-decision')
            decision = native.decide_emergency(actor, case.pk, profile.pk, role, authority, 'approve', evidence.pk,
                                              'The source owner checked this version of the simulated request.', rev(case))
            earlier.append(decision.pk)
        evidence = add_evidence(owner, case.pk, 'emergency_decision',
                                'Sample technology decision brief. The rollback rehearsal has not been evidenced.',
                                'synthetic:emergency-cto-decision-brief')
        implementation = case.evidence.get(kind='change_implementation', source='synthetic:emergency-tests')
        glpi = native.glpi_snapshot(case, profile.candidate)
        if (EmergencyAuthorization.objects.filter(profile=profile).exists()
                or EmergencyOutcome.objects.filter(profile=profile).exists()):
            raise RuntimeError('The sample must stop before authorization and implementation.')
        saved = event(owner, case, MARKER, operator=viewer.pk, owner=owner.pk, work=work.pk, profile=profile.pk,
                      candidate=profile.candidate_id, incident=profile.version.incident_id, approvers=[incident.pk, engineering.pk],
                      prior_decisions=earlier, evidence=evidence.pk, implementation_evidence=implementation.pk, glpi=glpi)
    else:
        saved = Audit.objects.get(case=case, action=MARKER)
    if saved.data['operator'] != viewer.pk:
        raise RuntimeError('Preserve the original synthetic technology decision scope.')
    return {
        **saved.data, 'case': str(case.pk), 'decision': reverse('factory_invoice_decision', args=[saved.data['work']]),
        'response': reverse('factory_work_response', args=[saved.data['work']]), 'preserved': not created,
    }


def run():
    project = os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv(GUARD)
    database = os.getenv('PGDATABASE', '')
    if project != (PREVIEW_PROJECT, 'design-acceptance', '1') or not database or database.startswith('test_'):
        raise RuntimeError('The exact isolated Railway preview and emergency technology fixture guard are required.')
    viewer = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    print(GUARD + '=' + json.dumps(prepare(viewer), sort_keys=True), flush=True)
