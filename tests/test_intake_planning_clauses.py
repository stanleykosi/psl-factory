"""Additive C09-C14 semantic contrasts; synthetic sources, no live acceptance."""
import copy
import json
from pathlib import Path
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.services import add_evidence
from apps.core.models import Audit, Case
from apps.documents.models import Publication, PublicationReceipt
from apps.pmo import commercial, engagement
from apps.pmo.models import Baseline, BaselineAdoption, ClientResponse
from tests.helpers import rev
from tests import test_commercial_changes as ch


class IntakeCommercialClauses(TestCase):
    def test_c09_exact_eligible_before_any_submission_or_signature(self):
        a,c,e,t=ch.fixture();v=ch.proposal(a,c,e)
        retained=list(Audit.objects.filter(case=c).values_list('pk',flat=True))
        with self.assertRaises(ValidationError):commercial.draft_submission(a,c.pk,v.pk,t.pk,rev(c))
        with self.assertRaises(ValidationError):commercial.decide_proposal(a,c.pk,v.pk,'CEO','approve','Premature CEO',rev(c))
        self.assertEqual(list(Audit.objects.filter(case=c).values_list('pk',flat=True)),retained)
        for role in ['PM','Head of PMO','CEO']:
            commercial.decide_proposal(a,c.pk,v.pk,role,'approve','Exact current cost',rev(c))
        with self.assertRaises(ValidationError):commercial.valid_approvals(v)
        commercial.decide_proposal(a,c.pk,v.pk,'PMO Lead','approve','Separate exact outward review',rev(c))
        decisions=list(v.decisions.order_by('pk'))
        self.assertEqual(commercial.valid_approvals(v),[d.pk for d in decisions])
        self.assertEqual([d.role for d in decisions],['PM','Head of PMO','CEO','PMO Lead'])
        self.assertEqual(v.sources,{k:e[k].pk for k in commercial.SOURCE_KINDS})
        draft=commercial.draft_submission(a,c.pk,v.pk,t.pk,rev(c))
        self.assertEqual(draft.commercialdocumentbinding.revision_id,v.pk)
        self.assertFalse(draft.reviews.exists())
        self.assertFalse(Publication.objects.exists());self.assertFalse(PublicationReceipt.objects.exists())
        self.assertFalse(ClientResponse.objects.exists());self.assertFalse(BaselineAdoption.objects.exists())
        self.assertFalse(Baseline.objects.filter(signed__isnull=False).exists())
        self.assertTrue(set(retained).issubset(set(Audit.objects.filter(case=c).values_list('pk',flat=True))))

    def test_c13_delivered_feedback_new_scope_and_cost_need_fresh_exact_chain(self):
        a,c,e,t=ch.fixture();v=ch.proposal(a,c,e);ch.approvals(a,c,v)
        receipt=ch.delivered(a,c,v,t)
        before=PublicationReceipt.objects.filter(pk=receipt.pk).values().get()
        prior_decisions=list(v.decisions.values())
        feedback=add_evidence(a,c.pk,'client_feedback','Client requests added rollout scope and revised price','synthetic:client-feedback')
        response=commercial.capture_response(a,c.pk,v.pk,receipt.pk,'feedback',feedback.pk,'Feedback on exact delivered v1',rev(c))
        sources=dict(v.sources)
        for kind in ['plan','costing','sow']:
            sources[kind]=add_evidence(a,c.pk,kind,'Revised '+kind+' including rollout and changed cost','synthetic:feedback-revision').pk
        v2=commercial.propose(a,c.pk,sources,feedback.pk,'Source-backed scope and cost revision',rev(c))
        self.assertEqual(response.revision_id,v.pk);self.assertEqual(response.receipt_id,receipt.pk)
        self.assertEqual(v2.context_id,feedback.pk);self.assertFalse(v2.decisions.exists())
        with self.assertRaises(ValidationError):commercial.draft_submission(a,c.pk,v2.pk,t.pk,rev(c))
        for role in ['PM','Head of PMO','CEO']:
            commercial.decide_proposal(a,c.pk,v2.pk,role,'approve','Current changed-cost version',rev(c))
        with self.assertRaises(ValidationError):commercial.draft_submission(a,c.pk,v2.pk,t.pk,rev(c))
        commercial.decide_proposal(a,c.pk,v2.pk,'PMO Lead','approve','Current changed outward version',rev(c))
        new_receipt=ch.delivered(a,c,v2,t)
        self.assertNotEqual(new_receipt.pk,receipt.pk)
        self.assertNotEqual(new_receipt.publication.version_id,receipt.publication.version_id)
        self.assertTrue(all(d.inherited_id is None for d in v2.decisions.all()))
        self.assertEqual(list(v.decisions.values()),prior_decisions)
        self.assertEqual(PublicationReceipt.objects.filter(pk=receipt.pk).values().get(),before)
        with self.assertRaises(ValidationError):commercial.capture_response(a,c.pk,v2.pk,receipt.pk,'feedback',feedback.pk,'Wrong delivered revision',rev(c))
        self.assertEqual(ClientResponse.objects.get().pk,response.pk)
        self.assertFalse(BaselineAdoption.objects.exists())

    def test_c11_same_won_conversion_distinct_capture_receipts_one_identity(self):
        from tests import test_rfp as r
        from tests.test_engagement_intake import activate
        from apps.policy.engagement_validators import ASSIGN,REGISTER
        a,c,e,t,_=r.fixture();v=r.response(a,c,e);r.approve(a,c,e,v);submission=r.submit(a,c,e,t,v)
        outcome=r.rfp.outcome(a,c.pk,submission.pk,'won',timezone.now(),'Client',e['rfp_outcome'].pk,'Synthetic evidenced win',rev(c))
        conversion=r.rfp.dispose(a,c.pk,outcome.pk,None,rev(c))
        values=json.loads(Path('fixtures/engagement-intake.json').read_text())
        activate(a,c,ASSIGN,values['assignment'],e['policy_decision']);activate(a,c,REGISTER,values['registration'],e['policy_decision'])
        captures=[];registrations=[]
        for suffix in ['first','second']:
            captures.append(engagement.capture(a,c.pk,'A',e['rfp_outcome'].pk,'same-won-rfp',suffix+'-receipt',conversion.pk))
            engagement.assign(a,c.pk,a.pk,'PMO Lead',e['rfp_outcome'].pk,suffix+'-assignment')
            registrations.append(engagement.register(a,c.pk,'SYN-WON-769','PMO Lead',e['rfp_outcome'].pk,e['plan'].pk,suffix+'-registration'))
        self.assertNotEqual(captures[0].pk,captures[1].pk)
        self.assertEqual(captures[0].data,captures[1].data)
        self.assertEqual(engagement.Record.objects.filter(kind='capture').count(),2)
        self.assertEqual(engagement.Identifier.objects.count(),1);self.assertEqual(Case.objects.count(),1)
        self.assertEqual(registrations[1].data['previous_registration'],registrations[0].pk)
        self.assertEqual(engagement.current_registration(c).pk,registrations[1].pk)
        self.assertEqual(r.rfp.RFPDisposition.objects.count(),1)
        self.assertEqual(engagement.Identifier.objects.get().record_id,registrations[0].pk)
        for capture in captures:
            self.assertTrue(Audit.objects.filter(case=c,action='engagement.capture',data__record=capture.pk).exists())
        self.assertEqual(PublicationReceipt.objects.count(),1)


class ReportClause(TestCase):
    def test_c10_same_dated_update_exact_internal_client_pins_and_unknown_date(self):
        from tests.meeting_helpers import meetings_fixture
        from apps.documents.controlled import register_template
        from tests.document_helpers import artifact
        from apps.pmo.reporting import draft_period_report
        from apps.pmo.meetings import create_action
        from apps.pmo.issues import log_issue
        a,c,owner,notes,minutes,_,meeting,_=meetings_fixture()
        update=add_evidence(a,c.pk,'project_update',json.dumps({'as_of':meeting.occurred_at.isoformat(),'milestone_date':None,'comment':'PRIVATE-C09-VENDOR-DIAGNOSIS'}),'synthetic:dated-update')
        issue=log_issue(a,c.pk,'DATED-UPDATE','Project delivery update','Delivery',a.pk,'PRIVATE-C09-VENDOR-DIAGNOSIS',update.pk,'Source explicitly provides no milestone date',rev(c),None)
        item=create_action(a,c.pk,'DATE-CONFIRM','PRIVATE-C09-VENDOR-DIAGNOSIS',a.pk,None,update.pk,'Confirm missing milestone date',rev(c),meeting.meeting_id)
        fields=['executive_summary','scope','status','risks','timeline','dependencies','next_steps']
        internal=register_template(a,c.pk,'Internal update',{'document_type':'status_report','required_fields':['executive_summary','status'],'audience_fields':{'internal':fields+['actions','owners','deadlines','issue_impact']}},owner.pk,rev(c))
        client=register_template(a,c.pk,'Client update',{'document_type':'status_report','required_fields':fields,'audience_fields':{'client':fields}},owner.pk,rev(c))
        artifact(a,c,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[internal.pk,client.pk],'repository':'internal-versioned','retention_days':30},owner)
        content=add_evidence(a,c.pk,'agent_private_report_content',json.dumps({'protocol':'pmo-weekly-client-content/v1','sections':{k:{'text':v,'evidence_ids':[update.pk]} for k,v in {'status':'Source update recorded; completion not established.','risks':'Delivery date remains unconfirmed.','timeline':'Milestone date unknown: no date supplied.','next_steps':'Owner to obtain the missing milestone date.'}.items()}}),'synthetic:explicit-client-projection')
        start=meeting.occurred_at-timedelta(days=1);end=timezone.now()+timedelta(seconds=1)
        inside=draft_period_report(a,c.pk,'internal_tuesday',start,end,internal.pk,'internal',rev(c))
        outside=draft_period_report(a,c.pk,'weekly_client',start,end,client.pk,'client',rev(c),client_safe=True,client_content_id=content.pk)
        for key in ['meetings','actions','issues','milestones','changes']:
            self.assertEqual(inside.manifest[key],outside.manifest[key])
        self.assertIn([issue.issue_id,issue.pk],outside.manifest['issues'])
        self.assertIn([item.pk,item.current_id],outside.manifest['actions'])
        self.assertIn([meeting.meeting_id,meeting.pk],outside.manifest['meetings'])
        self.assertEqual(json.loads(update.body)['milestone_date'],None)
        self.assertIsNone(item.current.due_at)
        self.assertIn('PRIVATE-C09-VENDOR-DIAGNOSIS',json.dumps(inside.version.payload))
        self.assertIn('Milestone date unknown',json.dumps(outside.version.payload))
        self.assertIn('Deadline unknown',json.dumps(inside.version.payload))
        for hidden in ['PRIVATE-C09-VENDOR-DIAGNOSIS','DATE-CONFIRM','DATED-UPDATE',update.body]:
            self.assertNotIn(hidden,json.dumps(outside.version.payload))
        self.assertEqual(outside.manifest['client_content'],{'id':content.pk,'sha256':content.sha256})
        self.assertFalse(Publication.objects.exists())


class KickoffClause(TestCase):
    def test_c14_prescribed_roles_and_source_linked_minutes_actions(self):
        from django.contrib.auth import get_user_model
        from apps.identity.models import Grant
        from tests.test_delivery import DeliveryFixture
        from tests.meeting_helpers import MINUTES_DEFINITION
        from tests.document_helpers import artifact
        from apps.documents.controlled import register_template
        from apps.pmo import delivery
        from apps.pmo.meetings import record_meeting,create_action
        from apps.pmo.reporting import draft_minutes
        f=DeliveryFixture();f.setup_delivery();a,c=f.actor,f.case
        for kind in delivery.PLANNING:
            f.source(kind,{'requires_ui':False,'client_signoff_required':False} if kind=='ui_applicability' else {})
        approval=delivery.decide_planning(a,c.pk,f.d.pk,'approve',f.e['plan'].pk,'PMO Lead planning approval before kickoff',rev(c))
        participants={}
        for role in ['Product','Engineering','QA','Infra','Security','PMO']:
            person=get_user_model().objects.create_user('kickoff-'+role)
            Grant.objects.create(case=c,user=person,action='meeting.participate');Grant.objects.create(case=c,user=person,action='action.own')
            participants[role]=person.pk
        occurred=timezone.now();due=occurred+timedelta(days=2)
        facts={'scope':'Implement the approved integration only','timeline':'Review integration after the explicitly supplied two-day action deadline','roles':participants,'expectations':'Raise dependencies; no unapproved scope change','actions':[{'owner_id':participants['Engineering'],'due_at':due.isoformat(),'description':'Confirm integration dependency'}]}
        notes=add_evidence(a,c.pk,'meeting_notes',json.dumps(facts),'synthetic:actual-kickoff-minutes')
        meeting=record_meeting(a,c.pk,'KICKOFF-769','kickoff',occurred,'Confirm scope, timeline, roles and delivery expectations',json.dumps(facts),list(participants.values()),[{'text':'Use approved integration scope and raise dependencies','evidence_id':notes.pk}],notes.pk,rev(c))
        action=create_action(a,c.pk,'KICKOFF-ACTION','Confirm integration dependency',participants['Engineering'],due,notes.pk,'Explicit recorded owner and deadline',rev(c),meeting.meeting_id)
        record=delivery.record_progress(a,c.pk,f.d.pk,'kickoff',notes.pk,'Source-linked actual kickoff',rev(c),meeting.pk)
        template=register_template(a,c.pk,'Kickoff minutes',MINUTES_DEFINITION,f.e['policy_decision'].pk,rev(c))
        artifact(a,c,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[template.pk],'repository':'internal-versioned','retention_days':30},f.e['policy_decision'])
        minutes=draft_minutes(a,c.pk,meeting.meeting_id,template.pk,'internal',rev(c))
        body=json.dumps(minutes.version.payload)
        for text in [facts['scope'],facts['timeline'],facts['expectations'],'Confirm integration dependency',due.isoformat()]:self.assertIn(text,body)
        for role,pk in participants.items():self.assertIn(role,body);self.assertIn(str(pk),body)
        self.assertEqual(meeting.evidence_id,notes.pk);self.assertEqual(action.current.evidence_id,notes.pk)
        self.assertEqual(minutes.manifest,{'meeting_version':meeting.pk,'actions':[[action.pk,action.current_id]]})
        self.assertLess(approval.pk,record.pk)
        self.assertFalse(Publication.objects.exists())


class RouteAPlanningClause(TestCase):
    def test_c12_signed_route_a_requirements_four_teams_plan_and_exact_finance_receipt(self):
        from django.contrib.auth import get_user_model
        from apps.identity.models import Grant
        from apps.identity.actions import ACTIONS
        from apps.policy.services import register_reference
        from apps.pmo import planning,delivery
        from apps.pmo.meetings import record_meeting
        from apps.pmo.services import complete_milestone
        from apps.finance.models import Handoff
        from apps.workflows.models import Outbox
        from apps.workflows.services import run_once
        from apps.documents.controlled import register_template
        from tests.document_helpers import artifact
        from tests.helpers import activate
        from tests.signature_helpers import packet_for
        from tests import test_rfp as r,planning_helpers as h
        a,c,e,t,_=r.fixture();response=r.response(a,c,e);r.approve(a,c,e,response);submission=r.submit(a,c,e,t,response)
        outcome=r.rfp.outcome(a,c.pk,submission.pk,'won',timezone.now(),'Client',e['rfp_outcome'].pk,'Actual synthetic won outcome',rev(c))
        conversion=r.rfp.dispose(a,c.pk,outcome.pk,None,rev(c))
        origin=engagement.capture(a,c.pk,'A',e['rfp_outcome'].pk,'approved-rfp','route-a-c12',conversion.pk)
        approved_requirements=response.commercial.sources['requirements']
        prd=add_evidence(a,c.pk,'prd',json.dumps({'document':'Product PRD v1','approved_rfp_response':response.pk,'approved_rfp_requirements':approved_requirements,'scope':'Approved bid integration'}),'synthetic:product-prd')
        e=dict(e,sow=add_evidence(a,c.pk,'sow','New project SOW, approved bid integration, not the bid response','synthetic:project-contract'))
        f={'a':a,'c':c,'e':e,'owners':{},'routes':{},'meetings':{}}
        refs=list(c.registeredreference_set.filter(schema_ref='schema:psl/role-assignment/v1').values_list('ref',flat=True))
        for key,role in planning.OWNER_ROLES.items():
            owner=get_user_model().objects.create_user('route-a-'+key)
            Grant.objects.bulk_create([Grant(case=c,user=owner,action=x) for x in ACTIONS])
            for person in [a,owner]:Grant.objects.get_or_create(case=c,user=person,action='approval.source.read:synthetic-planning-'+key)
            f['owners'][key]=owner
            refs.append(register_reference(a,c.pk,'route-a-owner:'+key,'schema:psl/role-assignment/v1',{'role':role,'user_id':owner.pk},e['policy_decision'].pk).ref)
        activate(a,c,'D05.role_principal_assignments',refs,e['policy_decision'])
        project=ch.proposal(a,c,e);ch.approvals(a,c,project)
        sow_template=register_template(a,c.pk,'Route A project SOW',ch.DEFINITION,e['policy_decision'].pk,rev(c))
        artifact(a,c,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[sow_template.pk],'repository':'internal-versioned','retention_days':30},e['policy_decision'])
        receipt=ch.delivered(a,c,project,sow_template)
        signed=commercial.capture_response(a,c.pk,project.pk,receipt.pk,'signed',e['signature'].pk,'Actual matching synthetic contract signature',rev(c))
        packet_for(a,c,e,project);commercial.adopt_signed(a,c.pk,project.pk,signed.pk,rev(c))
        example=json.loads(Path('fixtures/planning-packet.json').read_text())
        payload=example['capture'];rules=example['criteria']
        payload.update(prd_id=prd.pk,scope_id=e['plan'].pk,engineering_estimate_id=e['engineering_estimate'].pk,security_estimate_id=e['security_estimate'].pk)
        for row in payload['stakeholders']:row.update(contact_id=a.pk,evidence_id=prd.pk)
        payload['source_correlations']=[{'key':field,'source_field':field,'source_id':payload[field],'document_version':'explicit-v1','target_prd_id':prd.pk,'target_scope_id':e['plan'].pk,'evidence_id':payload[field],'state':'current','detail':'Explicit source-backed approved Route A PRD target','resolution_id':None} for field in ['scope_id','engineering_estimate_id','security_estimate_id']]
        rules.update(require_named_contacts=['Engineering','QA','Infra','Security'],comparison_reviewer_id=f['owners']['scope'].pk,comparison_reviewer_role='Product Owner')
        f.update(payload=payload,rules=rules)
        f['packet']=planning.capture(a,c.pk,payload)
        for index,purpose in enumerate(planning.PURPOSES):
            meeting=record_meeting(a,c.pk,'ROUTE-A-ALIGN-'+str(index),'alignment',timezone.now()-timedelta(minutes=2-index),purpose,'Source-backed PRD and estimates walkthrough',[a.pk],[],prd.pk,rev(c))
            f['meetings'][purpose]=meeting;planning.align(a,c.pk,f['packet'].pk,purpose,meeting.pk)
        f['pair']=planning.open_requests(a,c.pk,f['packet'].pk);h.setup_departments(f);h.criteria(f);h.observe(f)
        comparison=h.evidence(f,'planning_comparison_evidence','Independent source comparison: scope and estimates match the exact signed SOW')
        planning.compare(f['owners']['scope'],c.pk,f['packet'].pk,'no_difference',comparison.pk)
        readiness=planning.prepare(a,c.pk,f['packet'].pk)
        ready=planning.current_readiness(c,readiness.pk)
        self.assertTrue(ready['comparison_required']);self.assertEqual(len(ready['inputs']['observations']),2)
        dossier=delivery.open_dossier(a,c.pk,f['pair']['candidate_id'],e['plan'].pk,'Exact signed Route A planning packet',rev(c))
        scope=planning.bridge(a,c.pk,readiness.pk,dossier.pk);delivery.verify_source(a,c.pk,scope.pk,rev(c))
        for kind in delivery.PLANNING:
            if kind=='scope_baseline':continue
            source=delivery.capture_source(a,c.pk,dossier.pk,kind,'synthetic-route-a:'+kind,e['plan'].pk,{'requires_ui':False,'client_signoff_required':False} if kind=='ui_applicability' else {},rev(c))
            delivery.verify_source(a,c.pk,source.pk,rev(c))
        approval=delivery.decide_planning(a,c.pk,dossier.pk,'approve',e['plan'].pk,'PMO Lead exact source-backed planning exit',rev(c))
        milestone=complete_milestone(a,c.pk,'Route A planning milestone',e['completion'].pk,rev(c));self.assertTrue(run_once())
        handoff=Handoff.objects.get(milestone=milestone)
        self.assertEqual(handoff.payload,Outbox.objects.get(milestone=milestone).payload)
        self.assertEqual(handoff.payload['evidence_id'],e['completion'].pk)
        self.assertEqual(handoff.payload['evidence_sha256'],e['completion'].sha256)
        self.assertEqual(handoff.payload['milestone_id'],milestone.pk)
        _,p=planning.packet(c)
        self.assertEqual(p['engagement_id'],origin.pk);self.assertEqual(p['payload']['prd_id'],prd.pk)
        self.assertEqual({x['team'] for x in p['payload']['stakeholders']},{'Engineering','QA','Infra','Security'})
        self.assertEqual(json.loads(prd.body)['approved_rfp_requirements'],approved_requirements)
        self.assertEqual(delivery.approved_plan(dossier).pk,approval.pk)
        self.assertEqual(Baseline.objects.get(case=c).signed_id,e['signature'].pk)
        self.assertFalse(run_once());self.assertEqual(Handoff.objects.count(),1)
