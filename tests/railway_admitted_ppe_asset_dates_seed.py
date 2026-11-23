"""Prepare synthetic sources for the independently reviewed per-asset dates walkthrough."""

import json
import os
from functools import partial
from urllib.parse import urlencode
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.urls import reverse

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.finance import ppe, ppe_dates
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy.services import resolve
from apps.workflows import factory_ppe as flow
from apps.workflows.models import FactoryWork
from tests import finance_analysis_helpers, ppe_helpers, schedule_helpers, test_factory_ppe
from tests.helpers import rev
from tests.railway_admitted_ppe_seed import MAKER_ACTIONS as PPE_MAKER_ACTIONS
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_finance_schedule_seed import fixture_reviewer


GUARD = 'PSL_ADMITTED_PPE_ASSET_DATES_WALKTHROUGH'
TENANT = 'design-admitted-ppe-asset-dates-walkthrough'
MARKER = 'sample.ppe_asset_dates_prepared'
ORACLE_SOURCE = 'synthetic:ppe-browser-independent-date-example'
MAKER_ACTIONS = (*PPE_MAKER_ACTIONS, 'policy.read', 'policy.configure')
REVIEWER_ACTIONS = (*ppe.READ_ACTIONS, 'factory.read', 'ppe.report', 'ppe.review', 'evidence.add',
                    'policy.read', 'policy.activate')


def configuration(sample, oracle_id):
    scope = {key: sample[key] for key in ('category', 'period_start', 'period_end')}
    return {'method_evidence_id': sample['method'], 'oracle_evidence_id': oracle_id,
            'rules': [dict(scope, in_service_from=sample['in_service_date'],
                           in_service_through=sample['last_covered_date'], fraction='1')],
            'oracles': [dict(scope, in_service_date=sample['in_service_date'], expected_fraction='1'),
                        dict(scope, in_service_date=sample['first_uncovered_date'], expected_fraction=None)]}


def oracle_body(sample):
    return json.dumps({'contract': ppe_dates.ORACLE_CONTRACT, 'cases': configuration(sample, None)['oracles']})


@transaction.atomic
def prepare(invitation_id, user_id):
    if os.getenv(GUARD) != '1':
        raise RuntimeError('Explicit opt-in for the isolated asset dates walkthrough is required.')
    reviewer = fixture_reviewer()
    admission, maker = admitted_user(invitation_id, user_id, reviewer)
    if not MigrationRecorder(connection).migration_qs.filter(app='workflows', name='0095_ppe_asset_dates').exists():
        raise RuntimeError('The verified asset date checks must already be applied to the preview database.')
    reference = f'sample-admitted-individual-asset-dates-{invitation_id}'
    case, created = Case.objects.get_or_create(tenant=TENANT, title=f'SAMPLE individual asset dates {invitation_id}',
                                               kind='project', synthetic=True)
    if case.pk == admission.invitation.case_id:
        raise RuntimeError('A separate synthetic asset workspace is required.')
    owner_username = f'batch-ppe-asset-dates-{invitation_id}-setup'
    identities = {'invitation': invitation_id, 'admission': admission.pk, 'maker': maker.pk, 'reviewer': reviewer.pk}
    if created:
        owner = get_user_model().objects.create_user(owner_username)
        Grant.objects.bulk_create([Grant(case=case, user=owner, action=action) for action in dict.fromkeys(ACTIONS)])
        with (
            patch.object(finance_analysis_helpers, 'setup_case', return_value=(owner, case)),
            patch.object(schedule_helpers, 'ACTIONS', REVIEWER_ACTIONS),
            patch.object(test_factory_ppe, 'fixture', side_effect=partial(
                ppe_helpers.fixture, reviewer=reviewer, recipient_username=f'{owner_username}-reader',
            )),
        ):
            sample = test_factory_ppe.FactoryPPETests()
            sample.setUp()
        data = sample.f
        policy = ppe.config(case, ppe.AUTH)
        if not policy['independent_reviewer'] or not any(
            row['user_id'] == reviewer.pk and {'register', 'basis', 'schedule'} <= set(row['purposes'])
            for row in policy['assignments']
        ):
            raise RuntimeError('Separate review assignments for the exact asset case are required.')
        Grant.objects.bulk_create([Grant(case=case, user=maker, action=action) for action in MAKER_ACTIONS])
        body = data['register'].payload
        asset, = body['assets']
        if asset.get('dates') or asset['fraction'] != '1' or (body['period_start'], body['period_end']) != (
                '2026-10-01', '2026-10-20'):
            raise RuntimeError('The exact ordinary synthetic October asset source is required.')
        original = add_evidence(maker, case.pk, 'ppe_register', json.dumps(body), 'synthetic:asset-date-demo-register')
        register = ppe.capture(maker, case.pk, reference, original.pk, rev(case))
        missing = add_evidence(maker, case.pk, 'ppe_event',
                               'Synthetic asset A1 delivery note. Delivered on 2 October 2026. In-service date pending.',
                               'synthetic:asset-date-demo-delivery')
        supplied = add_evidence(maker, case.pk, 'ppe_event',
                                'Synthetic asset A1 commissioning note. Delivered on 2 October and in service on 10 October 2026.',
                                'synthetic:asset-date-demo-commissioning')
        explanation = add_evidence(maker, case.pk, 'ppe_basis_explanation',
                                   'Synthetic review of the separate delivery and commissioning facts for asset A1 within the October sample.',
                                   'synthetic:asset-date-demo-basis')
        method = add_evidence(maker, case.pk, 'ppe_policy',
                              'Synthetic rule for this walkthrough only. Equipment in service 10 through 12 October 2026 '
                              'uses an explicit fraction of 1 for the supplied 1 through 20 October 2026 reporting period. '
                              'Other dates are uncovered. Existing asset life, rate and rounding remain as supplied.',
                              'synthetic:asset-date-demo-rule')
        if resolve(ppe_dates.COMPONENT, case).status != 'MISSING':
            raise RuntimeError('The optional date fraction policy must be unset before the walkthrough.')
        marker = event(owner, case, MARKER, **identities, register=register.pk, original=original.pk,
                       mapping=data['parent'].pk, review_evidence=data['e']['finance_review'].pk,
                       basis_evidence=explanation.pk, missing_support=missing.pk, supplied_support=supplied.pk,
                       method=method.pk, policy_evidence=data['e']['policy_decision'].pk, asset=asset['asset_id'],
                       category=asset['category'], period_start=body['period_start'], period_end=body['period_end'],
                       delivery_date='2026-10-02', in_service_date='2026-10-10', last_covered_date='2026-10-12',
                       first_uncovered_date='2026-10-13')
    else:
        marker = Audit.objects.get(case=case, action=MARKER, actor__username=owner_username)
        if any(marker.data.get(key) != value for key, value in identities.items()):
            raise RuntimeError('Preserve the existing sample bound to a different admission or role.')

    work = FactoryWork.objects.filter(case=case, definition=flow.DEFINITION, request__register_reference=reference)
    if work.exclude(actor=maker).exists():
        raise RuntimeError('Preserve the original asset work owner.')
    details = {key: value for key, value in marker.data.items() if key not in identities}
    return {'case': str(case.pk), 'preparer': maker.username, 'reference': reference, **details,
            'existing_work': work.values_list('pk', flat=True).first(),
            'start_path': reverse('factory_create') + '?' + urlencode({'definition': flow.DEFINITION, 'case': case.pk}),
            'asset_path': reverse('ppe', args=[case.pk]), 'evidence_path': reverse('case', args=[case.pk]),
            'policy_path': reverse('policy', args=[case.pk])}


def run(invitation_id, user_id):
    sample = prepare(invitation_id, user_id)
    print('PSL_FINANCE_ADMITTED_PPE_ASSET_DATES_FIXTURE=' + json.dumps({**sample, 'oracle_body': oracle_body(sample),
          'oracle_source': ORACLE_SOURCE, 'policy_content': configuration(sample, 0)}), flush=True)
