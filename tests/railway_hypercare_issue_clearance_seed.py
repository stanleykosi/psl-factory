"""Prepare a guarded synthetic high issue and a separate proof for re-evaluation."""

import json
import os
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo.issues import log_issue
from apps.policy.change_drafts import draft_standard_policy
from apps.policy.services import transition
from apps.workflows import factory, factory_hypercare
from apps.workflows.models import FactoryProgress, FactoryWork
from tests import test_delivery
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_factory_hypercare import setup


GUARD = 'PSL_HYPERCARE_ISSUE_CLEARANCE_WALKTHROUGH'
TENANT = 'design-hypercare-issue-clearance-walkthrough'
CASE_ID = uuid5(NAMESPACE_URL, f'psl-factory:{TENANT}')
TITLE = 'SAMPLE release stability held by a high issue'
MARKER = 'sample.hypercare_issue_clearance_prepared'


def create_sample(case, operator):
    source_holder = get_user_model().objects.create_user('sample-hypercare-issue-source-holder')
    Grant.objects.bulk_create([Grant(case=case, user=user, action=action) for user, actions in (
        (operator, dict.fromkeys(ACTIONS)), (source_holder, ('case.read', 'issue.read', 'evidence.add')),
    ) for action in actions])
    with patch.object(test_delivery, 'setup_case', return_value=(operator, case)):
        sample = setup()
    release = sample.accepted()
    sample.observations()
    rule_proof = sample.evidence('policy_decision', 'Fictional rule for these scoped issue states and this sample project only.')
    rule = {**test_delivery.CRITERIA, 'issue_clearance': {'scope': 'project_issue_register',
        'reader_id': source_holder.pk, 'blocking_statuses': ['Open', 'In Progress', 'Resolved'],
        'blocking_severities': ['High', 'Critical']}}
    configuration = draft_standard_policy(operator, case.pk, 'D11.hypercare_criteria_ref', rule, rule_proof.pk, timezone.now())
    transition(operator, configuration.pk, 'validated')
    transition(operator, configuration.pk, 'active')
    proof = add_evidence(source_holder, case.pk, 'issue_source', 'Fictional payments fail on sample cards.', 'synthetic:release-stability-high')
    later = add_evidence(source_holder, case.pk, 'issue_source',
        'The sample fix passed. The remaining fictional issue is limited and its reviewed severity is Medium.',
        'synthetic:release-stability-verified-reduced-impact')
    state = log_issue(operator, case.pk, 'SAMPLE-HYPERCARE-CARDS', 'Sample payments fail for some cards', 'Delivery',
        operator.pk, 'Confirm the sample fix and reassess severity.', proof.pk, 'Exact fictional witness statement.', rev(case), 'High')
    factory.run_until_wait(sample.work.pk)
    sample.work.refresh_from_db()
    assessment = factory_hypercare.assessed(sample.work)
    if (sample.work.status != 'waiting' or not assessment or assessment.snapshot['qualified'] is not False
            or assessment.snapshot['issue_clearance']['status'] != 'not_met' or FactoryProgress.objects.filter(work=sample.work).exists()):
        raise RuntimeError('Stop at the native below-criterion assessment before the operator records the verified change.')
    return event(operator, case, MARKER, operator=operator.pk, source_holder=source_holder.pk, work=sample.work.pk,
        dossier=sample.d.pk, candidate=sample.candidate.pk, release=release.pk, assessment=assessment.pk,
        configuration=configuration.pk, issue=state.issue_id, state=state.pk, reference=state.issue.reference,
        original_proof=proof.pk, changed_impact_proof=later.pk, changed_severity='Medium',
        note='Recorded the separately witnessed reduced impact from the sample fix.').data


@transaction.atomic
def prepare(operator):
    if not operator.is_active or operator.is_staff or operator.is_superuser:
        raise RuntimeError('Use the active ordinary Trial account.')
    case, created = Case.objects.get_or_create(pk=CASE_ID, defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Preserve the unrelated workspace occupying this identifier.')
    data = create_sample(case, operator) if created else Audit.objects.get(case=case, action=MARKER).data
    if data['operator'] != operator.pk:
        raise RuntimeError('Preserve the original exact operator scope.')
    work = FactoryWork.objects.get(pk=data['work'], case=case, actor=operator, definition=factory_hypercare.DEFINITION)
    return {**data, 'case': str(case.pk), 'preserved': not created, 'path': reverse('factory_detail', args=[work.pk]),
            'issue_path': reverse('issues', args=[case.pk]) + f"#issue-{data['issue']}"}


def run():
    if (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv(GUARD)) != (
            PREVIEW_PROJECT, 'design-acceptance', '1'):
        raise RuntimeError('The exact Railway preview and Hypercare issue specimen guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('Use the explicitly configured isolated preview sample database.')
    operator = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    print(GUARD + '=' + json.dumps(prepare(operator)), flush=True)
