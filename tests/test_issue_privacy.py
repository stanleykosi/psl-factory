"""Generic issue routes must not adopt private domain evidence."""
from django.core.exceptions import ValidationError
from apps.core.evidence_access import PLANNING_PRIVATE
from apps.core.services import add_evidence
from apps.pmo.issues import log_issue
from .test_issues import IssueTests
from .helpers import rev

class IssuePrivacyTests(IssueTests):
    def test_private_planning_binding_rejected_before_issue_creation(self):
        for index, kind in enumerate(PLANNING_PRIVATE):
            with self.subTest(kind=kind):
                evidence=add_evidence(self.a,self.c.pk,kind,'Private native snapshot','synthetic:private')
                with self.assertRaises(ValidationError):
                    log_issue(self.a,self.c.pk,'PRIVATE-'+str(index),'Issue','Delivery',self.a.pk,'Investigate',evidence.pk,'Reason',rev(self.c))

    def test_private_posts_and_history_are_filtered_without_changing_native_subject(self):
        from apps.pmo.services import subject
        from apps.pmo.models import Issue, IssueState
        from apps.pmo.issues import update_issue
        from apps.agents.issues import investigate_issues
        s=self.issue()
        secret=add_evidence(self.a,self.c.pk,'planning_readiness','Secret readiness','synthetic:private')
        self.assertEqual(subject(self.c,secret.pk).pk,secret.pk)
        self.client.force_login(self.a)
        url=f'/cases/{self.c.pk}/issues/'
        before=IssueState.objects.count()
        response=self.client.post(url,{'action':'work','revision':rev(self.c),'issue':s.issue_id,'state':s.pk,'operation':'acknowledge','evidence':secret.pk,'note':'Attempt private binding'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(IssueState.objects.count(),before)
        self.assertNotContains(response,f'<option value="{secret.pk}">')
        # A retained legacy private state is immutable; hide its projection, do not rewrite it.
        old=Issue.objects.create(tenant=self.c.tenant,case=self.c,reference='LEGACY-PRIVATE')
        hidden=IssueState.objects.create(issue=old,number=1,title='Private legacy issue',kind='Delivery',severity=None,owner=self.a,next_action='Private followup',status='Open',evidence=secret,note='Private binding',actor=self.a)
        old.current=hidden;old.save(update_fields=['current'])
        page=self.client.get(url)
        self.assertNotContains(page,'LEGACY-PRIVATE')
        run=investigate_issues(self.a,self.c.pk,rev(self.c))
        self.assertEqual([f['issue_id'] for f in run.result['findings']],[s.issue_id])
        self.assertTrue(IssueState.objects.filter(pk=hidden.pk,evidence=secret).exists())

    def test_similarly_named_public_raw_evidence_is_allowed(self):
        e=add_evidence(self.a,self.c.pk,'planning_raw','Supplied public planning notes','synthetic:public')
        state=log_issue(self.a,self.c.pk,'PUBLIC-RAW','Issue','Delivery',self.a.pk,'Investigate',e.pk,'Reason',rev(self.c))
        self.assertEqual(state.evidence_id,e.pk)

    def test_every_mutation_rejects_private_snapshots_and_agent_sources(self):
        from apps.pmo.issues import update_issue,close_issue_log,reopen_issue
        from apps.pmo.models import IssueState,IssueClosureEntry
        from .document_helpers import artifact
        open_state=self.issue(ref='OPEN-PRIVATE-CHECK')
        resolved=self.resolved()
        for role in ['QA','PM']:close_issue_log(self.a,self.c.pk,resolved.issue_id,resolved.pk,role,self.fix.pk,'Close exact source',rev(self.c))
        resolved.issue.refresh_from_db();closed=resolved.issue.current
        artifact(self.a,self.c,'D05.decision_action_matrix','schema:psl/decision-actions/v1',{'rules':[{'role':'PM','actions':['reopen']}]},self.e['policy_decision'])
        other=self.issue(ref='RESOLVED-PRIVATE-CHECK');other=self.step(other,'acknowledge');other=self.step(other,'resolve',fix_id=self.fix.pk,root_cause_id=self.rca.pk)
        for kind in PLANNING_PRIVATE+['agent_private_issue_readback']:
            e=add_evidence(self.a,self.c.pk,kind,'Private','synthetic:private')
            before=(IssueState.objects.count(),IssueClosureEntry.objects.count())
            with self.assertRaises(ValidationError):update_issue(self.a,self.c.pk,open_state.issue_id,open_state.pk,'manage',e.pk,'Reason',rev(self.c))
            with self.assertRaises(ValidationError):close_issue_log(self.a,self.c.pk,other.issue_id,other.pk,'QA',e.pk,'Reason',rev(self.c))
            with self.assertRaises(ValidationError):reopen_issue(self.a,self.c.pk,closed.issue_id,closed.pk,'PM',e.pk,'Reason','Investigate',rev(self.c))
            self.assertEqual(before,(IssueState.objects.count(),IssueClosureEntry.objects.count()))
