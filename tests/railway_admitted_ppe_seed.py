"""Prepare distinct asset-schedule intake for the existing admitted sample preparer."""

import json
from functools import partial
from urllib.parse import urlencode
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from apps.core.models import Audit, Case
from apps.core.services import event
from apps.finance import ppe
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.workflows import factory_ppe as flow
from apps.workflows.models import FactoryWork
from tests import finance_analysis_helpers, ppe_helpers, test_factory_ppe
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_finance_schedule_seed import fixture_reviewer


TENANT = 'design-admitted-ppe-opening-walkthrough'
MARKER = 'sample.ppe_opening_intake_prepared'
MAKER_ACTIONS = ('case.read', 'evidence.add', 'factory.execute', 'factory.manage', 'factory.read', 'factory.start',
                 'finance.calculate', 'finance.read', 'ppe.capture', 'ppe.prepare', 'ppe.read', 'ppe.report')


@transaction.atomic
def prepare(invitation_id, user_id):
    reviewer = fixture_reviewer()
    admission, maker = admitted_user(invitation_id, user_id, reviewer)
    reference = f'sample-admitted-asset-proof-{invitation_id}'
    case, created = Case.objects.get_or_create(tenant=TENANT, title=f'SAMPLE separate asset proof review {invitation_id}',
                                               kind='project', synthetic=True)
    if case.pk == admission.invitation.case_id:
        raise RuntimeError('A separate synthetic asset workspace is required.')
    owner_username = f'batch-ppe-proof-invitation-{invitation_id}-setup'
    identities = {'invitation': invitation_id, 'admission': admission.pk, 'maker': maker.pk, 'reviewer': reviewer.pk}
    if created:
        owner = get_user_model().objects.create_user(owner_username)
        Grant.objects.bulk_create([Grant(user=owner, case=case, action=action) for action in dict.fromkeys(ACTIONS)])
        with (
            patch.object(finance_analysis_helpers, 'setup_case', return_value=(owner, case)),
            patch.object(test_factory_ppe, 'fixture', side_effect=partial(
                ppe_helpers.fixture, reviewer=reviewer, recipient_username=f'{owner_username}-reader',
            )),
        ):
            sample = test_factory_ppe.FactoryPPETests()
            sample.setUp()
        data = sample.f
        permissions = ppe.config(case, ppe.AUTH)
        if not permissions['independent_reviewer'] or not any(
            assignment['user_id'] == reviewer.pk and {'register', 'schedule'} <= set(assignment['purposes'])
            for assignment in permissions['assignments']
        ):
            raise RuntimeError('The existing synthetic policy must authorize an independent source and output reviewer.')
        Grant.objects.bulk_create([Grant(user=maker, case=case, action=action) for action in MAKER_ACTIONS])
        marker = event(owner, case, MARKER, **identities, register=data['register'].pk, mapping=data['parent'].pk,
                       review_evidence=data['e']['finance_review'].pk)
    else:
        marker = Audit.objects.get(case=case, action=MARKER, actor__username=owner_username)
        if any(marker.data.get(key) != value for key, value in identities.items()):
            raise RuntimeError('Preserve the fixture bound to a different exact admission or reviewer.')

    current = FactoryWork.objects.filter(case=case, definition=flow.DEFINITION, request__reference=reference)
    previous = current.filter(actor=maker).values_list('pk', flat=True).first()
    if current.exclude(actor=maker).exists():
        raise RuntimeError('The existing asset work has a different original preparer.')
    return {'case': str(case.pk), 'preparer': maker.username, 'reference': reference, 'register': marker.data['register'],
            'mapping': marker.data['mapping'], 'review_evidence': marker.data['review_evidence'], 'existing_work': previous,
            'start_path': reverse('factory_create') + '?' + urlencode({'definition': flow.DEFINITION, 'case': case.pk})}


def run(invitation_id, user_id):
    print('PSL_FINANCE_ADMITTED_PPE_FIXTURE=' + json.dumps(prepare(invitation_id, user_id)), flush=True)
