"""Prepare separate visible project rows with current recorded directory facts."""

import json
import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import event
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import engagement
from apps.policy.engagement_validators import ASSIGN
from apps.workflows import factory, factory_delivery
from tests import railway_weekly_return_walkthrough_seed as weekly
from tests.billing_helpers import coverage, policy, stage_policy
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_delivery import DeliveryFixture
from tests.test_engagement_intake import activate


GUARD = 'PSL_PROJECT_DIRECTORY_WALKTHROUGH'
TENANT = 'design-project-directory-walkthrough'
TITLES = {'release': 'SAMPLE project directory planned release', 'review': 'SAMPLE project directory report review',
          'unprovided': 'SAMPLE project directory unprovided facts'}
CASE_IDS = {name: uuid5(NAMESPACE_URL, f'psl-factory:{TENANT}/{name}') for name in TITLES}
MARKER = 'sample.project_directory_prepared'
MANAGER = 'Sample Delivery Manager'
MILESTONE = 'Sample customer acceptance'


def grant(case, user, actions):
    Grant.objects.bulk_create([Grant(case=case, user=user, action=action) for action in dict.fromkeys(actions)])


def prepare_release(case, viewer):
    maker = get_user_model().objects.create_user('sample-directory-delivery-manager', first_name=MANAGER)
    grant(case, maker, ACTIONS)
    grant(case, viewer, ('case.read', 'factory.read', 'engagement.read', 'delivery.read', 'finance.read'))
    sample = DeliveryFixture()
    sample.setup_delivery(context=(maker, case))
    facts = sample.evidence('engagement_source', 'Fictional ownership and scope evidence for the sample project.')
    engagement.capture(maker, case.pk, 'B', facts.pk, 'SAMPLE-DIRECTORY-PROJECT', 'sample-directory-engagement')
    rules = json.loads(Path('fixtures/engagement-intake.json').read_text(encoding='utf-8'))['assignment']
    activate(maker, case, ASSIGN, rules, sample.e['policy_decision'])
    assignment = engagement.assign(maker, case.pk, maker.pk, 'PMO Lead', facts.pk, 'sample-directory-assignment')

    bill = coverage(maker, case)
    stage_policy(maker, case, bill, sample.e['signature'])
    due = timezone.localdate() + timedelta(days=14)
    terms = policy(maker, case, 'D12.stage_terms', [
        {'coverage_id': bill.pk, 'stage': 'uat', 'amount': '42.50', 'due_date': due.isoformat()},
    ])
    predicate = policy(maker, case, 'D12.uat_billing_predicate_ref', {
        'coverage_id': bill.pk, 'stage': 'uat', 'milestone_name': MILESTONE,
    })
    work = factory_delivery.start(maker, case.pk, 'SAMPLE-DIRECTORY-RELEASE', sample.d.pk, case.title, rev(case))
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    if work.status != 'configuration_needed':
        raise RuntimeError('The sample release must retain its genuine setup hold.')
    return event(maker, case, MARKER, operator=viewer.pk, manager=maker.pk, assignment=assignment.pk,
        work=work.pk, dossier=sample.d.pk, signature=sample.e['signature'].pk, coverage=bill.pk,
        terms=terms.pk, predicate=predicate.pk, milestone=MILESTONE, due=due.isoformat()).data


def prepare_review(case, viewer):
    maker = get_user_model().objects.create_user('sample-directory-report-preparer')
    witness = weekly.create_sample(case, maker, viewer, {'scenario': 'directory-scoped-review'})
    grant(case, viewer, ('delivery.read',))
    data = witness.data
    return event(maker, case, MARKER, operator=viewer.pk, work=data['work'], report=data['first_report'],
                 review=data['first_task'], reviewer=viewer.pk).data


def prepare_unprovided(case, viewer):
    grant(case, viewer, ('case.read', 'factory.read', 'delivery.read'))
    return event(viewer, case, MARKER, operator=viewer.pk).data


@transaction.atomic
def prepare_case(viewer, scenario, builder):
    title = TITLES[scenario]
    case, created = Case.objects.get_or_create(pk=CASE_IDS[scenario], defaults={
        'tenant': TENANT, 'title': title, 'kind': 'project', 'synthetic': True,
    })
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, title, 'project', True):
        raise RuntimeError('Preserve the unrelated workspace occupying this sample identifier.')
    data = builder(case, viewer) if created else Audit.objects.get(case=case, action=MARKER).data
    if data['operator'] != viewer.pk:
        raise RuntimeError('Preserve the original Trial scope.')
    return {**data, 'case': str(case.pk), 'title': title,
            'journey': reverse('design_project', args=[case.pk]), 'preserved': not created}


def prepare(viewer):
    if not viewer.is_active or viewer.is_staff or viewer.is_superuser:
        raise RuntimeError('Use the active ordinary Trial account.')
    base = reverse('workspace_overview')
    return {'path': base + '?' + urlencode({'kind': 'project', 'tenant': TENANT}),
            'active': base + '?' + urlencode({'kind': 'project', 'tenant': TENANT, 'lifecycle': 'active'}),
            'release': prepare_case(viewer, 'release', prepare_release),
            'review': prepare_case(viewer, 'review', prepare_review),
            'unprovided': prepare_case(viewer, 'unprovided', prepare_unprovided)}


def run():
    if (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv(GUARD)) != (
            PREVIEW_PROJECT, 'design-acceptance', '1'):
        raise RuntimeError('The exact Railway preview and project directory fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('Use the explicitly configured isolated preview sample database.')
    viewer = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    print(GUARD + '=' + json.dumps(prepare(viewer)), flush=True)
