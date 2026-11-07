"""Complete Standard and conditional commercial paths through the native change factory."""
import json
from pathlib import Path
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.urls import reverse
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.pmo.changes import log_change,decide_change,authorize_change
from apps.pmo.commercial import capture_response,adopt_signed
from apps.pmo.models import Baseline,ChangeClosure,ChangeDecision,StandardPreapproval
from apps.documents.models import PublicationReceipt
from apps.workflows import factory,factory_change as change
from tests import test_factory_change as factory_tests,test_standard_changes as standard_tests,test_commercial_changes as native_tests
from tests.helpers import rev

class FactoryChangeBranchTests(TestCase):
    assessments=native_tests.ControlledChangeTests.assessments
    ready=native_tests.ChangeExecutionTests.ready
    change_template=native_tests.ChangeExecutionTests.change_template
    revised_commercial=native_tests.ControlledChangeTests.revised_commercial
    policies=standard_tests.StandardChangeTests.policies
    bound=standard_tests.StandardChangeTests.bound
    start=factory_tests.FactoryChangeTests.start
    advance=factory_tests.FactoryChangeTests.advance
    review=factory_tests.FactoryChangeTests.review

    def setUp(self):
        native_tests.ControlledChangeTests.setUp(self);self.template=self.change_template()
        value=json.loads(Path('fixtures/factory-change.json').read_text());value.pop('classification');value.update(preparer_id=self.actor.pk,executor_id=self.actor.pk)
        config=draft_operator_policy(self.actor,self.case.pk,'OPS.factory_change_execution',value,self.e['policy_decision'].pk,timezone.now())
        transition(self.actor,config.pk,'validated');transition(self.actor,config.pk,'active')

    def standard(self,positive=False):
        a,c=self.actor,self.case
        self.procedure=add_evidence(a,c.pk,'change_procedure','Synthetic exact declared maintenance procedure','synthetic:procedure')
        self.match=add_evidence(a,c.pk,'change_procedure_match','Human PM verified exact procedure applicability','synthetic:match')
        self.approval=add_evidence(a,c.pk,'change_preapproval','Actual synthetic owner preapproval record','synthetic:preapproval')
        self.cv=log_change(a,c.pk,'CR-001','Standard','API','Apply declared procedure','Human owner request',self.source.pk,rev(c))
        self.entry={'key':'api-maintenance','module':'API','procedure_evidence_id':self.procedure.pk,'procedure_sha256':self.procedure.sha256,'expected_impact':{'cost_impact':positive,'timeline_impact':positive,'client_facing':positive},'production_gate':'independent_release_controls'}
        self.assessments(positive,positive,positive);self.bound()

    def finish(self,auth,missing_client=False):
        self.advance();self.review('notice');self.advance();self.assertEqual(change.report(self.work)['stage'],'execution')
        self.ready(auth)
        from apps.pmo.change_impacts import timeline_required
        if timeline_required(auth):native_tests.weekly_change_report(self.actor,self.case,self.e['policy_decision'])
        self.advance();self.review('go_live');self.advance();self.assertEqual(change.report(self.work)['stage'],'signatures')
        v=change.document(self.work,'go_live');receipt=PublicationReceipt.objects.get(publication__version=v)
        pm=add_evidence(self.actor,self.case.pk,'signature','Actual synthetic PM signature for exact report '+str(v.pk),'synthetic:pm')
        if missing_client:
            self.work.refresh_from_db()
            with self.assertRaises(ValidationError):change.close(self.actor,self.work.pk,self.work.revision,rev(self.case),receipt.pk,pm.pk,None,'Actual client signature has not been supplied')
            self.assertFalse(ChangeClosure.objects.filter(authorization=auth).exists())
            self.assertEqual(len(change.published(self.work,'notice')[2]),1)
            self.assertEqual(len(change.published(self.work,'go_live')[2]),1)
            self.assertEqual(change.report(self.work)['stage'],'signatures')
        client=add_evidence(self.actor,self.case.pk,'signature','Actual synthetic Client signature for exact report '+str(v.pk),'synthetic:client')
        self.work.refresh_from_db();change.close(self.actor,self.work.pk,self.work.revision,rev(self.case),receipt.pk,pm.pk,client.pk,'Human attestation of distinct exact-version signatures')
        self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        proof=change.verify(self.work);self.assertEqual(proof['authorization'],auth.pk);self.assertEqual(len(proof['receipt_ids']),2)
        self.assertEqual(ChangeClosure.objects.get(authorization=auth).receipt_id,receipt.pk);self.assertFalse(proof['deployment_authorized'])

    def test_full_standard_factory_uses_exact_preapproval_and_human_signed_closure(self):
        self.standard();auth=authorize_change(self.actor,self.case.pk,self.cv.pk,None,rev(self.case))
        self.assertEqual(auth.decision_ids,[]);self.assertEqual(len(auth.preapproval_snapshot['preapproval_ids']),2)
        self.start(auth);self.finish(auth)
        self.assertEqual(StandardPreapproval.objects.count(),2);self.assertFalse(ChangeDecision.objects.filter(version=self.cv).exists())
        self.assertTrue(self.work.activities.filter(kind='ACT04',status='succeeded').exists());self.assertTrue(self.work.activities.filter(kind='ACT09',status='succeeded').exists())

    def conditional(self,standard=False):
        a,c=self.actor,self.case
        if standard:self.standard(positive=True)
        else:self.assessments(True,True,True)
        roles=['Client','Engineering Lead','Security Manager'] if standard else ['Product','Engineering','Client','Engineering Lead','Security Manager']
        for role in roles[:-1]:decide_change(a,c.pk,self.cv.pk,role,'approve',self.source.pk,'Exact applicable human change decision',rev(c))
        with self.assertRaisesMessage(ValidationError,'Security Manager'):authorize_change(a,c.pk,self.cv.pk,None,rev(c))
        decide_change(a,c.pk,self.cv.pk,roles[-1],'approve',self.source.pk,'Exact final conditional decision',rev(c))
        with self.assertRaisesMessage(ValidationError,'approved commercial'):authorize_change(a,c.pk,self.cv.pk,None,rev(c))
        commercial,e=self.revised_commercial();auth=authorize_change(a,c.pk,self.cv.pk,commercial.pk,rev(c));self.start(auth)
        old_signed=Baseline.objects.get(case=c).signed_id
        self.advance();self.assertIsNone(change.document(self.work,'notice'));self.assertIn('signed controlled commercial baseline',self.work.finding)
        receipt=native_tests.delivered(a,c,commercial,self.t)
        response=capture_response(a,c.pk,commercial.pk,receipt.pk,'signed',e['signature'].pk,'Human verifies actual signed replacement SOW',rev(c))
        from tests.signature_helpers import packet_for
        packet_for(a,c,e,commercial)
        adoption=adopt_signed(a,c.pk,commercial.pk,response.pk,rev(c))
        self.assertEqual(adoption.before['signed_id'],old_signed);self.assertEqual(Baseline.objects.get(case=c).signed_id,e['signature'].pk)
        self.work.refresh_from_db()
        if self.work.status in factory.TERMINAL:factory.manage(a,self.work.pk,self.work.revision,'resume')
        self.finish(auth)
        self.assertEqual(auth.commercial_id,commercial.pk);self.assertEqual(len(auth.decision_ids),len(roles))
        self.assertEqual(PublicationReceipt.objects.filter(publication__factory_work=self.work).count(),2)
        self.assertEqual(PublicationReceipt.objects.filter(publication__version__commercialdocumentbinding__revision=commercial).count(),1)

    def test_normal_cost_timeline_client_path_keeps_commercial_chain_and_signed_adoption(self):self.conditional()
    def test_standard_preapproval_does_not_waive_conditional_decisions_commercial_chain_or_signature(self):self.conditional(standard=True)

    def test_console_authorization_uses_native_authorize_grant_not_manage_grant(self):
        self.assessments(False,False,False)
        for role in ['Product','Engineering']:decide_change(self.actor,self.case.pk,self.cv.pk,role,'approve',self.source.pk,'Actual human scope decision',rev(self.case))
        self.start();Grant.objects.filter(case=self.case,user=self.actor,action='change.manage').update(active=False)
        self.client.force_login(self.actor);url=reverse('factory_detail',args=[self.work.pk]);self.assertContains(self.client.get(url),'Record native change authorization')
        response=self.client.post(url,{'action':'authorize','revision':self.work.revision,'case_revision':rev(self.case),'change_version':self.cv.pk})
        self.assertEqual(response.status_code,302);self.assertEqual(self.cv.changeauthorization_set.count(),1)
        Grant.objects.filter(case=self.case,user=self.actor,action='change.authorize').update(active=False)
        self.assertNotContains(self.client.get(url),'Record native change authorization')

    def test_missing_client_signature_blocks_closure_after_all_native_prerequisites_and_receipts(self):
        auth=native_tests.ChangeExecutionTests.authorized(self);self.start(auth);self.finish(auth,missing_client=True)
