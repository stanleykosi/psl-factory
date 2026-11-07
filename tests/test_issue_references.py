import json
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import DatabaseError,transaction
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo import issue_references as refs
from apps.pmo.models import IssueReferenceObservation,IssueReferenceRevision
from .test_issues import IssueTests
from .helpers import rev

class IssueReferenceTests(IssueTests):
    def setup_reference(self):
        self.s=self.issue()
        self.contract=refs.configure(self.a,self.c.pk,'incident','Engineering supplied register',['status','owner'],'supplied',self.fix.pk,rev(self.c))
        self.incident=add_evidence(self.a,self.c.pk,'incident','Incident external identity','supplied:ENG-I1')
        self.link={'kind':'incident','source_ref':'ENG-I1','evidence_id':self.incident.pk}

    def readback(self,availability='available',fields=None):
        data={'protocol':'issue-reference-readback/v1','source_identity':self.contract.source_identity,'source_ref':'ENG-I1','observed_at':timezone.now().isoformat(),'availability':availability,'fields':({'status':'Investigating'} if fields is None and availability=='available' else fields or {})}
        return add_evidence(self.a,self.c.pk,'agent_private_issue_readback',json.dumps(data),'supplied:Engineering:ENG-I1')

    def observe(self,**kwargs):
        e=self.readback(**kwargs)
        return refs.observe(self.a,self.c.pk,self.s.issue_id,self.s.pk,self.contract.pk,'ENG-I1',e.pk,rev(self.c))

    def correct(self,observation,previous=None,relations=None,extra=None):
        return refs.correct(self.a,self.c.pk,self.s.issue_id,self.s.pk,previous,[dict(self.link,observation_id=observation.pk)]+(extra or []),relations or [],self.fix.pk,'Source-owned correction',rev(self.c))

    def test_exact_observation_unknown_freshness_supersession_correction_and_immutable_history(self):
        self.setup_reference();one=self.observe();first=self.correct(one)
        report=refs.report(self.a,self.s.issue)
        self.assertEqual(report['references'][0]['freshness'],'unknown')
        self.assertEqual(report['references'][0]['fields']['status'],'Investigating')
        two=self.observe(availability='unavailable')
        self.assertEqual(refs.report(self.a,self.s.issue)['references'][0]['currentness'],'superseded')
        second=self.correct(two,first.pk)
        self.assertEqual(second.previous_id,first.pk)
        result=refs.report(self.a,self.s.issue)['references'][0]
        self.assertEqual(result['availability'],'unavailable');self.assertEqual(result['fields'],{})
        self.assertEqual(self.s.issue.current.status,'Open')
        with self.assertRaises(ValidationError):self.correct(one,first.pk)
        for model,pk in [(IssueReferenceObservation,one.pk),(IssueReferenceRevision,first.pk)]:
            with self.assertRaises(DatabaseError),transaction.atomic():model.objects.filter(pk=pk).delete()
        self.assertEqual(IssueReferenceRevision.objects.get(pk=first.pk).references[0]['observation_id'],one.pk)

    def test_source_field_allowlist_scope_revocation_and_no_unavailable_status_claim(self):
        self.setup_reference()
        with self.assertRaises(ValidationError):self.observe(fields={'severity':'P1'})
        with self.assertRaises(ValidationError):self.observe(availability='unavailable',fields={'status':'Resolved'})
        one=self.observe();self.correct(one)
        Grant.objects.filter(case=self.c,user=self.a,action='issue.reference.incident.read').update(active=False)
        with self.assertRaises(PermissionDenied):refs.report(self.a,self.s.issue)
        with self.assertRaises(PermissionDenied):self.observe()

    def test_explicit_human_incident_change_relation_not_inferred(self):
        self.setup_reference();one=self.observe()
        cr=add_evidence(self.a,self.c.pk,'change_request','Confirmed change identity','supplied:CR-1')
        change={'kind':'change','source_ref':'CR-1','evidence_id':cr.pk}
        relation={'incident_ref':'ENG-I1','change_ref':'CR-1','evidence_id':self.fix.pk,'confirmed':True}
        first=self.correct(one,extra=[change],relations=[relation])
        self.assertEqual(refs.report(self.a,self.s.issue)['relations'],[relation])
        self.assertEqual(first.state_id,self.s.pk)
        with self.assertRaises(ValidationError):self.correct(one,first.pk,relations=[dict(relation,confirmed=False)],extra=[change])

    def test_get_and_post_preserve_history_and_revoke_source_ids(self):
        self.setup_reference();one=self.observe();first=self.correct(one)
        self.client.force_login(self.a);url=f'/cases/{self.c.pk}/issues/'
        before=(rev(self.c),IssueReferenceRevision.objects.count(),IssueReferenceObservation.objects.count())
        self.assertContains(self.client.get(url),'Engineering supplied register')
        self.assertEqual(before,(rev(self.c),IssueReferenceRevision.objects.count(),IssueReferenceObservation.objects.count()))
        Grant.objects.filter(case=self.c,user=self.a,action='issue.reference.incident.read').update(active=False)
        page=self.client.get(url)
        self.assertNotContains(page,'Engineering supplied register')
        self.assertNotContains(page,'Investigating')
        self.assertEqual(set(page.context['issues'][0].public_references),{'held'})
        self.assertNotContains(page,one.source_sha256)
        # The independent public input keeps its deliberately public label.
        self.assertContains(page,'supplied:ENG-I1')
        response=self.client.post(url,{'action':'reference_correct','revision':rev(self.c),'issue':self.s.issue_id,'state':self.s.pk,'previous':first.pk,'references':json.dumps(first.references),'relations':'[]','evidence':self.fix.pk,'note':'No current source grant'})
        self.assertEqual(response.status_code,403)
        self.assertEqual(IssueReferenceRevision.objects.count(),1)
