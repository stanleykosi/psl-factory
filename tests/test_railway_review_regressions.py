"""Regression checks for Finance projections and worker queues."""

from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from adapters.approvals import InternalApprovalRoutingAdapter
from adapters.publications import InternalPublicationAdapter
from apps.core.models import Case
from apps.core.read_budget import ReadBudget
from apps.documents.models import PublicationJob
from apps.finance import invoices, month_end, payments_overview, project_money
from apps.identity.models import Grant
from apps.identity.services import require
from apps.pmo import approval_routing
from apps.workflows.factory_views import work_grant_scope
from tests import approval_helpers, document_helpers, factory_helpers, forecast_helpers, settlement_helpers
from tests.obligation_helpers import identified
from tests.process_role_helpers import role_accounts
from tests.test_fixed_contract_bridge import FixedContractFixture


class FinanceAndPublicationRegressions(TestCase):
    def test_cash_classification(self):
        projects=[Case.objects.create(tenant='review-fixture',kind='project',title=title,synthetic=synthetic) for title,synthetic in [('Example live',False),('Example sample',True)]]
        inputs=[{'case':p,'cash':[('NGN','gross_including_tax',Decimal(amount))]} for p,amount in zip(projects,[100,900])]
        observed=month_end.cash_in_month(inputs)['groups']
        self.assertEqual({row['sample']: row['amount'] for row in observed},
                         {False: Decimal(100), True: Decimal(900)})
    def test_later_horizon_opening(self):
        a,c,m=forecast_helpers.fixture()
        data=forecast_helpers.payload(a,c)
        data['months']=data['months'][1:]
        data['items']=data['items'][1:]
        forecast_helpers.actual(a,c,amount='20',verified=True)
        result = forecast_helpers.run(a,c,data).result
        self.assertIsNone(result['periods'][0]['opening'])
        self.assertIn('Opening for a later forecast month requires reconciliation', ' '.join(result['findings']))
    def test_new_reference_draft(self):
        a,c,cover,prep,proofs=settlement_helpers.fixture()
        old=settlement_helpers.draft(a,c,prep,'REFERENCE-A')
        superseded=settlement_helpers.draft(a,c,prep,'REFERENCE-A')
        replacement=settlement_helpers.draft(a,c,prep,'REFERENCE-B')
        self.assertEqual([old.version,superseded.version,replacement.version],[1,2,1])
        self.assertTrue(invoices.successor_drafts(superseded).filter(pk=replacement.pk).exists())
        self.assertEqual([row.pk for row in project_money.invoice_rows(a,c,ReadBudget())],[replacement.pk])
    def test_department_lead_can_find_issued_invoice(self):
        a,c,cover,prep,proofs=settlement_helpers.fixture()
        i=settlement_helpers.draft(a,c,prep,'LOOKUP-ROLE-SCOPE')
        identified(a,c,i)
        settlement_helpers.issue(a,c,i,proofs)
        reader=role_accounts(c)['finance_head']
        require(reader,c,'case.read'); require(reader,c,'finance.read')
        self.client.force_login(reader)
        r=self.client.get('/api/v1/payments',{'q':i.reference})
        self.assertEqual(r.status_code,200)
        self.assertIn(i.reference,[row['reference'] for row in r.json()['items']])
    def test_month_end_includes_authorized_department_work(self):
        f=factory_helpers.fixture()
        case=f['case']
        reader=role_accounts(case)['finance_head']
        require(reader,case,'finance.read')
        require(reader,case,'case.read')
        self.assertTrue(work_grant_scope(reader).filter(pk=f['work'].pk).exists())
        seen=month_end.work_in_month(reader,[{'case':case}],timezone.localdate().replace(day=1),timezone.now())
        self.assertIn(str(case.pk),[row['workspace_id'] for row in seen])

    def test_publication_batch_advances_after_twenty_uncertain_jobs(self):
        a,case,_,source,template,*_=document_helpers.publication_fixture()
        pubs=[document_helpers.reserved(a,case,template,source) for _ in range(21)]
        older={p.pk for p in pubs[:-1]}
        original=InternalPublicationAdapter.lookup
        def lookup(adapter,pub):
            if pub.pk in older: raise TimeoutError('Synthetic unavailable receipt')
            return original(adapter,pub)
        with patch.object(InternalPublicationAdapter,'lookup',new=lookup):
            for _ in range(2): call_command('work_publications',limit=20,verbosity=0)
        self.assertEqual(PublicationJob.objects.filter(publication_id__in=older,status='unknown').count(),20)
        self.assertGreater(PublicationJob.objects.get(publication=pubs[-1]).attempts,0)



class ProtectedPaymentPaginationTests(FixedContractFixture, TestCase):
    def test_protected_first_page_has_continuation(self):
        self.a.username='owner-fixed'; self.a.save(update_fields=['username'])
        owner,older,_,prep,proof=settlement_helpers.fixture()
        usable=settlement_helpers.draft(owner,older,prep,'CURSOR-OPEN')
        identified(owner,older,usable)
        settlement_helpers.issue(owner,older,usable,proof)
        _,_,protected=self.prepared()
        hidden,_=self.issued(protected,reference='CURSOR-PROTECTED',identity=True)
        Grant.objects.bulk_create([Grant(case=self.c,user=owner,action=a) for a in ('case.read','finance.read')])
        self.assertLess(usable.pk,hidden.pk)
        self.assertTrue(payments_overview.case_scope(owner,older,ReadBudget()))
        with self.assertRaises(PermissionDenied): payments_overview.case_scope(owner,self.c,ReadBudget())
        cases=payments_overview.granted(owner,['finance.read'])
        self.assertEqual(list(payments_overview.invoice_rows(cases,'CURSOR-',None).values_list('id',flat=True)),[hidden.pk,usable.pk])
        self.assertTrue(payments_overview.read_page(owner,'CURSOR-OPEN','','')[0])
        with patch.object(payments_overview,'SCAN_LIMIT',1):
            rows,_,cursor,_,_=payments_overview.read_page(owner,'CURSOR-','','')
            self.assertEqual(rows,[])
            self.assertIsNotNone(cursor,'An authorized older invoice is unreachable after the protected first scan')
            next_rows, *_ = payments_overview.read_page(owner, 'CURSOR-', '', cursor)
            self.assertEqual([row['reference'] for row in next_rows], [usable.reference])


class ApprovalWorkerRegressions(TestCase):
    def test_regular_approval_worker_with_one_unavailable_receipt(self):
        def reserve(prefix):
            f=approval_helpers.fixture(prefix=prefix)
            return approval_routing.reserve(f['actor'],f['case'].pk,f['request'].pk)
        older=reserve('queue-confirm-a')
        later=reserve('queue-confirm-b')
        original=InternalApprovalRoutingAdapter.lookup
        def lookup(adapter,job):
            if job.pk==older.pk: raise TimeoutError('Synthetic receipt service unavailable')
            return original(adapter,job)
        with patch.object(InternalApprovalRoutingAdapter,'lookup',new=lookup):
            call_command('work_approval_routes',limit=20,verbosity=0)
        older.refresh_from_db()
        later.refresh_from_db()
        self.assertEqual((older.status, older.attempts), ('unknown', 1))
        self.assertEqual((later.status, later.attempts), ('confirmed', 1))
