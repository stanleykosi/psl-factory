from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import DatabaseError, transaction
from django.test import TestCase
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import register_reference, transition, PolicyHold
from apps.pmo.issues import log_issue, update_issue, close_issue_log, reopen_issue
from apps.pmo.models import Issue, IssueState, IssueClosureEntry
from apps.agents.issues import investigate_issues
from apps.documents.controlled import register_template, preflight
from apps.pmo.reporting import draft_period_report
from apps.workflows.models import HumanTask
from .helpers import setup_case, project_evidence, roles, activate, rev
from .document_helpers import artifact

class IssueTests(TestCase):
    def setUp(self):
        self.a,self.c=setup_case();self.e=project_evidence(self.a,self.c)
        refs=[]
        for role in ['PM','QA']:
            r=register_reference(self.a,self.c.pk,'issue:role:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':self.a.pk},self.e['policy_decision'].pk)
            refs.append(r.ref)
        self.policy=activate(self.a,self.c,'D05.role_principal_assignments',refs,self.e['policy_decision'])
        self.fix=add_evidence(self.a,self.c.pk,'resolution','Documented owner fix','synthetic:Engineering')
        self.rca=add_evidence(self.a,self.c.pk,'root_cause','Critical cause analysis','synthetic:Engineering')

    def issue(self,severity='Critical',ref='ISS-001'):
        return log_issue(self.a,self.c.pk,ref,'Delivery blocker','Production',self.a.pk,'Investigate cause',self.e['requirements'].pk,'PM records source',rev(self.c),severity)

    def step(self,s,op,**kwargs):
        return update_issue(self.a,self.c.pk,s.issue_id,s.pk,op,self.fix.pk,'Owner work evidence',rev(self.c),**kwargs)

    def resolved(self):
        s=self.issue();s=self.step(s,'acknowledge');return self.step(s,'resolve',fix_id=self.fix.pk,root_cause_id=self.rca.pk)

    def closed(self):
        s=self.resolved()
        for role in ['QA','PM']:close_issue_log(self.a,self.c.pk,s.issue_id,s.pk,role,self.fix.pk,'Role updates authoritative log',rev(self.c))
        s.issue.refresh_from_db();return s.issue.current

    def test_critical_owner_fix_and_two_log_updates_close_without_approval_task(self):
        s=self.issue();s=self.step(s,'acknowledge');s=self.step(s,'start')
        with self.assertRaises(ValidationError):self.step(s,'resolve',fix_id=self.fix.pk)
        s=self.step(s,'resolve',fix_id=self.fix.pk,root_cause_id=self.rca.pk)
        close_issue_log(self.a,self.c.pk,s.issue_id,s.pk,'QA',self.fix.pk,'QA verified resolution',rev(self.c))
        s.issue.refresh_from_db();self.assertEqual(s.issue.current.status,'Resolved')
        close_issue_log(self.a,self.c.pk,s.issue_id,s.pk,'PM',self.fix.pk,'PM updated issue log',rev(self.c))
        s.issue.refresh_from_db();self.assertEqual(s.issue.current.status,'Closed')
        self.assertEqual(IssueClosureEntry.objects.count(),2)
        self.assertEqual(HumanTask.objects.count(),0)
        self.assertIsNotNone(s.acknowledged_at);self.assertIsNotNone(s.resolved_at)

    def test_no_owner_or_next_action_and_duplicate_tenant_identity(self):
        with self.assertRaises(ValidationError):log_issue(self.a,self.c.pk,'ISS-001','Issue','Delivery',None,'Investigate',self.fix.pk,'Reason',rev(self.c))
        with self.assertRaises(ValidationError):log_issue(self.a,self.c.pk,'ISS-001','Issue','Delivery',self.a.pk,'',self.fix.pk,'Reason',rev(self.c))
        self.issue()
        other_a,other=setup_case(username='other')
        with self.assertRaises(ValidationError):log_issue(other_a,other.pk,'ISS-001','Duplicate','Delivery',other_a.pk,'Investigate',self.fix.pk,'Reason',rev(other))
        self.assertEqual(Issue.objects.count(),1)

    def test_missing_policy_does_not_prevent_owned_intake_but_holds_pm_classification(self):
        transition(self.a,self.policy.pk,'revoked')
        s=self.issue(None)
        with self.assertRaises(PolicyHold):self.step(s,'manage',severity='High')
        s=self.step(s,'acknowledge')
        with self.assertRaises(ValidationError):self.step(s,'resolve',fix_id=self.fix.pk)
        self.assertIsNone(s.severity)

    def test_only_owner_can_work_and_pm_sets_exact_severity(self):
        s=self.issue('High')
        outsider=get_user_model().objects.create_user('worker')
        Grant.objects.create(user=outsider,case=self.c,action='issue.work')
        with self.assertRaises(ValidationError):update_issue(outsider,self.c.pk,s.issue_id,s.pk,'acknowledge',self.fix.pk,'Reason',rev(self.c))
        with self.assertRaises(ValidationError):self.step(s,'manage',severity='P1')
        s=self.step(s,'acknowledge');s=self.step(s,'resolve',fix_id=self.fix.pk)
        self.assertEqual(s.status,'Resolved');self.assertIsNone(s.root_cause_id)

    def test_external_register_links_are_scoped_typed_and_never_copied_as_authority(self):
        risk=add_evidence(self.a,self.c.pk,'risk_reference','Security risk record reference','synthetic:Security')
        incident=add_evidence(self.a,self.c.pk,'incident','Engineering incident reference','synthetic:Engineering')
        refs=[{'kind':'risk','source_ref':'SEC-RISK-7','evidence_id':risk.pk},{'kind':'incident','source_ref':'ENG-INC-9','evidence_id':incident.pk}]
        s=log_issue(self.a,self.c.pk,'ISS-REF','Referenced issue','Production',self.a.pk,'Ask source owner',self.fix.pk,'Owner links',rev(self.c),'Low',refs)
        self.assertEqual(s.external_links,refs)
        with self.assertRaises(ValidationError):log_issue(self.a,self.c.pk,'ISS-BAD','Bad source','Production',self.a.pk,'Ask owner',self.fix.pk,'Reason',rev(self.c),None,[{'kind':'risk','source_ref':'R1','evidence_id':incident.pk}])
        run=investigate_issues(self.a,self.c.pk,rev(self.c))
        self.assertFalse(run.result['external_risk_or_incident_lifecycle_changed']);self.assertFalse(run.result['automatic_escalation_authorized'])

    def test_stale_commands_and_immutable_histories_and_current_pointer(self):
        s=self.issue()
        s2=self.step(s,'acknowledge')
        with self.assertRaises(ValidationError):self.step(s,'start')
        with self.assertRaises(DatabaseError),transaction.atomic():IssueState.objects.filter(pk=s2.pk).update(note='Rewrite')
        other=self.issue('Low','ISS-OTHER')
        with self.assertRaises(DatabaseError),transaction.atomic():Issue.objects.filter(pk=s.issue_id).update(current=other)
        with self.assertRaises(DatabaseError),transaction.atomic():Issue.objects.filter(pk=s.issue_id).update(reference='Changed')

    def test_closure_logs_bind_exact_resolution_and_reopen_is_configured(self):
        s=self.closed()
        with self.assertRaises(PolicyHold):reopen_issue(self.a,self.c.pk,s.issue_id,s.pk,'PM',self.fix.pk,'New evidence','Investigate again',rev(self.c))
        artifact(self.a,self.c,'D05.decision_action_matrix','schema:psl/decision-actions/v1',{'rules':[{'role':'PM','actions':['reopen']}]},self.e['policy_decision'])
        self.client.force_login(self.a)
        response=self.client.post(f'/cases/{self.c.pk}/issues/',{'action':'reopen','revision':rev(self.c),'issue':s.issue_id,'state':s.pk,'role':'PM','evidence':self.fix.pk,'note':'New evidence','next_action':'Investigate again'})
        self.assertEqual(response.status_code,302)
        fresh=Issue.objects.get(pk=s.issue_id).current
        self.assertEqual(fresh.status,'Open');self.assertIsNone(fresh.fix_id);self.assertIsNone(fresh.acknowledged_at)
        self.assertEqual(IssueClosureEntry.objects.count(),2)
        self.assertEqual(IssueState.objects.get(pk=s.pk).status,'Closed')

    def test_actual_staff_forms_and_record_access(self):
        self.client.force_login(self.a);url=f'/cases/{self.c.pk}/issues/'
        response=self.client.post(url,{'action':'log','revision':rev(self.c),'reference':'ISS-UI','title':'Visible issue','kind':'Delivery','owner':self.a.pk,
            'next_action':'Investigate dependency','evidence':self.fix.pk,'note':'Staff source capture','severity':'High','external_links':'[]'})
        self.assertEqual(response.status_code,302)
        self.assertContains(self.client.get(url),'Visible issue')
        state=Issue.objects.get().current
        self.assertEqual(self.client.post(url,{'action':'work','revision':rev(self.c),'issue':state.issue_id,'state':state.pk,'operation':'acknowledge',
            'evidence':self.fix.pk,'note':'Owner acknowledges'}).status_code,302)
        self.assertIsNotNone(Issue.objects.get().current.acknowledged_at)
        admin=get_user_model().objects.create_superuser('admin','admin@example.test','test-only')
        self.client.force_login(admin);self.assertEqual(self.client.get(url).status_code,404)

    def test_issues_and_change_history_invalidate_local_reporting_snapshots(self):
        template=register_template(self.a,self.c.pk,'Issue report',{'document_type':'status_report','required_fields':['executive_summary','status'],
            'audience_fields':{'internal':['executive_summary','status','issue_status','issue_resolution','issue_impact','scope']}},self.e['policy_decision'].pk,rev(self.c))
        s=self.issue()
        b=draft_period_report(self.a,self.c.pk,'internal_tuesday',timezone.now()-timedelta(days=7),timezone.now(),template.pk,'internal',rev(self.c))
        self.assertIn('ISS-001',b.version.payload['sections'][2]['text'])
        self.assertFalse(preflight(b.version))
        self.step(s,'acknowledge')
        self.assertTrue(preflight(b.version))
