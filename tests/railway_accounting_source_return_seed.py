"""Prepare an original trial balance for independent return and changed-file intake."""
import json
import os
from pathlib import Path
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.finance import analysis
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.role_assignments import draft as draft_roles
from apps.policy.services import transition
from apps.workflows import factory, factory_accounting as accounting
from apps.workflows.factory_accounting_corrections import url as correction_url
from apps.workflows.models import FactoryWork, HumanTask
from tests import finance_analysis_helpers
from tests.helpers import rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_closure_walkthrough_seed import ADMITTED_IDENTITY, ADMITTED_STAFF_CASE, ADMITTED_USERNAME, PREVIEW_PROJECT


GUARD = 'PSL_ACCOUNTING_SOURCE_RETURN_WALKTHROUGH'
TENANT = 'design-accounting-source-return-walkthrough'
TITLE = 'SAMPLE accounting source that needs a corrected extract'
KEY = 'SAMPLE-ACCOUNTS-SOURCE-CORRECTION'
MARKER = 'sample.accounting_source_return_prepared'
CSV_PATH = 'fixtures/design-sample-accounts-corrected.csv'
RETURN_REASON = 'The supplied direct cost includes an extra amount. Ask for the corrected October extract.'
CORRECTED_TOTAL = '-110.99'
MAKER_ACTIONS = ('case.read', 'factory.read', 'factory.start', 'factory.execute', 'finance.read',
                 'finance.import', 'finance.validate', 'finance.source', 'finance.calculate', 'evidence.add',
                 'agent.finance')
REVIEWER_ACTIONS = ('case.read', 'factory.read', 'finance.read', 'finance.review')


def prepare_original(case, maker, reviewer, identity):
    owner = get_user_model().objects.create_user(f'sample-accounting-source-return-sponsor-{case.pk.hex[:8]}')
    Grant.objects.bulk_create([Grant(case=case, user=actor, action=action) for actor, actions in (
        (owner, dict.fromkeys(ACTIONS)), (maker, MAKER_ACTIONS), (reviewer, REVIEWER_ACTIONS),
    ) for action in actions])
    with patch.object(finance_analysis_helpers, 'setup_case', return_value=(owner, case)):
        _, _, evidence, data, _, original, template, _ = finance_analysis_helpers.fixture(
            review=False, recipient_username=f'sample-returned-accounts-reader-{case.pk.hex[:8]}')
    role = draft_roles(owner, case.pk, [{'role': 'Finance', 'user_id': reviewer.pk}], evidence['policy_decision'].pk, timezone.now())
    transition(owner, role.pk, 'validated')
    transition(owner, role.pk, 'active')
    for row in data['authority']['finance']:
        row['allow_preparer_review'] = False
    finance_analysis_helpers.policy(owner, case, 'D05.decision_action_matrix', data['authority'], evidence['policy_decision'])
    source = analysis.capture_source(maker, case.pk, original.batch_id, original.entity, original.accounting_basis,
        original.extracted_at, original.completeness, original.control_total, original.evidence_id, rev(case),
        unit_declaration=original.unit_declaration)
    profile = json.loads((settings.BASE_DIR / 'fixtures/factory-accounting.json').read_text(encoding='utf-8'))
    profile.pop('classification')
    profile.update(allocation_mode='company_only', bu_metrics=None, executor_id=None,
                   information_resolver_id=None, template_id=template.pk)
    config = draft_operator_policy(owner, case.pk, 'OPS.factory_accounting_execution', profile,
                                   evidence['policy_decision'].pk, timezone.now())
    transition(owner, config.pk, 'validated')
    transition(owner, config.pk, 'active')
    work = accounting.start(maker, case.pk, KEY, source.pk, [], TITLE, rev(case))
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    task = HumanTask.objects.get(case=case, kind='factory_accounting_review', status='open',
                                context__work=work.pk, context__purpose='source')
    if task.claimed_by_id or {item['id'] for item in task.context['packet']['candidates']} != {reviewer.pk}:
        raise RuntimeError('Leave the exact original source decision open for the independent Trial reviewer.')
    context = add_evidence(owner, case.pk, 'finance_source',
        'The sample corrected October trial balance is a same-basis extraction in individual naira. Its declared control total is −110.99.',
        'synthetic:accounting-corrected-extract-context')
    return event(owner, case, MARKER, **identity, work=work.pk, source=source.pk, batch=source.batch_id,
                 source_task=task.pk, review_proof=evidence['finance_review'].pk, extraction_proof=context.pk,
                 extracted_at=timezone.now().replace(microsecond=0).isoformat())


@transaction.atomic
def prepare(invitation_id, user_id, *, hosted=False):
    reviewer = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    admission, maker = admitted_user(invitation_id, user_id, reviewer)
    if hosted and (admission.invitation.case_id, maker.username) != (ADMITTED_STAFF_CASE, ADMITTED_USERNAME):
        raise RuntimeError('Match the exact accepted synthetic accounting preparer.')
    identity = {'invitation': invitation_id, 'admission': admission.pk, 'maker': maker.pk, 'reviewer': reviewer.pk}
    case_id = uuid5(NAMESPACE_URL, f'{TENANT}/{admission.pk}/{maker.pk}/{reviewer.pk}')
    case, created = Case.objects.get_or_create(pk=case_id, defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Preserve the unrelated workspace occupying the correction sample case.')
    marker = prepare_original(case, maker, reviewer, identity) if created else Audit.objects.get(case=case, action=MARKER)
    if any(marker.data[key] != value for key, value in identity.items()):
        raise RuntimeError('Preserve the sample’s exact admitted preparer and separate Finance reviewer.')
    work = FactoryWork.objects.get(case=case, actor=maker, definition=accounting.DEFINITION, key=KEY, pk=marker.data['work'])
    return {**marker.data, 'case': str(case.pk), 'return_reason': RETURN_REASON, 'csv': CSV_PATH,
            'control_total': CORRECTED_TOTAL, 'preserved': not created,
            'decision': reverse('factory_invoice_decision', args=[work.pk]),
            'recovery': reverse('factory_invoice_recovery', args=[work.pk]), 'correction': correction_url(work)}


def run():
    actual = os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv(GUARD)
    database = os.getenv('PGDATABASE', '')
    if actual != (PREVIEW_PROJECT, 'design-acceptance', '1') or not database or database.startswith('test_'):
        raise RuntimeError('The isolated Railway preview and returned accounting source fixture guard are required.')
    if not Path(settings.BASE_DIR, CSV_PATH).is_file():
        raise RuntimeError('Use the checked-in fictional corrected extract.')
    print(GUARD + '=' + json.dumps(prepare(*ADMITTED_IDENTITY, hosted=True), sort_keys=True), flush=True)
