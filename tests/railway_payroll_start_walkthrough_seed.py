"""Prepare only the exact restricted payroll sources for an admitted starter."""
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import event
from apps.finance import hrfinance, payroll
from apps.finance.models import PayrollPublication, PayrollReview, PayrollRun
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory_payroll as flow
from apps.workflows.models import FactoryWork
from tests import payroll_helpers
from tests.railway_admitted_payroll_draft_seed import MAKER_ACTIONS, REVIEWER_ACTIONS, SOURCE_ACTIONS
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.railway_finance_schedule_seed import fixture_reviewer


GUARD = 'PSL_ADMITTED_PAYROLL_START_FIXTURE'
TENANT = 'design-restricted-payroll-start'
MARKER = 'sample.restricted_payroll_start_prepared'
TRIAL_ACTIONS = {'case.read', 'factory.start', 'payroll.read', 'payroll.private.read', 'evidence.add'}
REFERENCE = 'SAMPLE start payroll with exact provider files and HR export'


def populate(case, owner, maker, trial, suffix):
    users = get_user_model().objects
    reviewer = users.create_user(username=f'sample-payroll-start-reviewer-{suffix}')
    recipient = users.create_user(username=f'sample-payroll-start-recipient-{suffix}')
    roles = {'preparer': maker, 'reviewer': reviewer, 'manager': recipient}
    for user, actions in ((owner, SOURCE_ACTIONS), (trial, TRIAL_ACTIONS)):
        Grant.objects.bulk_create([Grant(case=case, user=user, action=action) for action in actions])
    with patch.object(payroll_helpers, 'ACTIONS', tuple(dict.fromkeys((*MAKER_ACTIONS, *REVIEWER_ACTIONS)))):
        sample = payroll_helpers.fixture(context=(owner, case), principal=roles.__getitem__, preparer_receipt=False)
    for person, allowed in ((maker, MAKER_ACTIONS), (reviewer, REVIEWER_ACTIONS)):
        Grant.objects.filter(case=case, user=person).exclude(action__in=allowed).update(active=False)

    profile = json.loads(Path('fixtures/factory-payroll.json').read_text(encoding='utf-8'))
    profile.pop('classification')
    config = draft_operator_policy(owner, case.pk, 'OPS.factory_payroll_execution', profile,
                                   sample['e']['policy_decision'].pk, timezone.now())
    transition(owner, config.pk, 'validated')
    transition(owner, config.pk, 'active')
    return {'request': sample['request'].pk, 'input_ids': [record.pk for record in sample['inputs']],
            'hr_snapshot_id': sample['hr'].pk, 'period': sample['request'].metadata['period'],
            'reviewer': reviewer.pk, 'recipient': recipient.pk}


@transaction.atomic
def prepare(invitation_id, user_id):
    if os.getenv(GUARD) != '1':
        raise RuntimeError('Use the explicit isolated payroll start guard.')
    trial = fixture_reviewer()
    admission, maker = admitted_user(invitation_id, user_id, trial)
    require(maker, admission.invitation.case, 'case.read')
    cid = uuid5(NAMESPACE_URL, f'{TENANT}:{admission.pk}:{maker.pk}')
    attrs = {'tenant': TENANT, 'title': f'SAMPLE restricted payroll start {admission.pk}', 'kind': 'project', 'synthetic': True}
    case, created = Case.objects.get_or_create(pk=cid, defaults=attrs)
    case = Case.objects.select_for_update().get(pk=case.pk)
    if any(getattr(case, key) != value for key, value in attrs.items()) or case.pk == admission.invitation.case_id:
        raise RuntimeError('Use only the newly named synthetic source workspace.')
    owner_name = f'sample-payroll-start-owner-{admission.pk}'
    identity = {'admission': admission.pk, 'invitation': invitation_id, 'maker': maker.pk, 'trial': trial.pk}
    if created:
        owner = get_user_model().objects.create_user(username=owner_name)
        marker = event(owner, case, MARKER, **identity, **populate(case, owner, maker, trial, admission.pk))
    else:
        marker = Audit.objects.select_related('actor').get(case=case, action=MARKER, actor__username=owner_name)
    data, owner = marker.data, marker.actor
    if (any(data.get(key) != value for key, value in identity.items()) or not owner.is_active
            or owner.has_usable_password() or owner.is_staff or owner.is_superuser
            or Grant.objects.filter(user=owner).exclude(case=case).exists()):
        raise RuntimeError('Preserve the recorded admitted people and the separate source holder.')
    for person, actions in ((maker, MAKER_ACTIONS), (trial, TRIAL_ACTIONS)):
        if set(Grant.objects.filter(case=case, user=person, active=True).values_list('action', flat=True)) != set(actions):
            raise RuntimeError('Preserve the exact case-local maker and Trial grants.')
    request = payroll.exact(case, payroll.PayrollRequest, data['request'])
    _, rules = payroll.access(request, maker, True)
    if trial.pk in rules['reader_ids'] or request.metadata['period'] != data['period']:
        raise RuntimeError('Only the originally nominated source readers may start the sample.')
    sources = flow.input_rows(maker, case, request, {key: data[key] for key in ('input_ids', 'hr_snapshot_id')})
    snapshot = hrfinance.exact(case, hrfinance.HRReadSnapshot, data['hr_snapshot_id'])
    if any(source.actor_id != owner.pk for source in sources) or snapshot.actor_id != owner.pk:
        raise RuntimeError('Preserve the independently supplied provider and HR records.')
    work = FactoryWork.objects.filter(case=case, definition=flow.DEFINITION).first()
    if created and (work or PayrollReview.objects.filter(request__case=case).exists()
                    or PayrollRun.objects.filter(request__case=case).exists()
                    or PayrollPublication.objects.filter(request__case=case).exists()):
        raise RuntimeError('Leave work, review and publication for the browser.')
    if work and work.actor_id != maker.pk:
        raise RuntimeError('Only the named admitted maker may submit this specimen.')
    path = reverse('factory_create')
    return {**data, 'case': str(case.pk), 'preserved': not created, 'work': work.pk if work else None,
            'reference': REFERENCE, 'path': f'{path}?{urlencode({"definition": flow.DEFINITION, "case": str(case.pk)})}'}


def run(invitation_id, user_id):
    if (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_SERVICE_ID'),
            os.getenv(GUARD)) != (PREVIEW_PROJECT, 'design-acceptance', '00c14ca1-5361-4bee-97a5-2ec7aba6ef18', '1'):
        raise RuntimeError('Use only the isolated Railway acceptance checks service.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.lower().startswith('test_') or connection.vendor != 'postgresql':
        raise RuntimeError('Select the existing PostgreSQL preview database.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database()')
        if cursor.fetchone()[0] != database:
            raise RuntimeError('The configured preview database must match the connection.')
    print(GUARD + '=' + json.dumps(prepare(invitation_id, user_id)), flush=True)
