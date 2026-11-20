"""Prepare a fresh synthetic Finance intake for an already admitted test user."""

import json
from functools import partial
from urllib.parse import urlencode
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from apps.core.models import Audit, Case
from apps.core.services import event
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant, StaffAdmission
from apps.workflows import factory_schedules as schedules
from apps.workflows.models import FactoryWork
from tests import finance_analysis_helpers, schedule_helpers, test_factory_schedules
from tests.railway_finance_schedule_seed import fixture_reviewer


ADMISSION_TENANT = 'design-staff-account-walkthrough'
ADMISSION_PROFILE = 'sample-workspace-reader'
TENANT = 'design-admitted-schedule-row-walkthrough'
MARKER = 'sample.schedule_row_intake_prepared'
MAKER_ACTIONS = ('case.read', 'evidence.add', 'finance.calculate', 'finance.read', 'factory.read', 'factory.start',
                 'factory.execute', 'factory.manage', 'schedules.prepare', 'schedules.read', 'schedules.report')


def admitted_user(invitation_id, user_id, reviewer):
    if any(type(pk) is not int or pk < 1 for pk in (invitation_id, user_id)) or user_id == reviewer.pk:
        raise RuntimeError('Match an explicit accepted sample invitation and its distinct admitted user.')
    # Fixture setup serializes changes to this admission and account while ordinary
    # workflow writes can still commit foreign keys to the existing account.
    admission = StaffAdmission.objects.select_for_update(of=('self', 'user'), no_key=True).select_related(
        'user', 'invitation__case', 'invitation__authority',
    ).filter(invitation_id=invitation_id, user_id=user_id, invitation__case__tenant=ADMISSION_TENANT,
             invitation__case__synthetic=True, invitation__profile_key=ADMISSION_PROFILE,
             user__is_active=True, user__is_staff=False, user__is_superuser=False).first()
    if admission is None:
        raise RuntimeError('No exact matching accepted synthetic invitation and active ordinary account.')
    invitation, maker = admission.invitation, admission.user
    accepted = Audit.objects.filter(case=invitation.case, actor=maker, action='staff.invitation_accepted',
                                    data={'invitation': invitation_id}).exists()
    if (not accepted or not maker.has_usable_password() or maker.username != invitation.username
            or invitation.actions != ['case.read'] or invitation.authority.value['classification'] != 'synthetic'):
        raise RuntimeError('Recorded native acceptance and a usable unchanged sample sign-in are required.')
    return admission, maker


@transaction.atomic
def prepare(invitation_id, user_id):
    reviewer = fixture_reviewer()
    admission, maker = admitted_user(invitation_id, user_id, reviewer)
    reference = f'sample-invited-income-row-{invitation_id}'
    case, created = Case.objects.get_or_create(tenant=TENANT, title=f'SAMPLE accepted-invitation row review {invitation_id}',
                                               kind='project', synthetic=True)
    if case.pk == admission.invitation.case_id:
        raise RuntimeError('A separate synthetic Finance workspace is required.')
    owner_username = f'batch-schedule-invitation-{invitation_id}-setup'
    identity = {'invitation': invitation_id, 'admission': admission.pk, 'maker': maker.pk, 'reviewer': reviewer.pk}
    if created:
        owner = get_user_model().objects.create_user(owner_username)
        Grant.objects.bulk_create([Grant(user=owner, case=case, action=action) for action in dict.fromkeys(ACTIONS)])
        with (
            patch.object(finance_analysis_helpers, 'setup_case', return_value=(owner, case)),
            patch.object(test_factory_schedules, 'fixture', side_effect=partial(
                schedule_helpers.fixture, reviewer=reviewer, recipient_username=f'{owner_username}-reader',
            )),
        ):
            sample = test_factory_schedules.FactorySchedulesTests()
            sample.setUp()
        row = dict(schedule_helpers.row(sample.f, 'row-12', '0'), duplicate_state='separately_justified')
        source = schedule_helpers.evidence(sample.f, 'income_detail', json.dumps(
            dict(sample.payload, rows=[*sample.payload['rows'], row]),
        ))
        Grant.objects.bulk_create([Grant(user=maker, case=case, action=action) for action in MAKER_ACTIONS])
        marker = event(owner, case, MARKER, **identity, mapping=sample.f['parent'].pk, source=source.pk,
                       review_evidence=sample.f['e']['finance_review'].pk)
    else:
        marker = Audit.objects.get(case=case, action=MARKER, actor__username=owner_username)
        if any(marker.data.get(key) != value for key, value in identity.items()):
            raise RuntimeError('The existing fixture belongs to a different exact admission or reviewer.')

    current = FactoryWork.objects.filter(case=case, definition=schedules.DEFINITION, request__reference=reference)
    previous = current.filter(actor=maker).values_list('pk', flat=True).first()
    if current.exclude(actor=maker).exists():
        raise RuntimeError('The exact reference already belongs to a different preparer. Preserve it for review.')
    return {'case': str(case.pk), 'maker': maker.username, 'reference': reference, 'row': 'row-12',
            'source': marker.data['source'], 'mapping': marker.data['mapping'],
            'review_evidence': marker.data['review_evidence'], 'existing_work': previous,
            'start_path': reverse('factory_create') + '?' + urlencode({'definition': schedules.DEFINITION, 'case': case.pk})}


def run(invitation_id, user_id):
    print('PSL_FINANCE_ADMITTED_SCHEDULE_FIXTURE=' + json.dumps(prepare(invitation_id, user_id)), flush=True)
