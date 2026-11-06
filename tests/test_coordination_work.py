from django.test import TransactionTestCase,Client
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.urls import reverse,resolve
from django.utils import timezone
from apps.core import workbench
from apps.core.models import Audit
from apps.identity.models import Grant


class CoordinationWorkTests(TransactionTestCase):
    def rows(self,actor,kind):
        return [r for r in workbench.work(actor)['rows'] if r['kind']==kind]

    def test_delivered_department_request_current_recipient_source_resolution_and_no_effect(self):
        from tests.approval_helpers import fixture,capture,observe
        from apps.pmo import approval_routing as routing
        from apps.pmo.models import ApprovalRouteReceipt,GateVerification
        f=fixture('work-department');a,b,c=f['actor'],f['owner'],f['case']
        self.assertFalse(self.rows(b,'received_department_request'))
        job=routing.reserve(a,c.pk,f['request'].pk)
        self.assertFalse(self.rows(b,'received_department_request'))
        routing.run_once();receipt=ApprovalRouteReceipt.objects.get(job=job)
        before=(Audit.objects.count(),GateVerification.objects.count(),ApprovalRouteReceipt.objects.count())
        rows=self.rows(b,'received_department_request');self.assertEqual([r['record_id'] for r in rows],[receipt.pk])
        self.assertEqual(rows[0]['status'],'awaiting_source');self.assertNotIn('subject',rows[0]);resolve(rows[0]['url'])
        self.assertFalse(self.rows(a,'received_department_request'))
        client=Client();client.force_login(b);response=client.get(reverse('work_inbox'))
        self.assertContains(response,'Received department request');self.assertEqual(response['Cache-Control'],'no-store')
        self.assertEqual(before,(Audit.objects.count(),GateVerification.objects.count(),ApprovalRouteReceipt.objects.count()))
        source=capture(f);observe(f,source)
        self.assertFalse(self.rows(b,'received_department_request'));self.assertTrue(ApprovalRouteReceipt.objects.filter(pk=receipt.pk).exists())

    def test_department_current_contract_sender_and_recipient_revocation_keep_receipt(self):
        from tests.approval_helpers import fixture
        from apps.pmo import approval_routing as routing,approvals
        from apps.pmo.models import ApprovalRouteReceipt
        f=fixture('work-department-revoke');a,b,c=f['actor'],f['owner'],f['case']
        job=routing.reserve(a,c.pk,f['request'].pk);routing.run_once()
        self.assertEqual(len(self.rows(b,'received_department_request')),1)
        for user,action in [(a,'approval.route'),(b,'approval.receive'),(b,'case.read')]:
            Grant.objects.filter(user=user,case=c,action=action).update(active=False)
            self.assertFalse(self.rows(b,'received_department_request'))
            Grant.objects.filter(user=user,case=c,action=action).update(active=True)
        approvals.review_contract(b,c.pk,'qa_exit',f['e']['approval_contract_review'].pk,'withdraw')
        self.assertFalse(self.rows(b,'received_department_request'))
        self.assertTrue(ApprovalRouteReceipt.objects.filter(job=job).exists())

    def test_department_successor_request_retires_discovery_not_source_receipt(self):
        from tests.approval_helpers import fixture
        from apps.pmo import approval_routing as routing,approvals
        from apps.pmo.models import ApprovalRouteReceipt
        f=fixture('work-department-successor');a,b,c=f['actor'],f['owner'],f['case']
        job=routing.reserve(a,c.pk,f['request'].pk);routing.run_once()
        self.assertEqual(len(self.rows(b,'received_department_request')),1)
        approvals.create_request(a,c.pk,f['request'].reference,f['candidate'].pk,'qa_exit','B2','R2',f['e']['approval_request'].pk,predecessor=f['request'].pk)
        self.assertFalse(self.rows(b,'received_department_request'))
        self.assertTrue(ApprovalRouteReceipt.objects.filter(job=job).exists())

    def test_bounded_discovery_measurement_does_not_scan_or_count_hidden_cases(self):
        import json,time
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from apps.core.models import Case
        from tests.helpers import setup_case
        a,c=setup_case(username='discovery-load')
        cases=Case.objects.bulk_create([Case(tenant=c.tenant,title='Bounded scope '+str(n),kind='project',synthetic=True) for n in range(300)])
        Grant.objects.bulk_create([Grant(case=row,user=a,action='case.read') for row in cases[:100]])
        started=time.perf_counter()
        with CaptureQueriesContext(connection) as queries:
            page=workbench.discover(a,page_size=50)
            second=workbench.discover(a,page_size=50,cursor=page['next_cursor'])
        elapsed=time.perf_counter()-started
        self.assertEqual(len(page['cases']),50);self.assertEqual(len(second['cases']),50)
        shown={r.pk for r in page['cases']+second['cases']}
        self.assertTrue(shown <= {c.pk,*[r.pk for r in cases[:100]]});self.assertEqual(len(shown),100)
        self.assertNotIn('total',page);self.assertLessEqual(len(queries),4)
        self.assertTrue(all('LIMIT 51' in q['sql'] for q in queries if 'SELECT DISTINCT' in q['sql']))
        print('MEASURED_DISCOVERY '+json.dumps({'synthetic_cases':301,'granted_cases':101,'pages':2,'page_size':50,'queries':len(queries),'seconds':round(elapsed,6),'deployment_slo_claim':False}))

    def test_rfp_assignment_current_owner_deadline_and_intake_successor(self):
        from tests.test_rfp import fixture
        from tests.helpers import rev
        from apps.pmo import rfp
        from apps.pmo.models import RFPAssignment
        a,c,e,_,_=fixture();rows=self.rows(a,'assigned_rfp');self.assertEqual(len(rows),1)
        self.assertIsNone(rows[0]['recorded_due_at']);self.assertEqual(rows[0]['deadline_basis'],'not_stated');resolve(rows[0]['url'])
        before=(Audit.objects.count(),RFPAssignment.objects.count())
        client=Client();client.force_login(a);self.assertContains(client.get(reverse('work_inbox')),'Assigned RFP coordination')
        self.assertEqual(before,(Audit.objects.count(),RFPAssignment.objects.count()))
        rfp.intake(a,c.pk,'RFP-001',e['rfp_intake'].pk,timezone.now(),'unknown',None,None,'Revised unknown deadline',rev(c))
        self.assertFalse(self.rows(a,'assigned_rfp'))
        rfp.assign(a,c.pk,a,'CEO',e['policy_decision'].pk,'Current source assignment',rev(c))
        self.assertEqual(self.rows(a,'assigned_rfp')[0]['deadline_basis'],'unknown')
        self.assertContains(client.get(reverse('work_inbox')),'Deadline source: unknown')
        Grant.objects.filter(user=a,case=c,action='rfp.prepare').update(active=False)
        self.assertFalse(self.rows(a,'assigned_rfp'))
        Grant.objects.filter(user=a,case=c,action='rfp.prepare').update(active=True)
        get_user_model().objects.filter(pk=a.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):rfp.current_assignment(rfp.root(c))

    def test_rfp_real_reviewed_submission_and_won_disposition_remove_assignment(self):
        from tests.test_rfp import fixture,response,approve,submit
        from tests.helpers import rev
        from apps.pmo import rfp
        a,c,e,t,_=fixture();self.assertEqual(len(self.rows(a,'assigned_rfp')),1)
        value=response(a,c,e);approve(a,c,e,value);submission=submit(a,c,e,t,value)
        outcome=rfp.outcome(a,c.pk,submission.pk,'won',timezone.now(),'Client',e['rfp_outcome'].pk,'Actual synthetic win',rev(c))
        rfp.dispose(a,c.pk,outcome.pk,None,rev(c))
        self.assertFalse(self.rows(a,'assigned_rfp'))
