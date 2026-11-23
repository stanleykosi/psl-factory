"""A guarded fresh input and match review journey for the admitted synthetic makers."""
from copy import deepcopy
import json
import os
from pathlib import Path
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import event
from apps.finance import payroll
from apps.finance.payroll_models import PayrollInput, PayrollPublication, PayrollReview
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.payroll_validators import ACCESS
from apps.policy.services import transition
from apps.workflows import factory_payroll as flow
from apps.workflows.models import FactoryWork
from tests import payroll_helpers
from tests.helpers import rev
from tests.railway_admitted_payroll_draft_seed import MAKER_ACTIONS, REVIEWER_ACTIONS, SOURCE_ACTIONS
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.railway_finance_schedule_seed import fixture_reviewer


GUARD = 'PSL_PAYROLL_REVIEW_WALKTHROUGH'
TENANT = 'design-payroll-return-walkthrough'
MARKER = 'sample.payroll_review_return_prepared'
MAKER_GRANTS = set(MAKER_ACTIONS) | {'factory.manage', 'payroll.capture'}
REVIEWER_GRANTS = set(REVIEWER_ACTIONS) | {'payroll.hr_correction', 'hrfinance.correction'}
FORMAT = {'format': 'csv', 'delimiter': ',', 'columns': {
    'row_ref': 'Ref', 'employee_id': 'Staff ID', 'component': 'Pay code', 'amount': 'Total',
}}
VALID_CSV = 'Ref,Staff ID,Pay code,Total\nB1,E002,BASIC,150\n'
REJECTED_CSV = 'Ref,Staff ID,Pay code,Total,Unapproved column\nB1,E002,BASIC,150,SYNTHETIC-UNAPPROVED-TEXT\n'
INPUT_NOTE = 'The fictional provider must replace the earlier export with the correct columns.'
MATCH_NOTE = 'Please verify the fictional staff matching before calculating totals.'


def seed(case, owner, maker, reviewer, suffix):
    recipient = get_user_model().objects.create_user(f'sample-payroll-return-aggregate-{suffix}')
    people = {'preparer': maker, 'reviewer': reviewer, 'manager': recipient}
    registry = payroll_helpers.policy

    def policy(fixture, component, value):
        value = deepcopy(value)
        if component == ACCESS:
            value['providers'][1].update(owner_id=maker.pk, owner_role='Finance')
        return registry(fixture, component, value)

    def capture(fixture, index):
        actor = maker if index == 1 else owner
        provider = fixture['config']['exports'][index]['provider']
        return payroll.capture(actor, case.pk, fixture['request'].pk, provider, f'sample-source-{index}',
                               payroll_helpers.body(fixture, index), rev(case))

    Grant.objects.bulk_create([Grant(case=case, user=owner, action=action) for action in SOURCE_ACTIONS])
    with (patch.object(payroll_helpers, 'ACTIONS', sorted(MAKER_GRANTS | REVIEWER_GRANTS)),
          patch.object(payroll_helpers, 'policy', side_effect=policy),
          patch.object(payroll_helpers, 'capture', side_effect=capture)):
        sample = payroll_helpers.fixture(context=(owner, case), principal=people.__getitem__,
                                         payroll_layouts=[FORMAT], preparer_receipt=False)
    for actor, permitted in ((maker, MAKER_GRANTS), (reviewer, REVIEWER_GRANTS)):
        Grant.objects.filter(case=case, user=actor).exclude(action__in=permitted).update(active=False)
    profile = json.loads(Path('fixtures/factory-payroll.json').read_text(encoding='utf-8'))
    profile.pop('classification')
    config = draft_operator_policy(owner, case.pk, 'OPS.factory_payroll_execution', profile,
                                   sample['e']['policy_decision'].pk, timezone.now())
    transition(owner, config.pk, 'validated')
    transition(owner, config.pk, 'active')
    inputs = [row.pk for row in sample['inputs']]
    work = flow.start(maker, case.pk, 'SAMPLE-PAYROLL-RETURN', sample['request'].pk,
                      {'input_ids': inputs, 'hr_snapshot_id': sample['hr'].pk},
                      'SAMPLE payroll input and staff match review', rev(case))
    if PayrollReview.objects.filter(request__case=case).exists():
        raise RuntimeError('Leave all input and working result review decisions for the two browser accounts.')
    return {'work': work.pk, 'request': sample['request'].pk, 'other_input': inputs[0],
            'original_input': inputs[1], 'provider': sample['inputs'][1].provider,
            'snapshot': sample['hr'].pk, 'review_proof': sample['e']['payroll_review'].pk,
            'hr_proof': sample['e']['hr_disclosure_decision'].pk, 'correction_proof': sample['e']['hr_correction_request'].pk,
            'recipient': recipient.pk}


@transaction.atomic
def prepare(invitation_id, user_id):
    if os.getenv(GUARD) != '1':
        raise RuntimeError('Use the explicit isolated Payroll review walkthrough guard.')
    reviewer = fixture_reviewer()
    admission, maker = admitted_user(invitation_id, user_id, reviewer)
    require(maker, admission.invitation.case, 'case.read')
    cid = uuid5(NAMESPACE_URL, f'{TENANT}:{admission.pk}:{maker.pk}')
    attrs = {'tenant': TENANT, 'title': f'SAMPLE payroll reviews for admission {admission.pk}',
             'kind': 'project', 'synthetic': True}
    case, created = Case.objects.get_or_create(pk=cid, defaults=attrs)
    if any(getattr(case, key) != value for key, value in attrs.items()) or case.pk == admission.invitation.case_id:
        raise RuntimeError('Use only the distinct synthetic Payroll review workspace.')
    identity = {'admission': admission.pk, 'invitation': invitation_id, 'maker': maker.pk, 'reviewer': reviewer.pk}
    username = f'sample-payroll-return-source-{admission.pk}'
    if created:
        owner = get_user_model().objects.create_user(username)
        marker = event(owner, case, MARKER, **identity, **seed(case, owner, maker, reviewer, admission.pk))
    else:
        marker = Audit.objects.select_related('actor').get(case=case, actor__username=username, action=MARKER)
    if (any(marker.data[key] != value for key, value in identity.items()) or marker.actor.has_usable_password()
            or marker.actor.is_staff or marker.actor.is_superuser or not marker.actor.is_active
            or Grant.objects.filter(user=marker.actor).exclude(case=case).exists()):
        raise RuntimeError('Preserve exact admitted walkthrough identities and the non-interactive HR source holder.')
    for actor, permitted in ((maker, MAKER_GRANTS), (reviewer, REVIEWER_GRANTS)):
        if set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True)) != permitted:
            raise RuntimeError('Preserve the case-local payroll owner and reviewer actions.')
    data = marker.data
    work = FactoryWork.objects.get(pk=data['work'], case=case, actor=maker, definition=flow.DEFINITION)
    PayrollInput.objects.get(pk=data['original_input'], request_id=data['request'], request__case=case,
                             provider=data['provider'], actor=maker, metadata__accepted=True)
    if PayrollPublication.objects.filter(request__case=case).exists():
        raise RuntimeError('This walkthrough ends before payroll totals or publication.')
    return {**data, 'case': str(case.pk), 'preserved': not created,
            'work_path': reverse('factory_detail', args=[work.pk]),
            'decision': reverse('factory_invoice_decision', args=[work.pk]),
            'recovery': reverse('factory_invoice_recovery', args=[work.pk]),
            'inputs_page': reverse('design_payroll_inputs', args=[case.pk])}


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
            raise RuntimeError('The configured preview database must match the current connection.')
    if not MigrationRecorder(connection).migration_qs.filter(app='finance', name='0086_payroll_review_note').exists():
        raise RuntimeError('Apply the verified private review note migration first.')
    print(GUARD + '=' + json.dumps(prepare(invitation_id, user_id)), flush=True)
