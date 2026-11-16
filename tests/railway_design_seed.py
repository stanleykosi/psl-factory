"""Populate named synthetic acceptance workspaces through native services."""
import json
import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.documents.controlled import create_version, register_template, request_review
from apps.finance import invoice_delivery, invoices
from apps.finance.models import InvoiceIssue
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo.meetings import create_action
from apps.workflows import factory
from tests import document_helpers, factory_rfp_helpers, finance_analysis_helpers, finance_performance_helpers, settlement_helpers
from tests.helpers import rev, roles
from tests.obligation_helpers import identified
from tests import test_delivery
from tests.test_factory_emergency import FactoryEmergencyTests
from tests.test_rfp import commercial_helpers

if os.environ.get('RAILWAY_ENVIRONMENT_NAME') != 'design-acceptance':
    raise SystemExit('Exact Railway acceptance environment required')
actor = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
tenant = 'design-browser-acceptance'


def evidence(case, kind, body):
    return add_evidence(actor, case.pk, kind, body, 'synthetic:design-browser-acceptance')


def project(case):
    owner = evidence(case, 'policy_decision', 'Synthetic document template and approval responsibility fixture')
    source = evidence(case, 'completion', 'The synthetic project has documented progress and pending follow-up.')
    roles(actor, case, owner)
    template = register_template(actor, case.pk, 'Browser acceptance status report', document_helpers.DEFINITION, owner.pk, rev(case))
    version = create_version(actor, case.pk, template.pk, 'Browser acceptance report', 'client',
                             document_helpers.fields(source), rev(case))
    request_review(actor, case.pk, version.pk, rev(case))
    item = create_action(actor, case.pk, 'BROWSER-ACTION', 'Confirm the synthetic project evidence', actor.pk,
                         timezone.now() + timedelta(days=2), source.pk, 'Synthetic browser acceptance item', rev(case))
    return {'action': item.pk, 'document_version': version.pk}


def settlement(case):
    with patch.object(settlement_helpers, 'setup_case', return_value=(actor, case)):
        _, _, coverage, preparation, proofs = settlement_helpers.fixture()
    invoice = settlement_helpers.draft(actor, case, preparation, 'BROWSER-INVOICE-001')
    identified(actor, case, invoice)
    settlement_helpers.approve(actor, case, invoice, proofs)
    job = invoices.reserve(actor, case.pk, invoice.pk, 'issue', 'Finance', rev(case))
    invoice_delivery.run_once(case_id=case.pk, job_id=job.pk)
    issue = InvoiceIssue.objects.get(invoice=invoice)
    receipt, lot = settlement_helpers.receipt(actor, case, ref='browser-acceptance-cash')
    settlement_helpers.assign(actor, case, receipt, coverage, proofs)
    settlement_helpers.allocate(actor, case, lot, issue, '20.00', proofs)
    return {'invoice': invoice.pk, 'issue': issue.pk, 'coverage': coverage.pk}


def bid(case):
    with patch.object(commercial_helpers, 'setup_case', return_value=(actor, case)):
        data = factory_rfp_helpers.configured()
    work = factory_rfp_helpers.start(data, key='BROWSER-RFP')
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    return {'work': work.pk, 'state': work.status}


def finance_period(case):
    def fixture():
        return finance_analysis_helpers.fixture(recipient_username='design-acceptance-finance-recipient')

    with patch.object(finance_analysis_helpers, 'setup_case', return_value=(actor, case)), \
         patch.object(finance_performance_helpers, 'fixture', side_effect=fixture):
        data = finance_performance_helpers.fixture_performance()
    return {'period': data[8].pk}


def delivery(case):
    fixture = test_delivery.DeliveryFixture()
    with patch.object(test_delivery, 'setup_case', return_value=(actor, case)):
        fixture.setup_delivery()
    release = fixture.release()
    return {'dossier': fixture.d.pk, 'release': release.pk}


def emergency(case):
    fixture = FactoryEmergencyTests()
    with patch.object(commercial_helpers, 'setup_case', return_value=(actor, case)):
        fixture.setUp()
    fixture.policies('coexist')
    work = fixture.start_work()
    return {'work': work.pk, 'profile': fixture.profile.pk}


def seed(key, title, callback):
    try:
        with transaction.atomic():
            case, created = Case.objects.get_or_create(tenant=tenant, title=title, synthetic=True, kind='project')
            if created:
                Grant.objects.bulk_create([Grant(case=case, user=actor, action=action) for action in dict.fromkeys(ACTIONS)])
                outcome = callback(case)
            else:
                if not Grant.objects.filter(case=case, user=actor, action='case.read', active=True).exists():
                    raise RuntimeError('Unexpected fixture ownership')
                # This named synthetic fixture may need a newly registered read action after an application update.
                Grant.objects.get_or_create(case=case, user=actor, action='report.read')
                outcome = {'existing': True}
        print('PSL_BROWSER_FIXTURE=' + json.dumps({'key': key, 'case': str(case.pk), **outcome}), flush=True)
    except Exception as exc:
        print('PSL_BROWSER_FIXTURE_ERROR=' + json.dumps({'key': key, 'error': type(exc).__name__, 'reason': str(exc)[:240]}), flush=True)


seed('project', 'Browser acceptance project and documents', project)
seed('billing', 'Browser acceptance client billing and receipts', settlement)
seed('bid', 'Browser acceptance bid response and decisions', bid)
seed('finance', 'Browser acceptance reviewed monthly figures', finance_period)
seed('delivery', 'Browser acceptance delivery and release', delivery)
seed('emergency', 'Browser acceptance emergency approvals', emergency)
