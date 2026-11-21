"""Guarded synthetic statements for separate approve and return journeys."""
import json
import os
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.documents import controlled
from apps.documents.models import Publication, Version
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import commercial
from apps.policy.services import register_reference
from apps.workflows.models import HumanTask
from tests.document_helpers import artifact
from tests.helpers import activate, project_evidence, rev
from tests.railway_independent_commercial_seed import PROJECT
from tests.test_commercial_changes import DEFINITION, approvals
from tests.test_template_current import claim, configure, scope


TENANT = 'design-statement-of-work-review'
KINDS = ('approve', 'return')
CASE_IDS = {key: uuid5(NAMESPACE_URL, f'{TENANT}/{key}') for key in KINDS}
TRIAL = 'psl-agent-trial'
TRIAL_ACTIONS = {'case.read', 'commercial.read', 'document.read', 'document.review_controlled'}
MARKER = 'sample.statement_of_work_review_prepared'
ORIGINAL = 'SAMPLE: deliver the booking portal for one clinic.'
CORRECTED = 'SAMPLE: deliver the booking portal for the same clinic with a confirmed handover checklist.'


def proposal(owner, case, evidence, text):
    source = add_evidence(owner, case.pk, 'sow', text, 'synthetic:statement-of-work-owner-scope')
    selected = {kind: (source if kind == 'sow' else evidence[kind]).pk for kind in commercial.SOURCE_KINDS}
    row = commercial.propose(owner, case.pk, selected, evidence['requirements'].pk,
                             'Prepared from the exact source statement and unchanged costing', rev(case))
    approvals(owner, case, row)
    return row


def populate(owner, trial, case):
    proof = project_evidence(owner, case)
    decision = proof['policy_decision']
    assigned = [(role, owner.pk) for role in commercial.ROLES] + [('PMO Lead', trial.pk)]
    refs = [register_reference(owner, case.pk, f'sample-sow-role:{index}', 'schema:psl/role-assignment/v1',
                              {'role': role, 'user_id': user}, decision.pk).ref
            for index, (role, user) in enumerate(assigned)]
    activate(owner, case, 'D05.role_principal_assignments', refs, decision)
    artifact(owner, case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v1',
             {'rules': [{'role': 'PMO Lead', 'actions': ['return']}]}, decision)
    template = controlled.register_template(owner, case.pk, 'SAMPLE statement of work', DEFINITION,
                                            decision.pk, rev(case))
    template_scope = scope(owner, case, decision)
    configure(owner, case, decision, [template], [(template_scope, owner)])
    claim(owner, case, template_scope, template, decision)
    first = proposal(owner, case, proof, ORIGINAL)
    initial = commercial.draft_submission(owner, case.pk, first.pk, template.pk, rev(case),
                                          template_scope_id=template_scope.pk)
    historical_task = controlled.request_review(owner, case.pk, initial.pk, rev(case))
    historical = controlled.review_version(owner, case.pk, initial.pk, 'return',
                                           'SAMPLE original wording needs the handover detail', rev(case))
    second = proposal(owner, case, proof, CORRECTED)
    current = commercial.draft_submission(owner, case.pk, second.pk, template.pk, rev(case),
        template_scope_id=template_scope.pk, replaces_version_id=initial.pk)
    task = controlled.request_review(owner, case.pk, current.pk, rev(case))
    return event(owner, case, MARKER, trial=trial.pk, original=initial.pk, original_review=historical.pk,
        original_task=historical_task.pk, version=current.pk, proposal=second.pk, template=template.pk,
        scope=template_scope.pk, task=task.pk, costing=proof['costing'].pk, requirements=proof['requirements'].pk,
        plan=proof['plan'].pk)


@transaction.atomic
def prepare(key):
    if key not in CASE_IDS:
        raise RuntimeError('Choose the exact synthetic approval or return specimen.')
    trial = get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    if Case.objects.filter(tenant=TENANT).exclude(pk__in=CASE_IDS.values()).exists():
        raise RuntimeError('Preserve work outside the two exact standalone statement specimens.')
    title = f'SAMPLE Harbour Clinics statement review ({key})'
    case, created = Case.objects.get_or_create(pk=CASE_IDS[key], defaults={
        'tenant': TENANT, 'title': title, 'kind': 'project', 'synthetic': True,
    })
    case = Case.objects.select_for_update().get(pk=case.pk)
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, title, 'project', True):
        raise RuntimeError('Use only the exact synthetic statement specimen.')
    if created:
        owner = get_user_model().objects.create_user(f'sample-sow-{key}-preparer')
        Grant.objects.bulk_create([
            *[Grant(user=owner, case=case, action=action) for action in dict.fromkeys(ACTIONS)],
            *[Grant(user=trial, case=case, action=action) for action in sorted(TRIAL_ACTIONS)],
        ])
        marker = populate(owner, trial, case)
    else:
        marker = Audit.objects.select_related('actor').get(case=case, action=MARKER)
    if (marker.data['trial'] != trial.pk or marker.actor.username != f'sample-sow-{key}-preparer'
            or marker.actor.has_usable_password() or marker.actor.is_staff or marker.actor.is_superuser):
        raise RuntimeError('Preserve the separate scoped trial and noninteractive fixture author.')
    if set(Grant.objects.filter(user=trial, case=case, active=True).values_list('action', flat=True)) != TRIAL_ACTIONS:
        raise RuntimeError('Preserve the exact original Trial review permissions.')
    data = marker.data
    current = Version.objects.get(pk=data['version'], document__case=case, number=2, template_id=data['template'],
                                  commercialdocumentbinding__revision_id=data['proposal'])
    original = Version.objects.get(pk=data['original'], document_id=current.document_id, number=1)
    original.reviews.get(pk=data['original_review'], verdict='return', payload_sha256=original.payload_sha256)
    task = HumanTask.objects.get(version=current, pk=data['task'], required_role='PMO Lead')
    if Publication.objects.filter(version__document_id=current.document_id).exists():
        raise RuntimeError('No delivery reservation belongs in this synthetic review exercise.')
    review = current.reviews.order_by('-pk').first()
    if review and (review.actor_id != trial.pk or review.verdict != key):
        raise RuntimeError('Preserve the exact separate Trial review outcome.')
    return {**data, 'case': str(case.pk), 'preparer': marker.actor_id, 'preserved': not created,
            'task_status': task.status, 'review': review.pk if review else None,
            'previous': reverse('design_sow_review', args=[case.pk, original.pk]),
            'url': reverse('design_sow_review', args=[case.pk, current.pk])}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_SOW_REVIEW_FIXTURE')) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The exact Railway acceptance project and statement fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_') or database != connection.settings_dict['NAME']:
        raise RuntimeError('Set the exact preview database before preparing statement review records.')
    print('PSL_SOW_REVIEW_FIXTURE=' + json.dumps({key: prepare(key) for key in KINDS}), flush=True)
