"""Isolated reporting-period review for the existing admitted sample asset preparer."""

import json
import os
from datetime import date, timedelta
from functools import partial
from unittest.mock import patch
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.finance import ppe
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.workflows import factory_ppe as flow
from apps.workflows.models import FactoryWork
from tests import finance_analysis_helpers, ppe_helpers, schedule_helpers, test_factory_ppe
from tests.helpers import rev
from tests.railway_admitted_ppe_seed import MAKER_ACTIONS
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_finance_schedule_seed import fixture_reviewer


GUARD = 'PSL_ADMITTED_PPE_REPORTING_DATES_WALKTHROUGH'
TENANT = 'design-admitted-ppe-reporting-dates-walkthrough'
MARKER = 'sample.ppe_reporting_dates_intake_prepared'
REVIEWER_ACTIONS = ('case.read', 'factory.read', 'finance.read', 'ppe.read', 'ppe.report', 'ppe.review')
CORRECTED_SOURCE = 'synthetic:asset-reporting-period-clarification'


@transaction.atomic
def prepare(invitation_id, user_id):
    if os.getenv(GUARD) != '1':
        raise RuntimeError('Explicit opt-in for the isolated asset reporting-period walkthrough is required.')
    reviewer = fixture_reviewer()
    admission, maker = admitted_user(invitation_id, user_id, reviewer)
    reference = f'sample-admitted-asset-dates-{invitation_id}'
    case, created = Case.objects.get_or_create(tenant=TENANT, title=f'SAMPLE asset reporting dates {invitation_id}',
                                               kind='project', synthetic=True)
    if case.pk == admission.invitation.case_id:
        raise RuntimeError('A separate synthetic asset workspace is required.')
    owner_username = f'batch-ppe-dates-invitation-{invitation_id}-setup'
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
            raise RuntimeError('Separate exact independent Finance review authority is required.')
        Grant.objects.bulk_create([Grant(case=case, user=maker, action=action) for action in MAKER_ACTIONS])
        body = data['register'].payload.copy()
        body['label_as_of'] = (date.fromisoformat(body['period_start']) - timedelta(days=1)).isoformat()
        original = add_evidence(maker, case.pk, 'ppe_register', json.dumps(body), 'synthetic:asset-reporting-period')
        register = ppe.capture(maker, case.pk, reference, original.pk, rev(case))
        if not register.result['date_basis_ambiguous']:
            raise RuntimeError('The exact supplied register must require an independent reporting-period review.')
        basis = add_evidence(maker, case.pk, 'ppe_basis_explanation',
                             f'Synthetic reporting dates for register {register.pk}. Its printed label is '
                             f'{body["label_as_of"]}. The source handoff leaves the reporting cut-off unresolved.',
                             'synthetic:asset-reporting-period-initial')
        marker = event(owner, case, MARKER, **identities, register=register.pk, original=original.pk,
                       mapping=data['parent'].pk, review_evidence=data['e']['finance_review'].pk,
                       initial_basis=basis.pk, label=body['label_as_of'], period_start=body['period_start'],
                       period_end=body['period_end'])
    else:
        marker = Audit.objects.get(case=case, action=MARKER, actor__username=owner_username)
        if any(marker.data.get(key) != value for key, value in identities.items()):
            raise RuntimeError('Preserve the existing sample bound to a different role or admission.')

    current = FactoryWork.objects.filter(case=case, definition=flow.DEFINITION, request__reference=reference)
    if current.exclude(actor=maker).exists():
        raise RuntimeError('Preserve the existing asset work with a different preparer.')
    details = {key: value for key, value in marker.data.items() if key not in identities}
    return {'case': str(case.pk), 'preparer': maker.username, 'reference': reference, **details,
            'existing_work': current.values_list('pk', flat=True).first(),
            'start_path': reverse('factory_create') + '?' + urlencode({'definition': flow.DEFINITION, 'case': case.pk}),
            'evidence_path': reverse('case', args=[case.pk])}


def corrected_explanation(sample):
    return (f'Synthetic asset reporting dates for register {sample["register"]}. Retain the supplied label '
            f'{sample["label"]}. The supplied reporting period is {sample["period_start"]} through '
            f'{sample["period_end"]}. Asset values, useful lives and supplied fractions stay the same.')


def run(invitation_id, user_id):
    print('PSL_FINANCE_ADMITTED_PPE_DATE_FIXTURE=' + json.dumps(prepare(invitation_id, user_id)), flush=True)
