from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import DatabaseError, transaction, connection
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from apps.core.models import Evidence
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.models import Configuration
from apps.policy.services import register_reference, decision_authority, transition, PolicyHold
from apps.pmo.models import (Baseline, CommercialCase, CommercialRevision, CommercialDecision, CommercialDocumentBinding,
    BaselineAdoption, ClientResponse, ChangeAssessment, ChangeAuthorization)
from apps.pmo.commercial import (propose, decide_proposal, draft_submission, capture_response, adopt_signed, valid_approvals, SOURCE_KINDS)
from apps.pmo.changes import log_change, assess_change, decide_change, authorize_change, CONTRIBUTORS, required_roles
from apps.pmo.services import prepare_baseline, decide, sign_baseline
from apps.documents.controlled import register_template, request_review, review_version, reserve_publication, preflight
from apps.documents.delivery import run_publication_once as run_once
from apps.documents.models import PublicationReceipt
from apps.agents.commercial import investigate_proposal
from .helpers import setup_case, project_evidence, roles, rev, signed, activate, envelope
from .document_helpers import artifact

DEFINITION={'document_type':'sow','required_fields':['executive_summary','scope','timeline'],
    'audience_fields':{'client':['executive_summary','scope','timeline']}}


def fixture(existing=False,username='human'):
    actor,case=setup_case(username=username)
    e=signed(actor,case) if existing else project_evidence(actor,case)
    if not existing:roles(actor,case,e['policy_decision'])
    template=register_template(actor,case.pk,'Commercial SOW',DEFINITION,e['policy_decision'].pk,rev(case))
    r=register_reference(actor,case.pk,'commercial:recipient','schema:psl/document-recipient/v1',{'audience':'client','user_id':actor.pk},e['policy_decision'].pk)
    activate(actor,case,'D11.recipient_grant_refs',[r.ref],e['policy_decision'])
    artifact(actor,case,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',
        {'template_ids':[template.pk],'repository':'internal-versioned','retention_days':30},e['policy_decision'])
    return actor,case,e,template


def proposal(actor,case,e,context=None):
    return propose(actor,case.pk,{k:e[k].pk for k in SOURCE_KINDS},(context or e['requirements']).pk,'Explicit proposal rationale',rev(case))


def approvals(actor,case,v):
    for role in ['PM','Head of PMO','CEO','PMO Lead']:
        decide_proposal(actor,case.pk,v.pk,role,'approve','Checked exact sources',rev(case))


def delivered(actor,case,v,t):
    version=draft_submission(actor,case.pk,v.pk,t.pk,rev(case))
    request_review(actor,case.pk,version.pk,rev(case))
    review_version(actor,case.pk,version.pk,'approve','Reviewed client version',rev(case))
    reserve_publication(actor,case.pk,version.pk,rev(case))
    assert run_once()
    return PublicationReceipt.objects.get(publication__version=version)


def change_roles(actor,case,owner):
    refs=[]
    for role in ['PM','Head of PMO','CEO','PMO Lead','Product','Engineering','Client','Engineering Lead','Security Manager']:
        r=register_reference(actor,case.pk,'expanded:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':actor.pk},owner.pk)
        refs.append(r.ref)
    return activate(actor,case,'D05.role_principal_assignments',refs,owner)


class CommercialTests(TestCase):
    def setUp(self):self.actor,self.case,self.e,self.t=fixture()

    def test_staff_proposal_decisions_review_delivery_and_signed_adoption(self):
        a,c,e,t=self.actor,self.case,self.e,self.t
        self.client.force_login(a);url=f'/cases/{c.pk}/commercial/'
        data={k:e[k].pk for k in SOURCE_KINDS};data.update(action='propose',context=e['requirements'].pk,reason='Staff reviewed version',revision=rev(c))
        self.assertEqual(self.client.post(url,data).status_code,302)
        v=CommercialRevision.objects.get()
        for role in ['PM','Head of PMO','CEO','PMO Lead']:
            self.assertEqual(self.client.post(url,{'action':'decide','proposal':v.pk,'role':role,'verdict':'approve','note':'Staff checked source','revision':rev(c)}).status_code,302)
        self.assertContains(self.client.get(url),'Current proposal')
        receipt=delivered(a,c,v,t)
        response=capture_response(a,c.pk,v.pk,receipt.pk,'signed',e['signature'].pk,'PM verified matching signed artifact',rev(c))
        adoption=adopt_signed(a,c.pk,v.pk,response.pk,rev(c))
        self.assertEqual(Baseline.objects.get().signed_id,e['signature'].pk)
        self.assertEqual(adoption.before,{})
        self.assertEqual(connection.vendor,'postgresql')
        self.assertEqual(len(adoption.after),4)
        self.assertContains(self.client.get(url),'Adopted signed baseline')
        self.assertContains(self.client.get(url),'Finance intake receipt')
        self.assertFalse(investigate_proposal(a,c.pk,v.pk,rev(c)).result['approval_granted'])
        workspace=self.client.get(f'/cases/{c.pk}/')
        self.assertContains(workspace,f'href="/cases/{c.pk}/commercial/"')

    def test_drafting_needs_no_policy_but_order_and_submission_do(self):
        a,c,e,t=self.actor,self.case,self.e,self.t
        v=proposal(a,c,e)
        with self.assertRaises(ValidationError):decide_proposal(a,c.pk,v.pk,'CEO','approve','Reason',rev(c))
        with self.assertRaises(ValidationError):draft_submission(a,c.pk,v.pk,t.pk,rev(c))
        self.assertEqual(v.decisions.count(),0)
        # Missing optional reuse/return/delegation components never hold direct prescribed approvals.
        approvals(a,c,v);self.assertEqual(len(valid_approvals(v)),4)

    def test_return_reject_and_withdraw_require_config_and_new_revision(self):
        a,c,e,t=self.actor,self.case,self.e,self.t
        v=proposal(a,c,e)
        with self.assertRaises(PolicyHold):decide_proposal(a,c.pk,v.pk,'PM','return','Return reason',rev(c))
        artifact(a,c,'D05.decision_action_matrix','schema:psl/decision-actions/v1',{'rules':[{'role':'PM','actions':['return','reject','withdraw']}]},e['policy_decision'])
        decide_proposal(a,c.pk,v.pk,'PM','return','Revise source',rev(c))
        with self.assertRaises(ValidationError):approvals(a,c,v)
        self.assertEqual(v.decisions.count(),1)
        e=dict(e,sow=add_evidence(a,c.pk,'sow','Revised SOW','synthetic:revision'))
        v2=proposal(a,c,e)
        approvals(a,c,v2)
        self.assertEqual(v2.decisions.count(),4)

    def test_changed_cost_never_inherits_cost_chain(self):
        a,c,e,t=self.actor,self.case,self.e,self.t
        v=proposal(a,c,e);approvals(a,c,v)
        artifact(a,c,'D05.revision_invalidation_rules','schema:psl/commercial-revision/v1',
            {'unchanged_subject_reuse_roles':['PM','Head of PMO','CEO'],'changed_cost_requires_full_chain':True},e['policy_decision'])
        sources=dict(v.sources,costing=add_evidence(a,c.pk,'costing','Changed cost evidence','synthetic:cost').pk)
        v2=propose(a,c.pk,sources,e['requirements'].pk,'Changed cost',rev(c),True)
        self.assertEqual(v2.decisions.count(),0)

    def test_optional_reuse_is_typed_current_and_independent(self):
        a,c,e,t=self.actor,self.case,self.e,self.t
        v=proposal(a,c,e);approvals(a,c,v)
        sources=dict(v.sources,sow=add_evidence(a,c.pk,'sow','Revised outward clauses','synthetic:feedback').pk)
        with self.assertRaises(PolicyHold):propose(a,c.pk,sources,e['requirements'].pk,'Revise',rev(c),True)
        self.assertEqual(CommercialRevision.objects.count(),1)
        cfg=artifact(a,c,'D05.revision_invalidation_rules','schema:psl/commercial-revision/v1',
            {'unchanged_subject_reuse_roles':['PM','Head of PMO','CEO'],'changed_cost_requires_full_chain':True},e['policy_decision'])
        v2=propose(a,c.pk,sources,e['requirements'].pk,'Non-cost clauses',rev(c),True)
        self.assertEqual(v2.decisions.count(),3)
        decide_proposal(a,c.pk,v2.pk,'PMO Lead','approve','Reviewed changed clauses',rev(c))
        valid_approvals(v2)
        transition(a,cfg.pk,'revoked')
        with self.assertRaises(PolicyHold):valid_approvals(v2)

    def test_invalid_reuse_rule_and_cross_case_source(self):
        a,c,e,t=self.actor,self.case,self.e,self.t
        with self.assertRaises(ValidationError):artifact(a,c,'D05.revision_invalidation_rules','schema:psl/commercial-revision/v1',
            {'unchanged_subject_reuse_roles':['CEO'],'changed_cost_requires_full_chain':False},e['policy_decision'])
        other_actor,other=setup_case(username='other')
        foreign_source=add_evidence(other_actor,other.pk,'plan','Other case plan','synthetic:foreign')
        foreign_ids={k:e[k].pk for k in SOURCE_KINDS};foreign_ids['plan']=foreign_source.pk
        with self.assertRaises(ValidationError):propose(a,c.pk,foreign_ids,e['requirements'].pk,'Foreign source',rev(c))
        foreign=add_evidence(a,c.pk,'plan','Other local plan','source')
        sources={k:e[k].pk for k in SOURCE_KINDS};sources['plan']=foreign.pk
        # Valid local plan with unchanged cost is allowed only before a prior plan exists.
        proposal(a,c,e)
        with self.assertRaises(ValidationError):propose(a,c.pk,sources,e['requirements'].pk,'Changed plan',rev(c))

    def test_reuse_policy_supersession_expiry_and_stale_hash(self):
        from apps.policy.services import resolve, save_draft
        a,c,e,t=self.actor,self.case,self.e,self.t
        v=proposal(a,c,e);approvals(a,c,v)
        content={'unchanged_subject_reuse_roles':['PM','Head of PMO','CEO'],'changed_cost_requires_full_chain':True}
        config=artifact(a,c,'D05.revision_invalidation_rules','schema:psl/commercial-revision/v1',content,e['policy_decision'])
        sources=dict(v.sources,sow=add_evidence(a,c.pk,'sow','Changed terms','synthetic:terms').pk)
        v2=propose(a,c.pk,sources,e['requirements'].pk,'Non-cost clause',rev(c),True)
        artifact(a,c,'D05.revision_invalidation_rules','schema:psl/commercial-revision/v1',content,e['policy_decision'])
        with self.assertRaises(ValidationError):valid_approvals(v2,['PM'])
        r=register_reference(a,c.pk,'reuse:expiry','schema:psl/commercial-revision/v1',content,e['policy_decision'].pk)
        value={'artifact_ref':r.ref,'artifact_version':r.version,'sha256':r.sha256,'schema_ref':r.schema_ref}
        env=envelope(c,'D05.revision_invalidation_rules',value,e['policy_decision'])
        env['effective_from']=(timezone.now()-timedelta(days=2)).isoformat()
        env['effective_until']=(timezone.now()-timedelta(days=1)).isoformat()
        expired=save_draft(a,c.pk,env);transition(a,expired.pk,'validated');transition(a,expired.pk,'active')
        self.assertEqual(resolve('D05.revision_invalidation_rules',c).status,'EXPIRED')
        invalid=envelope(c,'D05.revision_invalidation_rules',dict(value,sha256='0'*64),e['policy_decision'])
        draft=save_draft(a,c.pk,invalid)
        with self.assertRaises(ValidationError):transition(a,draft.pk,'validated')

    def test_queued_proposal_is_held_after_source_revision(self):
        from apps.documents.models import PublicationJob
        a,c,e,t=self.actor,self.case,self.e,self.t
        v=proposal(a,c,e);approvals(a,c,v)
        doc=draft_submission(a,c.pk,v.pk,t.pk,rev(c))
        request_review(a,c.pk,doc.pk,rev(c));review_version(a,c.pk,doc.pk,'approve','Current outward review',rev(c))
        publication=reserve_publication(a,c.pk,doc.pk,rev(c))
        e=dict(e,sow=add_evidence(a,c.pk,'sow','New outward clauses','synthetic:new'))
        proposal(a,c,e)
        self.assertTrue(run_once())
        self.assertEqual(PublicationJob.objects.get(publication=publication).status,'held')
        self.assertFalse(PublicationReceipt.objects.exists())

    def test_manual_sow_cannot_bypass_commercial_approvals(self):
        from apps.documents.controlled import create_version
        a,c,e,t=self.actor,self.case,self.e,self.t
        fields={key:{'text':'Unbound outward content','evidence_ids':[e['sow'].pk]} for key in ['executive_summary','scope','timeline']}
        version=create_version(a,c.pk,t.pk,'Unbound SOW','client',fields,rev(c))
        self.assertTrue(preflight(version))
        with self.assertRaises(ValidationError):request_review(a,c.pk,version.pk,rev(c))

    def test_legacy_actions_cannot_bypass_versioned_workbench(self):
        a,c,e,t=self.actor,self.case,self.e,self.t;proposal(a,c,e)
        with self.assertRaises(ValidationError):prepare_baseline(a,c.pk,e['plan'].pk,e['costing'].pk,e['sow'].pk,rev(c))
        with self.assertRaises(ValidationError):decide(a,c.pk,'PM',rev(c))
        with self.assertRaises(ValidationError):sign_baseline(a,c.pk,e['signature'].pk,rev(c))

    def test_decision_revocation_holds_outward_version(self):
        a,c,e,t=self.actor,self.case,self.e,self.t;v=proposal(a,c,e);approvals(a,c,v)
        version=draft_submission(a,c.pk,v.pk,t.pk,rev(c))
        Grant.objects.filter(user=a,case=c,action='commercial.decide').update(active=False)
        self.assertTrue(preflight(version))
        with self.assertRaises(ValidationError):request_review(a,c.pk,version.pk,rev(c))

    def test_new_proposal_invalidates_queued_document_and_keeps_old_response_capture(self):
        a,c,e,t=self.actor,self.case,self.e,self.t;v=proposal(a,c,e);approvals(a,c,v)
        receipt=delivered(a,c,v,t)
        e=dict(e,sow=add_evidence(a,c.pk,'sow','New outward content','synthetic:revision'))
        proposal(a,c,e)
        feedback=add_evidence(a,c.pk,'client_feedback','Late feedback on first version','synthetic:client')
        response=capture_response(a,c.pk,v.pk,receipt.pk,'feedback',feedback.pk,'Late source linked',rev(c))
        self.assertEqual(response.revision_id,v.pk)
        with self.assertRaises(ValidationError):adopt_signed(a,c.pk,v.pk,response.pk,rev(c))

    def test_grants_staleness_and_history_protection(self):
        a,c,e,t=self.actor,self.case,self.e,self.t;v=proposal(a,c,e)
        with self.assertRaises(ValidationError):decide_proposal(a,c.pk,v.pk,'PM','approve','reason',rev(c)-1)
        with self.assertRaises(DatabaseError),transaction.atomic():CommercialRevision.objects.filter(pk=v.pk).update(reason='rewrite')
        other_actor,other=setup_case(username='outsider');other_e=project_evidence(other_actor,other)
        foreign=proposal(other_actor,other,other_e)
        with self.assertRaises(DatabaseError),transaction.atomic():CommercialCase.objects.filter(case=c).update(current=foreign)
        admin=get_user_model().objects.create_superuser('admin','admin@example.test','test-only')
        with self.assertRaises(PermissionDenied):decide_proposal(admin,c.pk,v.pk,'PM','approve','reason',rev(c))
        self.client.force_login(other_actor);self.assertEqual(self.client.get(f'/cases/{c.pk}/commercial/').status_code,404)

    def test_bounded_agent_compares_sources_without_decisions(self):
        a,c,e,t=self.actor,self.case,self.e,self.t;v=proposal(a,c,e)
        run=investigate_proposal(a,c.pk,v.pk,rev(c))
        self.assertFalse(run.result['approval_granted']);self.assertFalse(run.result['cost_calculated'])
        self.assertEqual(len(run.result['changed_sources']),6)
        self.assertEqual(v.decisions.count(),0)

    def test_explicit_delegation_current_and_expired(self):
        a,c,e,t=self.actor,self.case,self.e,self.t;v=proposal(a,c,e)
        delegate=get_user_model().objects.create_user('delegate')
        Grant.objects.create(user=delegate,case=c,action='commercial.decide')
        r=register_reference(a,c.pk,'pm:delegate','schema:psl/decision-delegation/v1',{'role':'PM','principal_id':a.pk,'delegate_id':delegate.pk,
            'valid_from':(timezone.now()-timedelta(hours=1)).isoformat(),'valid_until':(timezone.now()+timedelta(hours=1)).isoformat()},e['policy_decision'].pk)
        cfg=activate(a,c,'D05.delegation_rules',[r.ref],e['policy_decision'])
        with self.assertRaises(PermissionDenied):decide_proposal(delegate,c.pk,v.pk,'PM','approve','reason',rev(c))
        decide_proposal(delegate,c.pk,v.pk,'PM','approve','Delegated review',rev(c),True)
        transition(a,cfg.pk,'revoked')
        with self.assertRaises(PolicyHold):valid_approvals(v,['PM'])


def weekly_change_report(actor,case,evidence):
    from datetime import timedelta
    from django.utils import timezone
    from apps.pmo.reporting import draft_period_report
    template=register_template(actor,case.pk,'Synthetic weekly change report',{'document_type':'status_report','required_fields':['executive_summary','status'],
        'audience_fields':{'client':['executive_summary','status','timeline']}},evidence.pk,rev(case))
    now=timezone.now()
    return draft_period_report(actor,case.pk,'weekly_client',now-timedelta(days=7),now,template.pk,'client',rev(case))


def impact_fixture(team, timeline=False):
    # Explicit synthetic owner statements, never production defaults.
    return {'outputs':{'discipline':team+' reviewed its synthetic discipline impact',
        'timeline':'Milestone moves from 2026-11-10 to 2026-11-12' if timeline else 'No timeline change',
        'cost_resource':'No additional resources in this synthetic fixture',
        'risk':'No additional risk in this synthetic fixture',
        'dependency':'No additional dependency in this synthetic fixture'},
        'production_impact':False if team=='Infra' else None,
        'scope_items':['CR-001/item-1'] if team=='Engineering' else None}


class ControlledChangeTests(TestCase):
    def setUp(self):
        self.actor,self.case,self.e,self.t=fixture(existing=True)
        change_roles(self.actor,self.case,self.e['policy_decision'])
        self.source=add_evidence(self.actor,self.case.pk,'change_request','Client requests a scope change','synthetic:change')
        self.cv=log_change(self.actor,self.case.pk,'CR-001','Normal','Delivery','New work requested','Client evidence',self.source.pk,rev(self.case))

    def assessments(self,cost=True,timeline=True,client=True):
        for team in CONTRIBUTORS:assess_change(self.actor,self.case.pk,self.cv.pk,team,cost,timeline,client,self.source.pk,'Owner impact assessment',rev(self.case),**impact_fixture(team,timeline))

    def decisions(self):
        for role in ['Product','Engineering','Client','Engineering Lead','Security Manager']:
            decide_change(self.actor,self.case.pk,self.cv.pk,role,'approve',self.source.pk,'Owner decision',rev(self.case))

    def revised_commercial(self):
        e=dict(self.e)
        for k in ['plan','costing','sow','signature']:e[k]=add_evidence(self.actor,self.case.pk,k,'Revised '+k,'synthetic:change')
        v=proposal(self.actor,self.case,e,self.source);approvals(self.actor,self.case,v)
        return v,e

    def test_signed_scope_replacement_requires_current_controlled_change(self):
        a,c=self.actor,self.case
        self.assessments();self.decisions();v,e=self.revised_commercial()
        receipt=delivered(a,c,v,self.t)
        response=capture_response(a,c.pk,v.pk,receipt.pk,'signed',e['signature'].pk,'Matching new signed document',rev(c))
        with self.assertRaises(ValidationError):adopt_signed(a,c.pk,v.pk,response.pk,rev(c))
        auth=authorize_change(a,c.pk,self.cv.pk,v.pk,rev(c))
        before=Baseline.objects.get(case=c).signed_id
        adoption=adopt_signed(a,c.pk,v.pk,response.pk,rev(c))
        self.assertEqual(adoption.before['signed_id'],before)
        self.assertEqual(Baseline.objects.get(case=c).signed_id,e['signature'].pk)
        self.assertEqual(auth.commercial_id,v.pk)
        with self.assertRaises(DatabaseError),transaction.atomic():Baseline.objects.filter(case=c).update(sow=self.e['sow'])
        with self.assertRaises(DatabaseError),transaction.atomic():BaselineAdoption.objects.filter(pk=adoption.pk).update(before={})

    def test_unknowns_and_missing_contributors_hold_only_authorization(self):
        a,c=self.actor,self.case
        with self.assertRaises(ValidationError):authorize_change(a,c.pk,self.cv.pk,None,rev(c))
        self.assessments(cost=None)
        with self.assertRaises(ValidationError):self.decisions()
        self.assertEqual(ChangeAssessment.objects.count(),4)
        self.assertEqual(ChangeAuthorization.objects.count(),0)

    def test_changed_assessment_invalidates_decisions_and_authorization(self):
        a,c=self.actor,self.case;self.assessments();self.decisions();v,e=self.revised_commercial()
        authorize_change(a,c.pk,self.cv.pk,v.pk,rev(c))
        assess_change(a,c.pk,self.cv.pk,'QA',False,False,False,self.source.pk,'New assessment',rev(c))
        from apps.pmo.changes import require_change_for_adoption
        with self.assertRaises(ValidationError):require_change_for_adoption(c,v)

    def test_cost_impact_requires_approved_commercial_context(self):
        self.assessments();self.decisions()
        with self.assertRaises(ValidationError):authorize_change(self.actor,self.case.pk,self.cv.pk,None,rev(self.case))
        v,e=self.revised_commercial()
        self.assertIsNotNone(authorize_change(self.actor,self.case.pk,self.cv.pk,v.pk,rev(self.case)))

    def test_no_cost_timeline_or_client_impact_needs_only_source_roles(self):
        self.assessments(False,False,False)
        for role in ['Product','Engineering']:decide_change(self.actor,self.case.pk,self.cv.pk,role,'approve',self.source.pk,'Owner decision',rev(self.case))
        result=authorize_change(self.actor,self.case.pk,self.cv.pk,None,rev(self.case))
        self.assertEqual(len(result.decision_ids),2)

    def test_standard_emergency_intake_does_not_invent_a_waiver(self):
        a,c=self.actor,self.case
        v=log_change(a,c.pk,'CR-STD','Standard','API','Catalogue candidate','Needs owner policy',self.source.pk,rev(c))
        for team in CONTRIBUTORS:assess_change(a,c.pk,v.pk,team,False,False,False,self.source.pk,'Assessment',rev(c))
        for role in ['Product','Engineering']:decide_change(a,c.pk,v.pk,role,'approve',self.source.pk,'Owner decision',rev(c))
        with self.assertRaises(ValidationError):authorize_change(a,c.pk,v.pk,None,rev(c))
        with self.assertRaises(ValidationError):log_change(a,c.pk,'CR-EM','Emergency','API','Emergency request','Incident required',self.source.pk,rev(c))
        incident=add_evidence(a,c.pk,'incident','External incident identity','synthetic:incident')
        emergency=log_change(a,c.pk,'CR-EM','Emergency','API','Emergency request','Incident linked',self.source.pk,rev(c),incident.pk)
        self.assertEqual(emergency.incident_id,incident.pk)

    def test_change_ui_and_access_and_immutable_records(self):
        a,c=self.actor,self.case;self.client.force_login(a)
        url=f'/cases/{c.pk}/changes/'
        self.assertContains(self.client.get(url),'CR-001')
        response=self.client.post(url,{'action':'assess','revision':rev(c),'version':self.cv.pk,'contributor':'QA','cost_impact':'unknown',
            'timeline_impact':'false','client_facing':'true','evidence':self.source.pk,'note':'Staff impact evidence'})
        self.assertEqual(response.status_code,302)
        assessment=ChangeAssessment.objects.get();self.assertIsNone(assessment.cost_impact)
        with self.assertRaises(DatabaseError),transaction.atomic():ChangeAssessment.objects.filter(pk=assessment.pk).update(cost_impact=False)
        Grant.objects.filter(user=a,case=c,action='change.assess:QA').update(active=False)
        with self.assertRaises(PermissionDenied):assess_change(a,c.pk,self.cv.pk,'QA',False,False,False,self.source.pk,'Reason',rev(c))


class ChangeExecutionTests(TestCase):
    setUp = ControlledChangeTests.setUp
    assessments = ControlledChangeTests.assessments

    def authorized(self):
        self.assessments(False,False,False)
        for role in ['Product','Engineering']:
            decide_change(self.actor,self.case.pk,self.cv.pk,role,'approve',self.source.pk,'Owner decision',rev(self.case))
        return authorize_change(self.actor,self.case.pk,self.cv.pk,None,rev(self.case))

    def ready(self,auth):
        from apps.pmo.change_execution import record_execution
        evidence={}
        for kind,e_kind in [('plan_updated','plan'),('implemented','change_implementation'),('testing_validated','change_validation'),('documentation_updated','document')]:
            source=add_evidence(self.actor,self.case.pk,e_kind,'Owner evidence '+kind,'synthetic:execution')
            evidence[kind]=record_execution(self.actor,self.case.pk,auth.pk,kind,source.pk,'Captured exact change evidence',rev(self.case),scope_items=['CR-001/item-1'] if kind=='implemented' else None)
        return evidence

    def change_template(self):
        t=register_template(self.actor,self.case.pk,'Change status',{'document_type':'project_artifact','required_fields':['executive_summary','status'],
            'audience_fields':{'client':['executive_summary','scope','status','timeline','next_steps']}},self.e['policy_decision'].pk,rev(self.case))
        artifact(self.actor,self.case,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',
            {'template_ids':[self.t.pk,t.pk],'repository':'internal-versioned','retention_days':30},self.e['policy_decision'])
        return t

    def publish_change(self,auth,t,purpose):
        from apps.pmo.change_execution import draft_change_document
        v=draft_change_document(self.actor,self.case.pk,auth.pk,t.pk,purpose,rev(self.case))
        request_review(self.actor,self.case.pk,v.pk,rev(self.case))
        review_version(self.actor,self.case.pk,v.pk,'approve','Exact change document review',rev(self.case))
        reserve_publication(self.actor,self.case.pk,v.pk,rev(self.case));self.assertTrue(run_once())
        return PublicationReceipt.objects.get(publication__version=v)

    def test_execution_reviewed_notice_golive_and_closure(self):
        from apps.pmo.change_execution import close_change, record_execution
        from apps.pmo.models import ChangeClosure
        auth=self.authorized();t=self.change_template()
        notice=self.publish_change(auth,t,'notice')
        self.ready(auth);receipt=self.publish_change(auth,t,'go_live')
        pm=add_evidence(self.actor,self.case.pk,'signature','PM signature of exact change go-live','synthetic:PM')
        client=add_evidence(self.actor,self.case.pk,'signature','Client signature of exact change go-live','synthetic:Client')
        closure=close_change(self.actor,self.case.pk,auth.pk,receipt.pk,pm.pk,client.pk,'PM verified both signatures on receipt version',rev(self.case))
        self.assertEqual(len(closure.execution_ids),4)
        self.assertEqual(ChangeClosure.objects.count(),1)
        with self.assertRaises(ValidationError):assess_change(self.actor,self.case.pk,self.cv.pk,'QA',False,False,False,self.source.pk,'After close',rev(self.case))
        from apps.pmo.change_execution import draft_change_document
        with self.assertRaises(ValidationError):draft_change_document(self.actor,self.case.pk,auth.pk,t.pk,'notice',rev(self.case))
        with self.assertRaises(ValidationError):record_execution(self.actor,self.case.pk,auth.pk,'plan_updated',self.e['plan'].pk,'After close',rev(self.case))
        with self.assertRaises(DatabaseError),transaction.atomic():ChangeClosure.objects.filter(pk=closure.pk).update(note='Rewrite')
        self.client.force_login(self.actor)
        self.assertContains(self.client.get(f'/cases/{self.case.pk}/changes/'),'Authorization #')

    def test_new_implementation_holds_old_golive_until_revalidated_and_reviewed(self):
        from apps.pmo.change_execution import record_execution, draft_change_document
        auth=self.authorized();t=self.change_template();self.ready(auth)
        receipt=self.publish_change(auth,t,'go_live')
        source=add_evidence(self.actor,self.case.pk,'change_implementation','New implementation revision','synthetic:new-build')
        record_execution(self.actor,self.case.pk,auth.pk,'implemented',source.pk,'New build reference',rev(self.case))
        self.assertTrue(preflight(receipt.publication.version))
        with self.assertRaises(ValidationError):draft_change_document(self.actor,self.case.pk,auth.pk,t.pk,'go_live',rev(self.case))

    def test_partial_execution_and_foreign_receipt_cannot_close(self):
        from apps.pmo.change_execution import close_change, draft_change_document
        auth=self.authorized();t=self.change_template()
        with self.assertRaises(ValidationError):draft_change_document(self.actor,self.case.pk,auth.pk,t.pk,'go_live',rev(self.case))
        with self.assertRaises(ValidationError):close_change(self.actor,self.case.pk,auth.pk,999,self.e['signature'].pk,self.e['signature'].pk,'No evidence',rev(self.case))


class SignedIntakeTests(TestCase):
    def test_atomic_receipt_and_signature_reference_cannot_be_reused(self):
        from apps.finance.models import SignedBaselineIntake
        from adapters.signed_baselines import InternalSignedBaselineAdapter
        a,c,e,t=fixture();v=proposal(a,c,e);approvals(a,c,v);receipt=delivered(a,c,v,t)
        response=capture_response(a,c.pk,v.pk,receipt.pk,'signed',e['signature'].pk,'Matched signed artifact',rev(c))
        adoption=adopt_signed(a,c.pk,v.pk,response.pk,rev(c))
        intake=SignedBaselineIntake.objects.get()
        self.assertEqual(intake.payload['sources']['sow']['sha256'],e['sow'].sha256)
        self.assertIsNone(intake.payload['agreed_billing_schedule'])
        self.assertFalse(intake.payload['invoice_created'])
        self.assertEqual(InternalSignedBaselineAdapter().deliver(adoption).pk,intake.pk)
        with self.assertRaises(DatabaseError),transaction.atomic():SignedBaselineIntake.objects.filter(pk=intake.pk).update(payload={})
        with self.assertRaises(ValidationError):adopt_signed(a,c.pk,v.pk,response.pk,rev(c))
        self.assertEqual(SignedBaselineIntake.objects.count(),1)


from concurrent.futures import ThreadPoolExecutor
from django.db import close_old_connections
from django.test import TransactionTestCase

class CommercialConcurrencyTests(TransactionTestCase):
    def test_two_postgresql_connections_adopt_once(self):
        from apps.finance.models import SignedBaselineIntake
        a,c,e,t=fixture();v=proposal(a,c,e);approvals(a,c,v);receipt=delivered(a,c,v,t)
        response=capture_response(a,c.pk,v.pk,receipt.pk,'signed',e['signature'].pk,'Matching signed artifact',rev(c))
        expected=rev(c)
        def adopt():
            close_old_connections()
            try:
                adopt_signed(a,c.pk,v.pk,response.pk,expected)
                return 'adopted'
            except ValidationError:return 'stale'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:adopt(),range(2)))
        self.assertCountEqual(results,['adopted','stale'])
        self.assertEqual(BaselineAdoption.objects.count(),1)
        self.assertEqual(SignedBaselineIntake.objects.count(),1)
