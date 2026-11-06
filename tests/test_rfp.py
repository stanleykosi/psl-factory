from datetime import timedelta
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.test import TestCase,TransactionTestCase
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import register_reference,PolicyHold
from apps.pmo import rfp,rfp_documents,commercial
from apps.pmo.models import RFPSubmission,RFPDisposition,Baseline,RFPIntake
from apps.pmo.services import prepare_baseline
from apps.documents.controlled import register_template,request_review,review_version,reserve_publication,preflight
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationReceipt,PublicationJob
from apps.agents.rfp import investigate_rfp
from .helpers import rev,activate,setup_case
from .document_helpers import artifact
from . import test_commercial_changes as commercial_helpers

DEFINITION={'document_type':'rfp_response','required_fields':['executive_summary','scope','requirements_mapping','commercial_terms'],
    'audience_fields':{'client':['executive_summary','scope','requirements_mapping','commercial_terms']}}

def fixture():
    a,c,e,_=commercial_helpers.fixture();commercial_helpers.change_roles(a,c,e['policy_decision'])
    for k in ['rfp_commercial_terms','rfp_intake','rfp_deadline','rfp_response','rfp_outcome','rfp_lessons','qa_estimate','product_input']:
        e[k]=add_evidence(a,c.pk,k,'Synthetic '+k+' source','synthetic:rfp')
    artifact(a,c,'D05.decision_action_matrix','schema:psl/decision-actions/v2',{'rfp':{'assignment_roles':['CEO'],'outcome_roles':['Client']},
        'rules':[{'role':role,'actions':['return','reject']} for role in rfp.REVIEW_ROLES]},e['policy_decision'])
    t=register_template(a,c.pk,'RFP response',DEFINITION,e['policy_decision'].pk,rev(c))
    artifact(a,c,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[t.pk],'repository':'internal-versioned','retention_days':30},e['policy_decision'])
    route={'kind':'rfp_submission','key':'client_bid','method':'internal_recipient_inbox','destination_ref':'synthetic:rfp-inbox','recipient_ids':[a.pk],'sender_roles':['PM']}
    rr=register_reference(a,c.pk,'rfp:route','schema:psl/rfp-submission-route/v1',route,e['policy_decision'].pk)
    activate(a,c,'D11.adapter_configuration_refs',[rr.ref],e['policy_decision'])
    rfp.intake(a,c.pk,'RFP-001',e['rfp_intake'].pk,timezone.now()-timedelta(hours=1),'not_stated',None,None,'Source explicitly has no deadline',rev(c))
    rfp.assign(a,c.pk,a,'CEO',e['policy_decision'].pk,'Actual assignment evidence',rev(c))
    for team,kind in rfp.TEAMS.items():rfp.contribute(a,c.pk,team,e[kind].pk,rev(c))
    return a,c,e,t,route

def response(a,c,e):
    return rfp.prepare_response(a,c.pk,e['rfp_response'].pk,[{'key':'R1','evidence_id':e['requirements'].pk,'response':'Cited coverage','disposition':'addressed'}],{k:e[k].pk for k in ['requirements','plan','costing']},rev(c),public_terms_id=e['rfp_commercial_terms'].pk)

def approve(a,c,e,v):
    # The source supplies no ordering between these two distinct response reviews.
    for role in reversed(rfp.REVIEW_ROLES):rfp.review(a,c.pk,v.pk,role,'approve',e['policy_decision'].pk,'Reviewed exact response',rev(c))
    for role in ['PM','Head of PMO','CEO']:commercial.decide_proposal(a,c.pk,v.commercial_id,role,'approve','Costing exact response',rev(c))

def submit(a,c,e,t,v):
    d=rfp_documents.draft(a,c.pk,v.pk,t.pk,'client_bid',rev(c));request_review(a,c.pk,d.pk,rev(c))
    review_version(a,c.pk,d.pk,'approve','Exact outward RFP quality review',rev(c));reserve_publication(a,c.pk,d.pk,rev(c))
    assert run_publication_once()
    return rfp_documents.capture_submission(a,c.pk,d.pk,rev(c))

class RFPTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.a,cls.c,cls.e,cls.t,cls.route=fixture()

    def test_won_route_a_then_fresh_project_contract(self):
        a,c,e,t=self.a,self.c,self.e,self.t;v=response(a,c,e);approve(a,c,e,v);s=submit(a,c,e,t,v)
        self.assertEqual(connection.vendor,'postgresql');self.assertEqual(s.receipt_ids,list(PublicationReceipt.objects.values_list('pk',flat=True)))
        o=rfp.outcome(a,c.pk,s.pk,'won',timezone.now(),'Client',e['rfp_outcome'].pk,'Relationship owner evidenced win',rev(c))
        d=rfp.dispose(a,c.pk,o.pk,None,rev(c));self.assertEqual(d.kind,'route_a');self.assertFalse(Baseline.objects.exists())
        with self.assertRaises(ValidationError):commercial.draft_submission(a,c.pk,v.commercial_id,t.pk,rev(c))
        sources=dict(v.commercial.sources)
        with self.assertRaises(ValidationError):commercial.propose(a,c.pk,sources,e['requirements'].pk,'Fresh contract needed',rev(c))
        sources['sow']=add_evidence(a,c.pk,'sow','New project contract, not the bid','synthetic:project-contract').pk
        with self.assertRaises(ValidationError):commercial.propose(a,c.pk,sources,e['requirements'].pk,'No inherited RFP decisions',rev(c),True)
        project=commercial.propose(a,c.pk,sources,e['requirements'].pk,'New Route A project contract',rev(c));self.assertEqual(project.decisions.count(),0)
        commercial_helpers.approvals(a,c,project)
        st=register_template(a,c.pk,'Project SOW',commercial_helpers.DEFINITION,e['policy_decision'].pk,rev(c))
        artifact(a,c,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[st.pk],'repository':'internal-versioned','retention_days':30},e['policy_decision'])
        receipt=commercial_helpers.delivered(a,c,project,st)
        signed=commercial.capture_response(a,c.pk,project.pk,receipt.pk,'signed',e['signature'].pk,'Actual matching signature attestation',rev(c))
        commercial.adopt_signed(a,c.pk,project.pk,signed.pk,rev(c));self.assertTrue(Baseline.objects.get().signed_id)

    def test_lost_archive_requires_lessons_and_preserves_sources(self):
        a,c,e,t=self.a,self.c,self.e,self.t;v=response(a,c,e);approve(a,c,e,v);s=submit(a,c,e,t,v)
        o=rfp.outcome(a,c.pk,s.pk,'lost',timezone.now(),'Client',e['rfp_outcome'].pk,'Actual loss evidence',rev(c))
        with self.assertRaises(ValidationError):rfp.dispose(a,c.pk,o.pk,None,rev(c))
        d=rfp.dispose(a,c.pk,o.pk,e['rfp_lessons'].pk,rev(c));self.assertEqual(d.kind,'loss_archive');self.assertEqual(d.lessons_id,e['rfp_lessons'].pk)
        with self.assertRaises(ValidationError):rfp.dispose(a,c.pk,o.pk,e['rfp_lessons'].pk,rev(c))

    def test_reviews_precede_ordered_costing_and_outward_review(self):
        a,c,e,t=self.a,self.c,self.e,self.t;v=response(a,c,e)
        with self.assertRaises(ValidationError):commercial.decide_proposal(a,c.pk,v.commercial_id,'PM','approve','Not reviewed',rev(c))
        for role in rfp.REVIEW_ROLES:rfp.review(a,c.pk,v.pk,role,'approve',e['policy_decision'].pk,'Checked',rev(c))
        with self.assertRaises(ValidationError):commercial.decide_proposal(a,c.pk,v.commercial_id,'CEO','approve','Wrong order',rev(c))
        for role in ['PM','Head of PMO','CEO']:commercial.decide_proposal(a,c.pk,v.commercial_id,role,'approve','Ordered costing',rev(c))
        d=rfp_documents.draft(a,c.pk,v.pk,t.pk,'client_bid',rev(c))
        with self.assertRaises(ValidationError):reserve_publication(a,c.pk,d.pk,rev(c))
        self.assertFalse(PublicationReceipt.objects.exists())

    def test_public_terms_are_explicit_and_internal_costing_is_not_a_quote(self):
        import json
        a,c,e,t=self.a,self.c,self.e,self.t
        with self.assertRaises(ValidationError):rfp.prepare_response(a,c.pk,e['rfp_response'].pk,[{'key':'R1','evidence_id':e['requirements'].pk,'response':'Valid technical coverage','disposition':'addressed'}],{k:e[k].pk for k in ['requirements','plan','costing']},rev(c))
        v=response(a,c,e);approve(a,c,e,v);d=rfp_documents.draft(a,c.pk,v.pk,t.pk,'client_bid',rev(c))
        rendered=json.dumps(d.payload)
        self.assertIn(e['rfp_commercial_terms'].body,rendered);self.assertNotIn(e['costing'].body,rendered)
        self.assertEqual(rfp.public_terms_for(v),e['rfp_commercial_terms'])

    def test_return_requires_new_response_and_all_fresh_decisions(self):
        a,c,e=self.a,self.c,self.e;v=response(a,c,e)
        rfp.review(a,c.pk,v.pk,'Engineering Lead','return',e['policy_decision'].pk,'Revise technical coverage',rev(c))
        with self.assertRaises(ValidationError):rfp.review(a,c.pk,v.pk,'PMO Lead','approve',e['policy_decision'].pk,'Cannot bypass return',rev(c))
        v2=response(a,c,e);self.assertNotEqual(v.commercial.sources['sow'],v2.commercial.sources['sow']);approve(a,c,e,v2)

    def test_unknown_deadline_holds_only_submission(self):
        a,c,e,t=self.a,self.c,self.e,self.t
        rfp.intake(a,c.pk,'RFP-001',e['rfp_intake'].pk,timezone.now(),'unknown',None,None,'Await deadline source',rev(c))
        rfp.assign(a,c.pk,a,'CEO',e['policy_decision'].pk,'Assign revised intake',rev(c))
        for team,kind in rfp.TEAMS.items():rfp.contribute(a,c.pk,team,e[kind].pk,rev(c))
        v=response(a,c,e);approve(a,c,e,v)
        d=rfp_documents.draft(a,c.pk,v.pk,t.pk,'client_bid',rev(c));self.assertFalse(preflight(d))
        request_review(a,c.pk,d.pk,rev(c));review_version(a,c.pk,d.pk,'approve','Exact client document reviewed while deadline evidence is pending',rev(c))
        with self.assertRaises(ValidationError):reserve_publication(a,c.pk,d.pk,rev(c))
        self.assertTrue(investigate_rfp(a,c.pk,rev(c)).result['citations'])

    def test_rfp_template_cannot_remove_the_required_final_client_document_review(self):
        a,c,e=self.a,self.c,self.e;v=response(a,c,e);approve(a,c,e,v)
        template=register_template(a,c.pk,'Unsafe RFP review bypass',dict(DEFINITION,internal_review_required=False),e['policy_decision'].pk,rev(c))
        with self.assertRaisesMessage(ValidationError,'final controlled document review'):
            rfp_documents.draft(a,c.pk,v.pk,template.pk,'client_bid',rev(c))

    def test_factory_execution_profile_validates_unknowns_limits_and_native_references(self):
        import json
        from pathlib import Path
        from apps.policy.operator_drafts import draft_operator_policy
        from apps.policy.services import transition
        from apps.policy.factory_rfp_validators import COMPONENT
        a,c,e=self.a,self.c,self.e
        value=json.loads(Path('fixtures/factory-rfp.json').read_text());value.pop('classification')
        policy=draft_operator_policy(a,c.pk,COMPONENT,value,e['policy_decision'].pk,timezone.now())
        transition(a,policy.pk,'validated');transition(a,policy.pk,'active')
        for changed in [dict(value,max_tokens=1),dict(value,executor_id=True),dict(value,route_key='unconfigured'),dict(value,template_id=999999999)]:
            with self.subTest(changed=changed),self.assertRaises(ValidationError):
                invalid=draft_operator_policy(a,c.pk,COMPONENT,changed,e['policy_decision'].pk,timezone.now())
                transition(a,invalid.pk,'validated')
        selected=dict(value,template_id=self.t.pk,route_key='client_bid',executor_id=a.pk)
        policy=draft_operator_policy(a,c.pk,COMPONENT,selected,e['policy_decision'].pk,timezone.now())
        transition(a,policy.pk,'validated')
        Grant.objects.filter(case=c,user=a,action='rfp.submit').update(active=False)
        with self.assertRaises(ValidationError):
            invalid=draft_operator_policy(a,c.pk,COMPONENT,selected,e['policy_decision'].pk,timezone.now())
            transition(a,invalid.pk,'validated')

    def test_changed_inputs_hold_queued_publication(self):
        a,c,e,t=self.a,self.c,self.e,self.t;v=response(a,c,e);approve(a,c,e,v)
        d=rfp_documents.draft(a,c.pk,v.pk,t.pk,'client_bid',rev(c));request_review(a,c.pk,d.pk,rev(c));review_version(a,c.pk,d.pk,'approve','Reviewed',rev(c));reserve_publication(a,c.pk,d.pk,rev(c))
        rfp.contribute(a,c.pk,'QA',e['qa_estimate'].pk,rev(c));self.assertTrue(preflight(d));run_publication_once()
        self.assertEqual(PublicationJob.objects.get().status,'held');self.assertFalse(PublicationReceipt.objects.exists())

    def test_receipt_capture_is_actual_idempotent_and_preserves_history(self):
        a,c,e,t=self.a,self.c,self.e,self.t;v=response(a,c,e);approve(a,c,e,v)
        d=rfp_documents.draft(a,c.pk,v.pk,t.pk,'client_bid',rev(c))
        with self.assertRaises(ValidationError):rfp_documents.capture_submission(a,c.pk,d.pk,rev(c))
        request_review(a,c.pk,d.pk,rev(c));review_version(a,c.pk,d.pk,'approve','Reviewed',rev(c));reserve_publication(a,c.pk,d.pk,rev(c));run_publication_once()
        # Later source changes cannot erase a real historical delivered effect.
        rfp.contribute(a,c.pk,'QA',e['qa_estimate'].pk,rev(c))
        s=rfp_documents.capture_submission(a,c.pk,d.pk,rev(c));self.assertEqual(s.pk,rfp_documents.capture_submission(a,c.pk,d.pk,rev(c)).pk)
        self.assertEqual(RFPSubmission.objects.count(),1)

    def test_scoped_access_and_revocation_not_admin_flags(self):
        a,c,e=self.a,self.c,self.e;other,_=setup_case(username='outsider');other.is_staff=True;other.is_superuser=True;other.save()
        with self.assertRaises(PermissionDenied):rfp.contribute(other,c.pk,'QA',e['qa_estimate'].pk,rev(c))
        v=response(a,c,e);approve(a,c,e,v);Grant.objects.filter(user=a,case=c,action='rfp.review').update(active=False)
        with self.assertRaises(PermissionDenied):rfp.reviewed(v)

    def test_policy_validation_and_missing_independent_authority(self):
        a,c,e=self.a,self.c,self.e
        artifact(a,c,'D05.decision_action_matrix','schema:psl/decision-actions/v2',{'rfp':{'outcome_roles':['Client']}},e['policy_decision'])
        with self.assertRaises(PermissionDenied):rfp.assign(a,c.pk,a,'CEO',e['policy_decision'].pk,'No assignment policy',rev(c))
        # Input capture remains available without assignment policy.
        rfp.contribute(a,c.pk,'QA',e['qa_estimate'].pk,rev(c))
        with self.assertRaises(ValidationError):artifact(a,c,'D05.decision_action_matrix','schema:psl/decision-actions/v2',{'rfp':{'assignment_roles':['invented']}},e['policy_decision'])
        bad=dict(self.route,destination_ref='https://user:secret@example.com')
        r=register_reference(a,c.pk,'bad:route','schema:psl/rfp-submission-route/v1',bad,e['policy_decision'].pk)
        with self.assertRaises(ValidationError):activate(a,c,'D11.adapter_configuration_refs',[r.ref],e['policy_decision'])

    def test_configuring_outcome_later_does_not_require_resubmission(self):
        a,c,e,t=self.a,self.c,self.e,self.t
        artifact(a,c,'D05.decision_action_matrix','schema:psl/decision-actions/v2',{'rfp':{'assignment_roles':['CEO']}},e['policy_decision'])
        v=response(a,c,e);approve(a,c,e,v);s=submit(a,c,e,t,v)
        with self.assertRaises(PermissionDenied):rfp.outcome(a,c.pk,s.pk,'won',timezone.now(),'Client',e['rfp_outcome'].pk,'Hold only unknown outcome authority',rev(c))
        artifact(a,c,'D05.decision_action_matrix','schema:psl/decision-actions/v2',{'rfp':{'assignment_roles':['CEO'],'outcome_roles':['Client']}},e['policy_decision'])
        o=rfp.outcome(a,c.pk,s.pk,'won',timezone.now(),'Client',e['rfp_outcome'].pk,'Actual relationship owner now configured',rev(c))
        self.assertEqual(rfp.dispose(a,c.pk,o.pk,None,rev(c)).kind,'route_a')
        self.assertEqual(RFPSubmission.objects.count(),1);self.assertEqual(PublicationReceipt.objects.count(),1)

    def test_postgres_immutable_history_and_stale_revision(self):
        a,c,e=self.a,self.c,self.e;old=rev(c);rfp.contribute(a,c.pk,'QA',e['qa_estimate'].pk,old)
        with self.assertRaises(ValidationError):rfp.contribute(a,c.pk,'QA',e['qa_estimate'].pk,old)
        with self.assertRaises(DatabaseError),transaction.atomic():
            with connection.cursor() as cursor:cursor.execute('UPDATE pmo_rfpintake SET note=%s',['tamper'])

    def test_pending_unknown_future_and_wrong_case_never_convert(self):
        a,c,e,t=self.a,self.c,self.e,self.t;v=response(a,c,e);approve(a,c,e,v);s=submit(a,c,e,t,v)
        for result in ['unknown','pending']:
            o=rfp.outcome(a,c.pk,s.pk,result,timezone.now(),'Client',e['rfp_outcome'].pk,'Actual uncertainty',rev(c))
            with self.assertRaises(ValidationError):rfp.dispose(a,c.pk,o.pk,None,rev(c))
        with self.assertRaises(ValidationError):rfp.outcome(a,c.pk,s.pk,'won',timezone.now()+timedelta(days=1),'Client',e['rfp_outcome'].pk,'Future assertion',rev(c))
        self.assertFalse(RFPDisposition.objects.exists())

    def test_ui_agent_and_policy_draft_are_connected(self):
        a,c,e=self.a,self.c,self.e;self.client.force_login(a);url=f'/cases/{c.pk}/rfp/'
        self.assertContains(self.client.get(url),'RFP intake and response studio')
        self.assertContains(self.client.get(url),'Public terms:')
        self.assertEqual(self.client.post(url,{'action':'investigate','revision':rev(c)}).status_code,302)
        self.assertContains(self.client.get(url),'Cited RFP investigation')
        from apps.core.presentation import workspace_name
        self.assertContains(self.client.get(f'/cases/{c.pk}/'),workspace_name(c))
        self.assertContains(self.client.get(f'/cases/{c.pk}/commercial/'),'RFP pre-engagement workspace')
        result=investigate_rfp(a,c.pk,rev(c)).result;self.assertFalse(result['approval_granted']);self.assertFalse(result['submission_dispatched'])
        self.assertTrue(result['citations'])

    def test_rfp_factory_settings_use_native_template_and_route_choices(self):
        import json
        from pathlib import Path
        from django.urls import reverse
        from apps.policy.models import Configuration
        from apps.policy.services import reference_values,transition
        from apps.policy.factory_rfp_validators import COMPONENT
        a,c,e=self.a,self.c,self.e;self.client.force_login(a)
        url=reverse('factory_configuration',args=[c.pk])+'?definition=rfp-response/v1'
        page=self.client.get(url)
        self.assertContains(page,'Client response template');self.assertContains(page,'Reviewed submission destination')
        self.assertNotContains(page,'Invoice executor')
        value=json.loads(Path('fixtures/factory-rfp.json').read_text());value.pop('classification');value.pop('review_role')
        value.update(action='draft',required_evidence_kinds='rfp_intake',executor_id='',information_resolver_id='',
            template_id=self.t.pk,route_key='client_bid',evidence=e['policy_decision'].pk)
        result=self.client.post(url,value)
        if result.status_code==200:self.assertFalse(result.context['form'].errors,result.context['form'].errors.as_json())
        self.assertRedirects(result,url)
        policy=Configuration.objects.filter(case=c,component=COMPONENT).latest('pk')
        configured=reference_values(policy)[0]
        self.assertIsNone(configured['review_role']);self.assertIsNone(configured['executor_id'])
        self.assertEqual(configured['template_id'],self.t.pk);self.assertEqual(configured['route_key'],'client_bid')
        transition(a,policy.pk,'validated')
        count=Configuration.objects.filter(case=c,component=COMPONENT).count()
        page=self.client.post(url,dict(value,route_key='unconfigured'))
        self.assertEqual(page.status_code,200);self.assertTrue(page.context['form'].errors)
        self.assertEqual(Configuration.objects.filter(case=c,component=COMPONENT).count(),count)
        self.assertEqual(self.client.get(url)['Cache-Control'],'no-store')

    def test_completed_agent_cites_actual_outcome_and_loss_lessons(self):
        a,c,e,t=self.a,self.c,self.e,self.t;v=response(a,c,e);approve(a,c,e,v);s=submit(a,c,e,t,v)
        o=rfp.outcome(a,c.pk,s.pk,'lost',timezone.now(),'Client',e['rfp_outcome'].pk,'Actual synthetic loss evidence',rev(c))
        rfp.dispose(a,c.pk,o.pk,e['rfp_lessons'].pk,rev(c));result=investigate_rfp(a,c.pk,rev(c)).result
        self.assertEqual(result['recorded_disposition']['kind'],'loss_archive')
        ids={x['id'] for x in result['citations']};self.assertIn(e['rfp_outcome'].pk,ids);self.assertIn(e['rfp_lessons'].pk,ids)
        self.assertFalse(result['approval_granted']);self.assertFalse(result['submission_dispatched'])

    def test_legacy_commercial_and_baseline_cannot_bypass_rfp(self):
        a,c,e=self.a,self.c,self.e
        with self.assertRaises(ValidationError):prepare_baseline(a,c.pk,e['plan'].pk,e['costing'].pk,e['sow'].pk,rev(c))
        with self.assertRaises(ValidationError):commercial_helpers.proposal(a,c,e)

    def test_stated_past_deadline_never_dispatches_or_backdates(self):
        a,c,e,t=self.a,self.c,self.e,self.t
        rfp.intake(a,c.pk,'RFP-001',e['rfp_intake'].pk,timezone.now()-timedelta(hours=2),'stated',timezone.now()-timedelta(hours=1),e['rfp_deadline'].pk,'Actual source deadline passed',rev(c))
        rfp.assign(a,c.pk,a,'CEO',e['policy_decision'].pk,'Assign',rev(c))
        for team,kind in rfp.TEAMS.items():rfp.contribute(a,c.pk,team,e[kind].pk,rev(c))
        v=response(a,c,e);approve(a,c,e,v)
        d=rfp_documents.draft(a,c.pk,v.pk,t.pk,'client_bid',rev(c))
        self.assertFalse(preflight(d))
        request_review(a,c.pk,d.pk,rev(c))
        review_version(a,c.pk,d.pk,'approve','Review records document quality without authorising a late dispatch',rev(c))
        with self.assertRaises(ValidationError):reserve_publication(a,c.pk,d.pk,rev(c))
        self.assertFalse(PublicationReceipt.objects.exists())

    def deadline_publication(self):
        a,c,e=self.a,self.c,self.e;deadline=timezone.now()+timedelta(days=1)
        rfp.intake(a,c.pk,'RFP-001',e['rfp_intake'].pk,timezone.now(),'stated',deadline,e['rfp_deadline'].pk,'Actual source deadline',rev(c))
        rfp.assign(a,c.pk,a,'CEO',e['policy_decision'].pk,'Assign exact current intake',rev(c))
        for team,kind in rfp.TEAMS.items():rfp.contribute(a,c.pk,team,e[kind].pk,rev(c))
        v=response(a,c,e);approve(a,c,e,v)
        document=rfp_documents.draft(a,c.pk,v.pk,self.t.pk,'client_bid',rev(c))
        request_review(a,c.pk,document.pk,rev(c));review_version(a,c.pk,document.pk,'approve','Exact response reviewed',rev(c))
        publication=reserve_publication(a,c.pk,document.pk,rev(c))
        return document,publication,deadline

    def test_queued_response_rechecks_deadline_and_holds_operator_retry(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from apps.documents.delivery import operate_publication
        document,publication,deadline=self.deadline_publication()
        # Controlled domain clock only; native claims, services and PostgreSQL remain real.
        with patch.object(rfp_documents,'timezone',SimpleNamespace(now=lambda:deadline+timedelta(seconds=1))):
            self.assertTrue(run_publication_once(job_id=publication.job.pk))
            publication.job.refresh_from_db();self.assertEqual(publication.job.status,'held')
            self.assertFalse(PublicationReceipt.objects.filter(publication=publication).exists())
            self.assertFalse(preflight(document))
            with self.assertRaisesMessage(ValidationError,'deadline has passed'):
                operate_publication(self.a,self.c.pk,publication.job.pk,'retry','Review current submission',rev(self.c))

    def test_committed_receipt_reconciles_after_deadline_without_resending(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from adapters.publications import PublicationTimeoutAfterAccept,InternalPublicationAdapter
        document,publication,deadline=self.deadline_publication()
        self.assertTrue(run_publication_once(PublicationTimeoutAfterAccept(),job_id=publication.job.pk))
        publication.job.refresh_from_db();self.assertEqual(publication.job.status,'unknown')
        receipts=list(PublicationReceipt.objects.filter(publication=publication).values_list('pk',flat=True))
        self.assertEqual(len(receipts),1)
        with patch.object(rfp_documents,'timezone',SimpleNamespace(now=lambda:deadline+timedelta(seconds=1))),patch.object(
                InternalPublicationAdapter,'deliver',side_effect=AssertionError('Existing receipt must not be sent again')):
            self.assertTrue(run_publication_once(job_id=publication.job.pk))
            submission=rfp_documents.capture_submission(self.a,self.c.pk,document.pk,rev(self.c))
        publication.job.refresh_from_db();self.assertEqual(publication.job.status,'confirmed')
        self.assertEqual(submission.receipt_ids,receipts)
        self.assertEqual(list(PublicationReceipt.objects.filter(publication=publication).values_list('pk',flat=True)),receipts)

    def test_route_keys_and_recipients_validated(self):
        a,c,e=self.a,self.c,self.e
        refs=[]
        for i in range(2):refs.append(register_reference(a,c.pk,'duplicate:'+str(i),'schema:psl/rfp-submission-route/v1',self.route,e['policy_decision'].pk).ref)
        with self.assertRaises(ValidationError):activate(a,c,'D11.adapter_configuration_refs',refs,e['policy_decision'])
        bad=dict(self.route,recipient_ids=[9999999]);r=register_reference(a,c.pk,'wrong:recipient','schema:psl/rfp-submission-route/v1',bad,e['policy_decision'].pk)
        with self.assertRaises(ValidationError):activate(a,c,'D11.adapter_configuration_refs',[r.ref],e['policy_decision'])

    def test_route_policy_change_holds_queued_publication(self):
        a,c,e,t=self.a,self.c,self.e,self.t;v=response(a,c,e);approve(a,c,e,v)
        d=rfp_documents.draft(a,c.pk,v.pk,t.pk,'client_bid',rev(c));request_review(a,c.pk,d.pk,rev(c));review_version(a,c.pk,d.pk,'approve','Reviewed',rev(c));reserve_publication(a,c.pk,d.pk,rev(c))
        r=register_reference(a,c.pk,'changed:route','schema:psl/rfp-submission-route/v1',dict(self.route,destination_ref='synthetic:other'),e['policy_decision'].pk)
        activate(a,c,'D11.adapter_configuration_refs',[r.ref],e['policy_decision']);run_publication_once()
        self.assertEqual(PublicationJob.objects.get().status,'held');self.assertFalse(PublicationReceipt.objects.exists())

    def test_sender_revocation_holds_effect(self):
        a,c,e,t=self.a,self.c,self.e,self.t;v=response(a,c,e);approve(a,c,e,v)
        d=rfp_documents.draft(a,c.pk,v.pk,t.pk,'client_bid',rev(c));request_review(a,c.pk,d.pk,rev(c));review_version(a,c.pk,d.pk,'approve','Reviewed',rev(c));reserve_publication(a,c.pk,d.pk,rev(c))
        Grant.objects.filter(user=a,case=c,action='rfp.submit').update(active=False);run_publication_once()
        self.assertEqual(PublicationJob.objects.get().status,'held');self.assertFalse(PublicationReceipt.objects.exists())

    def test_matrix_cross_case_duplicate_and_unknown_rejected(self):
        a,c,e=self.a,self.c,self.e;outsider,other=setup_case(username='other-mapping');foreign=add_evidence(outsider,other.pk,'requirements','Foreign','synthetic:foreign')
        base={'key':'R1','evidence_id':foreign.pk,'response':'Foreign mapping','disposition':'addressed'}
        for matrix in [[base],[dict(base,evidence_id=e['requirements'].pk),dict(base,evidence_id=e['requirements'].pk)],[dict(base,evidence_id=e['requirements'].pk,disposition='assumed')]]:
            with self.assertRaises(ValidationError):rfp.prepare_response(a,c.pk,e['rfp_response'].pk,matrix,{k:e[k].pk for k in ['requirements','plan','costing']},rev(c),public_terms_id=e['rfp_commercial_terms'].pk)

    def test_outcome_currentness_prevents_old_win_conversion(self):
        a,c,e,t=self.a,self.c,self.e,self.t;v=response(a,c,e);approve(a,c,e,v);s=submit(a,c,e,t,v)
        won=rfp.outcome(a,c.pk,s.pk,'won',timezone.now(),'Client',e['rfp_outcome'].pk,'Initially won',rev(c))
        rfp.outcome(a,c.pk,s.pk,'unknown',timezone.now(),'Client',e['rfp_outcome'].pk,'Later uncertainty',rev(c))
        with self.assertRaises(ValidationError):rfp.dispose(a,c.pk,won.pk,None,rev(c))

    def test_rfp_histories_invalidate_report_manifest(self):
        from adapters.rfp import reporting_manifest
        a,c,e=self.a,self.c,self.e;before=reporting_manifest(c)
        rfp.contribute(a,c.pk,'QA',e['qa_estimate'].pk,rev(c))
        self.assertNotEqual(before,reporting_manifest(c))

    def test_rfp_period_report_survives_json_roundtrip_review_and_delivery(self):
        from apps.pmo.reporting import draft_period_report,binding_manifest
        a,c,e=self.a,self.c,self.e
        t=register_template(a,c.pk,'RFP status report',{'document_type':'status_report','required_fields':['executive_summary','status'],
            'audience_fields':{'client':['executive_summary','status']}},e['policy_decision'].pk,rev(c))
        artifact(a,c,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[t.pk],'repository':'internal-versioned','retention_days':30},e['policy_decision'])
        now=timezone.now();b=draft_period_report(a,c.pk,'weekly_client',now-timedelta(days=7),now,t.pk,'client',rev(c))
        b.refresh_from_db();self.assertEqual(b.manifest,binding_manifest(b));self.assertFalse(preflight(b.version))
        request_review(a,c.pk,b.version_id,rev(c));review_version(a,c.pk,b.version_id,'approve','Reviewed actual RFP report',rev(c));reserve_publication(a,c.pk,b.version_id,rev(c));run_publication_once()
        self.assertEqual(PublicationReceipt.objects.filter(publication__version_id=b.version_id).count(),1)
        rfp.contribute(a,c.pk,'QA',e['qa_estimate'].pk,rev(c));self.assertTrue(preflight(b.version))

    def test_unbound_typed_rfp_document_cannot_publish(self):
        from apps.documents.controlled import create_version
        a,c,e,t=self.a,self.c,self.e,self.t
        fields={k:{'text':'Unbound assertion','evidence_ids':[e['rfp_response'].pk]} for k in DEFINITION['required_fields']}
        d=create_version(a,c.pk,t.pk,'Unbound response','client',fields,rev(c))
        self.assertTrue(any('source-bound' in f for f in preflight(d)))
        with self.assertRaises(ValidationError):reserve_publication(a,c.pk,d.pk,rev(c))

    def test_distinct_review_principals_and_revoked_engineering_review(self):
        from django.contrib.auth import get_user_model
        a,c,e=self.a,self.c,self.e
        lead=get_user_model().objects.create_user(username='engineering-reviewer')
        Grant.objects.create(case=c,user=lead,action='rfp.review')
        refs=[]
        for role,user in [('PM',a),('Head of PMO',a),('CEO',a),('PMO Lead',a),('Client',a),('Engineering Lead',lead)]:
            refs.append(register_reference(a,c.pk,'distinct:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':user.pk},e['policy_decision'].pk).ref)
        activate(a,c,'D05.role_principal_assignments',refs,e['policy_decision'])
        # Assignment used the old authority snapshot and must be explicitly reaffirmed.
        rfp.assign(a,c.pk,a,'CEO',e['policy_decision'].pk,'Reaffirm exact current assignment',rev(c))
        v=response(a,c,e)
        with self.assertRaises(PermissionDenied):rfp.review(a,c.pk,v.pk,'Engineering Lead','approve',e['policy_decision'].pk,'Wrong principal',rev(c))
        rfp.review(lead,c.pk,v.pk,'Engineering Lead','approve',e['policy_decision'].pk,'Engineering human review',rev(c))
        rfp.review(a,c.pk,v.pk,'PMO Lead','approve',e['policy_decision'].pk,'Separate PMO review',rev(c))
        self.assertEqual(len(rfp.reviewed(v)),2)
        Grant.objects.filter(case=c,user=lead,action='rfp.review').update(active=False)
        with self.assertRaises(PermissionDenied):rfp.reviewed(v)


class RFPConcurrencyTests(TransactionTestCase):
    def test_two_postgres_connections_convert_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import close_old_connections,connections
        from django.contrib.auth import get_user_model
        a,c,e,t,_=fixture();v=response(a,c,e);approve(a,c,e,v);s=submit(a,c,e,t,v)
        o=rfp.outcome(a,c.pk,s.pk,'won',timezone.now(),'Client',e['rfp_outcome'].pk,'Actual synthetic win',rev(c))
        def convert(_):
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=a.pk)
                return rfp.dispose(actor,c.pk,o.pk,None,None).kind
            except ValidationError:return 'already_recorded'
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(convert,range(2)))
        self.assertCountEqual(results,['route_a','already_recorded']);self.assertEqual(RFPDisposition.objects.count(),1)
