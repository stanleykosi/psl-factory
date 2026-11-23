"""An independent synthetic payroll source check for two already admitted readers."""

import json
import os
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse

from apps.core.models import Audit, Case
from apps.core.services import event
from apps.finance import payroll, payroll_departure as timing, payroll_identity as names
from apps.finance.payroll_models import PayrollPublication
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.payroll_validators import ACCESS, DEPARTURE_CHECK, NAME_CHECK
from tests import payroll_helpers
from tests.helpers import rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.railway_finance_schedule_seed import fixture_reviewer


TENANT = 'design-admitted-payroll-source-checks'
GUARD = 'PSL_ADMITTED_PAYROLL_SOURCE_CHECKS'
MARKER = 'sample.admitted_payroll_source_checks'
MAKER_ACTIONS = (
    'case.read', 'evidence.add', 'payroll.read', 'payroll.private.read', 'payroll.capture',
    'payroll.request', 'payroll.combine', 'payroll.match', 'payroll.hr_correction',
    'hrfinance.read', 'hrfinance.need', 'hrfinance.contract', 'hrfinance.receive',
    'hrfinance.snapshot.read', 'hrfinance.correction',
)
HR_ACTIONS = ('case.read', 'evidence.add', 'hrfinance.read', 'hrfinance.authorize', 'hrfinance.capture', 'hrfinance.respond')
SETUP_AUTHORITY = ('policy.configure', 'policy.activate', 'policy.read')
BASELINE_REVIEW_ACTIONS = ('case.read', 'payroll.read', 'payroll.private.read', 'payroll.review',
                           'hrfinance.read', 'hrfinance.receive', 'hrfinance.snapshot.read')


def case_id(invitation_id):
    return uuid5(NAMESPACE_URL, f'{TENANT}:{invitation_id}')


def baseline(case, maker, hr_actor, suffix):
    users = get_user_model().objects
    reviewer = users.create_user(username=f'payroll-checks-{suffix}-baseline-reviewer')
    aggregate_reader = users.create_user(username=f'payroll-checks-{suffix}-aggregate-reader')
    grants = [Grant(case=case, user=hr_actor, action=action) for action in (*HR_ACTIONS, *SETUP_AUTHORITY)]
    Grant.objects.bulk_create(grants)
    original_policy = payroll_helpers.policy

    def typed_policy(fixture, component, value):
        if component == ACCESS:
            for provider in value['providers']:
                provider.update(owner_id=maker.pk, owner_role='Finance')
        return original_policy(fixture, component, value)

    def capture(fixture, index):
        export = fixture['config']['exports'][index]
        return payroll.capture(maker, case.pk, fixture['request'].pk, export['provider'], f'sample-input-{index}',
                               payroll_helpers.body(fixture, index), rev(case))

    principals = {'preparer': maker, 'reviewer': reviewer, 'manager': aggregate_reader}
    with (
        patch.object(payroll_helpers, 'ACTIONS', tuple(dict.fromkeys((*MAKER_ACTIONS, *BASELINE_REVIEW_ACTIONS)))),
        patch.object(payroll_helpers, 'policy', side_effect=typed_policy),
        patch.object(payroll_helpers, 'capture', side_effect=capture),
    ):
        fixture = payroll_helpers.fixture(context=(hr_actor, case), principal=principals.__getitem__)
    for actor, permitted in ((maker, MAKER_ACTIONS), (reviewer, BASELINE_REVIEW_ACTIONS)):
        Grant.objects.filter(case=case, user=actor).exclude(action__in=permitted).update(active=False)
    combined = payroll_helpers.combined(fixture, 'sample-payroll-combine')
    payroll_helpers.approve(fixture, combined)
    snapshot = fixture['hr']
    match = payroll.match(maker, case.pk, combined.pk, snapshot.pk, 'sample-payroll-match', rev(case))
    payroll_helpers.approve(fixture, match)
    if (snapshot.actor_id != hr_actor.pk or match.metadata['status'] != 'complete'
            or any(item.actor_id != maker.pk for item in fixture['inputs'])):
        raise RuntimeError('The exact independent payroll and HR sources must produce the reviewed baseline.')
    return fixture, match


def seed(case, maker, hr_actor, suffix, identity):
    fixture, match = baseline(case, maker, hr_actor, suffix)
    payroll_helpers.policy(fixture, NAME_CHECK, {'comparison': 'exact_as_supplied', 'reader_ids': [maker.pk]})
    contracts = {side + '_contract_id': timing.record_source_contract(hr_actor, case.pk, side,
        f'sample-approved-{side}-sources-{suffix}', rev(case)).pk for side in ('employment', 'settlement')}
    payroll_helpers.policy(fixture, DEPARTURE_CHECK, {'check': {'entity': fixture['request'].metadata['entity'],
        'employment_holder_id': hr_actor.pk, 'settlement_holder_id': maker.pk, 'reviewer_id': hr_actor.pk,
        'reader_ids': [maker.pk], 'comparison': 'settlement_after_effective_instant',
        'proof_max_age_seconds': 86400, **contracts}})
    Grant.objects.filter(case=case, user=hr_actor, action__in=SETUP_AUTHORITY).update(active=False)
    chosen = fixture['inputs'][0]
    row = chosen.payload['rows'][0]
    if (names.assess(maker, case, match.pk, chosen.pk, row['row_ref'])[1]['result'] != 'awaiting_source'
            or Audit.objects.filter(case=case, action__in=(names.FACT, names.CHECK, timing.FACT, timing.CHECK)).exists()
            or PayrollPublication.objects.filter(request__case=case).exists()):
        raise RuntimeError('Leave both private facts and comparison decisions for the named test users.')
    return event(hr_actor, case, MARKER, **identity, input=chosen.pk, row=row['row_ref'], staff=row['employee_id'],
                 match=match.pk, hr_snapshot=fixture['hr'].pk, aggregate_reader=fixture['manager'].pk)


@transaction.atomic
def prepare(invitation_id, user_id):
    if os.getenv(GUARD) != '1':
        raise RuntimeError('Explicit synthetic payroll check preparation is required.')
    hr_actor = fixture_reviewer()
    admission, maker = admitted_user(invitation_id, user_id, hr_actor)
    require(maker, admission.invitation.case, 'case.read')
    suffix = str(invitation_id)
    properties = {'tenant': TENANT, 'title': f'SAMPLE independent payroll source checks {suffix}', 'kind': 'project',
                  'synthetic': True}
    case, created = Case.objects.get_or_create(pk=case_id(invitation_id), defaults=properties)
    if any(getattr(case, name) != expected for name, expected in properties.items()) or case.pk == admission.invitation.case_id:
        raise RuntimeError('Preserve any existing workspace outside the exact synthetic payroll case.')
    identity = {'invitation': invitation_id, 'admission': admission.pk, 'maker': maker.pk, 'hr': hr_actor.pk}
    marker = seed(case, maker, hr_actor, suffix, identity) if created else Audit.objects.get(
        case=case, actor=hr_actor, action=MARKER)
    if any(marker.data.get(name) != expected for name, expected in identity.items()):
        raise RuntimeError('The prepared case belongs to different admitted people.')
    return {**marker.data, 'case': str(case.pk), 'preserved': not created,
            'name_path': reverse('payroll_name_checks', args=[case.pk]) + f'?run={marker.data["match"]}',
            'timing_path': reverse('payroll_departure_check', args=[case.pk]),
            'hr_corrections_path': reverse('design_hr_payroll_corrections', args=[case.pk])}


def run(invitation_id, user_id):
    if (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'),
            os.getenv('RAILWAY_SERVICE_ID'), os.getenv(GUARD)) != (
            PREVIEW_PROJECT, 'design-acceptance', '00c14ca1-5361-4bee-97a5-2ec7aba6ef18', '1'):
        raise RuntimeError('Use the isolated Railway fixture checks service.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.lower().startswith('test_') or connection.vendor != 'postgresql':
        raise RuntimeError('Select the existing PostgreSQL preview database.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database()')
        if cursor.fetchone()[0] != database:
            raise RuntimeError('The original preview database must match the configured database.')
    print('PSL_ADMITTED_PAYROLL_SOURCE_CHECKS=' + json.dumps(prepare(invitation_id, user_id)), flush=True)
