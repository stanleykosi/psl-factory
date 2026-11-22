"""Add distinct synthetic invoice delegation and receipt recovery browser stations."""

import json
import os
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from adapters.factory_invoices import MockFactoryInvoiceAdapter
from apps.core.models import Audit, Case, Evidence
from apps.core.services import add_evidence
from apps.finance import invoice_delivery
from apps.finance.models import InvoiceIssue, InvoiceJob, InvoiceReview
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy import role_assignments
from apps.policy.factory_routing_validators import COMPONENT
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory
from apps.workflows.factory_routing import review_capabilities
from apps.workflows.models import FactoryWork, HumanTask
from tests import factory_helpers
from tests.helpers import rev
from tests.obligation_helpers import factory_approve_identified, factory_identified
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT


TENANT = 'design-invoice-authority-recovery-walkthrough'
DELEGATION_CASE = 'SAMPLE delegated Finance packet decision'
RECOVERY_CASE = 'SAMPLE exact invoice receipt after a delayed observation'
WITNESS_KIND = 'agent_private_invoice_recovery_witness'
REVIEW_GRANTS = ('case.read', 'finance.read', 'factory.read', 'finance.invoice.review', 'policy.read')


def require_sample_account():
    environment = (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'),
                   os.getenv('PSL_COMPOSED_WALKTHROUGH'))
    if environment != (PREVIEW_PROJECT, 'design-acceptance', '1'):
        raise RuntimeError('Exact Railway acceptance project and fixture guard required')
    return get_user_model().objects.get(username='psl-agent-trial', is_active=True,
                                        is_staff=False, is_superuser=False)


def sample_work(case):
    return FactoryWork.objects.select_related('invoice', 'case').get(
        case=case, definition='pmo-finance/v1', key='FACTORY-EXAMPLE')


@transaction.atomic
def prepare_delegation():
    delegate = require_sample_account()
    case, created = Case.objects.get_or_create(tenant=TENANT, title=DELEGATION_CASE, kind='project', synthetic=True)
    if not created:
        work = sample_work(case)
        return delegated_station(work, preserved=True)

    maker = get_user_model().objects.create_user('batch-delegated-invoice-maker')
    Grant.objects.bulk_create([Grant(user=maker, case=case, action=action) for action in dict.fromkeys(ACTIONS)] +
                              [Grant(user=delegate, case=case, action=action) for action in REVIEW_GRANTS])
    with patch.object(factory_helpers, 'setup_case', return_value=(maker, case)):
        data = factory_helpers.fixture(max_age_seconds=7 * 86400, responsibility=False)
    settings = json.loads(Path('fixtures/factory-finance-delegation.json').read_text(encoding='utf-8'))
    if settings['classification'] != 'synthetic_test_only':
        raise RuntimeError('Use only the existing synthetic delegation limits')
    now = timezone.now()
    start, end = now - timedelta(minutes=1), now + timedelta(seconds=settings['window_seconds'])
    value = {'role': settings['role'], 'principal_id': maker.pk, 'delegate_id': delegate.pk,
             'valid_from': start.isoformat(), 'valid_until': end.isoformat(),
             'delegate_eligibility': {'roles': settings['delegate_eligibility_roles'],
                                      'valid_from': start.isoformat(), 'valid_until': end.isoformat()},
             'decision_scope': {**settings['decision_scope'], 'case_ref': str(case.pk)}}
    proof = data['evidence']['policy_decision']
    delegated = role_assignments.draft_delegations(maker, case.pk, [value], proof.pk, start)
    owners = {name: maker.pk for name in ('process_owner_id', 'activity_owner_id', 'policy_owner_id', 'governance_resolver_id')}
    owners.update(definition='pmo-finance/v1', process_id='F30', activity='ACT10', method=settings['method'],
                  authority_mode=settings['authority_mode'])
    routing = draft_operator_policy(maker, case.pk, COMPONENT, owners, proof.pk, now)
    for configuration in [delegated, routing]:
        transition(maker, configuration.pk, 'validated')
        transition(maker, configuration.pk, 'active')
    factory.run_until_wait(data['work'].pk)
    work = factory_identified(data)
    capabilities = review_capabilities(work, delegate)
    if capabilities != {'delegated': True, 'verdicts': ['approve']} or InvoiceReview.objects.filter(invoice=work.invoice).exists():
        raise RuntimeError('The sample needs an unrecorded and bounded exact delegate decision')
    return {**delegated_station(work, preserved=False), 'proof': data['proof'].pk,
            'delegation': delegated.pk, 'valid_until': end.isoformat()}


def delegated_station(work, *, preserved):
    task = HumanTask.objects.filter(case=work.case, kind='factory_review', status='open').order_by('-pk').first()
    return {'work': work.pk, 'case': str(work.case_id), 'invoice': work.invoice_id,
            'task': task.pk if task else None, 'preserved': preserved,
            'decision_path': reverse('factory_invoice_decision', args=[work.pk]),
            'delegation_path': reverse('design_delegation', args=[work.case_id])}


@transaction.atomic
def reserve_recovery(trial):
    case, created = Case.objects.get_or_create(tenant=TENANT, title=RECOVERY_CASE, kind='project', synthetic=True)
    if not created:
        return sample_work(case), None
    Grant.objects.bulk_create([Grant(user=trial, case=case, action=action) for action in dict.fromkeys(ACTIONS)])
    with patch.object(factory_helpers, 'setup_case', return_value=(trial, case)):
        data = factory_helpers.fixture(max_age_seconds=7 * 86400)
    factory.run_until_wait(data['work'].pk)
    factory_approve_identified(data)
    factory.run_once(data['work'].pk)
    work = sample_work(case)
    job = InvoiceJob.objects.get(invoice=work.invoice, kind='issue')
    lease = invoice_delivery.claim(case_id=case.pk, job_id=job.pk)
    if not lease or job.status != 'pending' or InvoiceIssue.objects.filter(invoice=work.invoice).exists():
        raise RuntimeError('Expected a fresh exact invoice reservation with no prior receipt')
    return work, lease


def prepare_recovery():
    trial = require_sample_account()
    work, lease = reserve_recovery(trial)
    job = InvoiceJob.objects.select_related('invoice__case').get(invoice=work.invoice, kind='issue', generation=1)
    if lease:
        invoice_delivery.dispatch_context(*lease)
        with TemporaryDirectory(prefix='psl-invoice-acceptance-') as directory:
            adapter = MockFactoryInvoiceAdapter(directory, lose_response=True)
            try:
                adapter.deliver(*lease)
            except TimeoutError:
                witness = adapter.path(job).read_text(encoding='utf-8')
                if json.loads(witness) != adapter.intended(job):
                    raise RuntimeError('The recorded mock acceptance differs from the original exact invoice intent')
                add_evidence(trial, work.case_id, WITNESS_KIND, witness, job.operation_key)
                invoice_delivery.finish(*lease, 'unknown', 'Synthetic acceptance occurred before its receipt became visible.')
            else:
                raise RuntimeError('Expected the isolated mock acceptance with its reply interrupted')
    if not Evidence.objects.filter(case=work.case, kind=WITNESS_KIND, source=job.operation_key).exists():
        raise RuntimeError('The original synthetic witness is unavailable. Preserve the reservation for inspection.')
    return {'work': work.pk, 'case': str(work.case_id), 'invoice': work.invoice_id, 'job': job.pk,
            'operation_key': job.operation_key, 'preserved': lease is None,
            'path': reverse('factory_invoice_recovery', args=[work.pk])}


def reveal_original_receipt(work_id):
    trial = require_sample_account()
    case = Case.objects.get(tenant=TENANT, title=RECOVERY_CASE, kind='project', synthetic=True, factorywork__pk=work_id)
    work = sample_work(case)
    if work.pk != work_id or work.actor_id != trial.pk:
        raise RuntimeError('Exact synthetic recovery work and original actor required')
    job = InvoiceJob.objects.select_related('invoice__case').get(invoice=work.invoice, kind='issue', generation=1)
    if not Audit.objects.filter(case=case, actor=trial, action='factory.reconciliation_requested',
                                data={'work': work.pk, 'job': job.pk}).exists():
        raise RuntimeError('Observe the initial lookup miss in the browser before revealing the original mock receipt')
    witness = Evidence.objects.get(case=case, kind=WITNESS_KIND, source=job.operation_key, created_by=trial)
    with TemporaryDirectory(prefix='psl-invoice-observation-') as directory:
        adapter = MockFactoryInvoiceAdapter(directory)
        if witness.sha256 != sha256(witness.body.encode()).hexdigest() or json.loads(witness.body) != adapter.intended(job):
            raise RuntimeError('The protected original witness differs from this reserved operation')
        adapter.path(job).write_text(witness.body, encoding='utf-8')
        if job.status != 'confirmed':
            with patch.object(factory, 'adapter_for', return_value=adapter):
                factory.reconcile(trial, work.pk, work.revision)
    job.refresh_from_db()
    if job.status != 'confirmed':
        raise RuntimeError('The exact original lookup has not settled. Check for an active lease before trying again.')
    receipt = InvoiceIssue.objects.get(invoice=work.invoice, job=job)
    return {'work': work.pk, 'job': job.pk, 'operation_key': job.operation_key, 'original_receipt': receipt.pk,
            'path': reverse('factory_invoice_recovery', args=[work.pk])}


def run():
    print('PSL_DELEGATED_INVOICE_FIXTURE=' + json.dumps(prepare_delegation()), flush=True)
    print('PSL_DELAYED_INVOICE_FIXTURE=' + json.dumps(prepare_recovery()), flush=True)
