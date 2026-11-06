from datetime import timedelta
from django.test import TransactionTestCase,Client
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.urls import reverse,resolve as url_resolve
from django.utils import timezone
from apps.core.models import Case,Audit
from apps.core import workbench as d
from apps.identity.models import Grant
from tests.helpers import setup_case,rev

class SharedWorkbenchTests(TransactionTestCase):
    def test_search_scope_keyset_cursor_binding_active_user_and_escaping(self):
        a,c=setup_case(username='discovery-owner');c.title='Visible <script>alert(1)</script>';c.save(update_fields=['title'])
        permitted={c.pk}
        for index in range(7):
            row=Case.objects.create(tenant='tenant-two' if index%2 else c.tenant,title='Discovery case '+str(index),kind='support' if index%2 else 'project',synthetic=True)
            if index<6:Grant.objects.create(case=row,user=a,action='case.read');permitted.add(row.pk)
        rows=[];cursor=None
        while True:
            page=d.discover(a,page_size=2,cursor=cursor);rows += [r.pk for r in page['cases']];cursor=page['next_cursor']
            if cursor is None:break
        self.assertEqual(set(rows),permitted);self.assertEqual(len(rows),len(permitted))
        cursor=d.discover(a,page_size=2)['next_cursor'];other=get_user_model().objects.create_user('other-discovery')
        for call in [lambda:d.discover(other,page_size=2,cursor=cursor),lambda:d.discover(a,q='changed',page_size=2,cursor=cursor),lambda:d.discover(a,page_size=2,cursor=cursor+'x')]:
            with self.assertRaises(ValidationError):call()
        self.assertFalse(d.discover(a,q="%' OR 1=1 --")['cases']);self.assertFalse(d.discover(a,tenant='hidden-tenant')['cases'])
        self.assertTrue(all(r.kind=='support' and r.tenant=='tenant-two' for r in d.discover(a,tenant='tenant-two',kind='support')['cases']))
        self.assertEqual(d.discover(a,q=str(c.pk))['cases'][0].pk,c.pk)
        client=Client();client.force_login(a);response=client.get(reverse('workspace_overview'),{'q':'Visible'})
        self.assertContains(response,'&lt;script&gt;');self.assertNotContains(response,'<script>alert(1)</script>');self.assertEqual(response['Cache-Control'],'no-store')
        self.assertContains(client.get(reverse('workspace_overview'),{'cursor':'x'*4097}),'This page link is invalid')
        Grant.objects.filter(case=c,user=a,action='case.read').update(active=False);self.assertFalse(d.discover(a,q='Visible')['cases'])
        get_user_model().objects.filter(pk=a.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):d.discover(a)
        with self.assertRaises(PermissionDenied):d.work(a)

    def test_project_references_require_current_engagement_read_and_case_read(self):
        from tests.test_engagement_intake import EngagementIntakeTests
        from apps.pmo import engagement
        helper=EngagementIntakeTests();a,c,e,p,policy,values=helper.ready('discovery-project-owner')
        engagement.register(a,c.pk,'SYN-SEARCH-REF','PMO Lead',e.pk,p.pk,'search-identifier')
        self.assertEqual([r.pk for r in d.discover(a,q='SYN-SEARCH-REF')['cases']],[c.pk])
        self.assertEqual([r.pk for r in d.discover(a,q='direct-client')['cases']],[c.pk])
        Grant.objects.filter(case=c,user=a,action='engagement.read').update(active=False)
        self.assertFalse(d.discover(a,q='SYN-SEARCH-REF')['cases']);self.assertFalse(d.discover(a,q='direct-client')['cases'])
        self.assertEqual([r.pk for r in d.discover(a,q=str(c.pk))['cases']],[c.pk])

    def test_action_assignment_and_document_review_are_source_owned_and_read_only(self):
        from tests.meeting_helpers import meetings_fixture
        from apps.pmo.meetings import create_action,change_action
        from apps.pmo.reporting import draft_minutes
        from apps.documents.controlled import request_review,review_version
        from apps.workflows.models import TaskEvent
        a,c,owner,notes,minutes,report_template,meeting,recipient=meetings_fixture()
        item=create_action(a,c.pk,'OWN-ACTION','Recorded own commitment',a.pk,None,notes.pk,'Actual recorded owner without guessed deadline',rev(c),meeting.meeting_id)
        create_action(a,c.pk,'UNASSIGNED','Unknown owner',None,None,notes.pk,'Unknown is not assigned to a grant holder',rev(c),meeting.meeting_id)
        binding=draft_minutes(a,c.pk,meeting.meeting_id,minutes.pk,'client',rev(c));task=request_review(a,c.pk,binding.version_id,rev(c))
        before=(Audit.objects.count(),TaskEvent.objects.count());value=d.work(a)
        self.assertEqual(before,(Audit.objects.count(),TaskEvent.objects.count()));self.assertFalse(value['authority_from_discovery']);self.assertEqual(value['effect_tools'],[])
        action=next(r for r in value['rows'] if r['kind']=='assigned_action');self.assertEqual(action['record_id'],item.pk);self.assertIsNone(action['recorded_due_at'])
        self.assertEqual(len([r for r in value['rows'] if r['kind']=='assigned_action']),1)
        self.assertTrue(any(r['kind']=='eligible_document_review' and r['record_id']==task.pk for r in value['rows']))
        self.assertTrue(all(r['synthetic'] for r in value['rows']))
        client=Client();client.force_login(a);response=client.get(reverse('work_inbox'))
        self.assertContains(response,'Assigned action');self.assertContains(response,'Sample data');self.assertNotContains(response,'Synthetic demonstration')
        for row in value['rows']:url_resolve(row['url'])
        review_version(a,c.pk,binding.version_id,'approve','Actual current PMO quality review',rev(c))
        self.assertFalse(any(r['kind']=='eligible_document_review' for r in d.work(a)['rows']))
        change_action(a,c.pk,item.pk,'complete',notes.pk,'Actual owned action completed',rev(c),item.current.number)
        self.assertFalse(any(r['kind']=='assigned_action' for r in d.work(a)['rows']))
        client=Client();client.force_login(a);self.assertContains(client.get(reverse('work_inbox')),'My work')

    def test_support_ownership_uses_latest_event_and_closed_cases_disappear(self):
        from tests.support_helpers import fixture,ready
        from apps.baas import support
        f=fixture('work-support');a,b,c=f['actor'],f['reviewer'],f['case'];ready(f)
        rows=d.work(a)['rows'];self.assertTrue(any(r['kind']=='owned_support' and r['case_id']==str(c.pk) for r in rows))
        for row in rows:url_resolve(row['url'])
        support.transition(a,c.pk,'investigate',b.pk,f['e']['support_transition'].pk,timezone.now().isoformat())
        self.assertFalse(any(r['kind']=='owned_support' for r in d.work(a)['rows']))
        self.assertTrue(any(r['kind']=='owned_support' for r in d.work(b)['rows']))
        support.transition(a,c.pk,'resolve',b.pk,f['e']['support_transition'].pk,timezone.now().isoformat())
        self.assertFalse(any(r['kind']=='owned_support' for r in d.work(b)['rows']))

    def test_summary_review_requires_configured_reviewer_source_scope_and_current_version(self):
        from tests.test_complaint_summaries import ComplaintSummaryTests
        from apps.baas import summaries
        from apps.policy.summary_validators import SCOPE,REVIEW
        helper=ComplaintSummaryTests();f,g,e,proof,values=helper.fixture();a,b,c=f['actor'],f['reviewer'],f['case']
        helper.config(f,SCOPE,values['scope']);request=helper.request(f,g,e);version=summaries.prepare(a,c.pk,request.pk,'work-summary')
        self.assertFalse(any(r['kind']=='eligible_summary_review' for r in d.work(b)['rows']))
        helper.config(f,REVIEW,values['review_template'])
        self.assertTrue(any(r['kind']=='eligible_summary_review' and r['record_id']==version.pk for r in d.work(b)['rows']))
        self.assertFalse(any(r['kind']=='eligible_summary_review' for r in d.work(a)['rows']))
        Grant.objects.filter(case=g['case'],user=b,action='support.read').update(active=False)
        self.assertFalse(any(r['kind']=='eligible_summary_review' for r in d.work(b)['rows']))

    def test_financial_intent_metadata_does_not_retry_or_issue(self):
        from tests import settlement_helpers as f
        from apps.finance import invoices,invoice_delivery
        from apps.finance.models import InvoiceIssue,InvoiceJob
        a,c,coverage,preparation,e=f.fixture();invoice=f.draft(a,c,preparation);f.approve(a,c,invoice,e)
        job=invoices.reserve(a,c.pk,invoice.pk,'issue','Finance',rev(c))
        Grant.objects.filter(case=c,user=a,action='finance.invoice.issue').update(active=False);invoice_delivery.run_once();job.refresh_from_db();self.assertEqual(job.status,'held')
        before=(job.status,job.attempts,InvoiceIssue.objects.count());rows=d.work(a)['rows']
        self.assertTrue(any(r['kind']=='initiated_finance_intent' and r['record_id']==job.pk for r in rows));job.refresh_from_db()
        self.assertEqual(before,(job.status,job.attempts,InvoiceIssue.objects.count()))
        Grant.objects.filter(case=c,user=a,action='finance.read').update(active=False)
        self.assertFalse(any(r['kind']=='initiated_finance_intent' for r in d.work(a)['rows']))

    def test_document_review_authority_revocation_does_not_close_or_reassign_task(self):
        from tests.document_helpers import publication_fixture,drafted
        from apps.documents.controlled import request_review
        from apps.policy.services import active_component,transition
        from apps.workflows.models import HumanTask
        a,c,owner,source,template,*_=publication_fixture();v=drafted(a,c,template,source);task=request_review(a,c.pk,v.pk,rev(c))
        self.assertTrue(any(r['kind']=='eligible_document_review' for r in d.work(a)['rows']))
        transition(a,active_component('D05.role_principal_assignments',c).pk,'revoked')
        self.assertFalse(any(r['kind']=='eligible_document_review' for r in d.work(a)['rows']))
        task.refresh_from_db();self.assertEqual(task.status,'open');self.assertEqual(HumanTask.objects.count(),1)

    def test_private_finance_version_never_enters_generic_pmo_review_discovery(self):
        from tests.readiness_helpers import endpoint
        from tests.accepted_publication_helpers import ready,draft
        from apps.workflows.models import HumanTask
        with endpoint():
            f=ready();v=draft(f)
            # An unexpected legacy open task is a real PostgreSQL fixture, not an
            # authorized generic review path for this native private version.
            task=HumanTask.objects.create(case=f['case'],version=v,created_by=f['actor'])
            self.assertFalse(any(r['kind']=='eligible_document_review' and r['record_id']==task.pk for r in d.work(f['actor'])['rows']))
            task.refresh_from_db();self.assertEqual(task.status,'open')
