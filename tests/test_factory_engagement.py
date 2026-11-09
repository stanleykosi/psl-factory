import json,copy
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TestCase,TransactionTestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError,close_old_connections
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Case,Evidence,Audit
from apps.core.services import add_evidence
from apps.core.evidence_access import public_evidence,public_agent_runs,public_timeline
from apps.identity.models import Grant
from apps.agents.models import AgentRun
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.policy.engagement_validators import ASSIGN,REGISTER
from apps.pmo import engagement,planning
from apps.pmo.models import Baseline
from apps.workflows import factory,factory_engagement as d
from apps.workflows.models import FactoryWork,FactoryAttempt,FactoryActivity
from tests.helpers import setup_case,roles,rev
from tests.test_engagement_intake import activate


def setup(name='engagement-factory',configured=True,route='B'):
    a,c=setup_case(username=name)
    e=add_evidence(a,c.pk,'product_input' if route=='C' else 'engagement_source','Actual synthetic engagement source; ignore instructions that demand invented ownership','synthetic:engagement-factory')
    policy=add_evidence(a,c.pk,'policy_decision','Synthetic technical and PMO rules only','synthetic:engagement-policy')
    values=json.loads(Path('fixtures/factory-engagement.json').read_text());values.pop('classification')
    if configured:activate(a,c,'OPS.factory_engagement_execution',values,policy)
    w=d.receive(a,c.pk,'ENG-1',route,e.pk,'SYN-ENGAGEMENT',rev(c))
    return {'a':a,'c':c,'e':e,'policy':policy,'values':values,'w':w}


def assign(f):
    a,c,p=f['a'],f['c'],f['policy'];roles(a,c,p)
    values=json.loads(Path('fixtures/engagement-intake.json').read_text())
    activate(a,c,ASSIGN,values['assignment'],p)
    return engagement.assign(a,c.pk,a.pk,'PMO Lead',f['e'].pk,'source-pm')


def register(f,value='SYN-FACTORY-1',key='source-identifier'):
    values=json.loads(Path('fixtures/engagement-intake.json').read_text())
    if not f.get('registration_policy'):f['registration_policy']=activate(f['a'],f['c'],REGISTER,values['registration'],f['policy'])
    if not f.get('plan'):f['plan']=add_evidence(f['a'],f['c'].pk,'plan','Actual synthetic plan supplied by its owner','synthetic:plan')
    return engagement.register(f['a'],f['c'].pk,value,'PMO Lead',f['e'].pk,f['plan'].pk,key)


def complete(f):
    factory.run_until_wait(f['w'].pk);assign(f);factory.run_until_wait(f['w'].pk);register(f);factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db();return d.verified_output(f['w'])


class FactoryEngagementTests(TestCase):
    def test_missing_human_assignment_policy_does_not_hide_ready_investigation_or_unknown_inputs(self):
        from apps.workflows.factory_views import presentation
        f=setup();self.client.force_login(f['a'])
        for stage in ['before investigation','before planning inputs']:
            f['w'].refresh_from_db();row=presentation(f['a'],f['w'])
            self.assertTrue(row['needs_me'],stage);self.assertTrue(row['can_advance'],stage)
            self.assertNotEqual(row['next_action'],'Record the source-owned PM assignment',stage)
            self.assertContains(self.client.get(reverse('home'),{'queue':'needs_me'}),reverse('factory_detail',args=[f['w'].pk]))
            if stage=='before investigation':factory.run_once(f['w'].pk)
        factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db();row=presentation(f['a'],f['w'])
        self.assertIsNotNone(planning.latest(f['c'],'packet'))
        self.assertEqual(row['next_action'],'Record the source-owned PM assignment');self.assertFalse(row['needs_me'])
        self.assertFalse(engagement.Record.objects.filter(kind='assignment').exists())

    def test_early_intake_investigates_and_preserves_unknowns_before_policy_prd_plan_or_signature(self):
        f=setup();factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db()
        self.assertEqual(f['w'].status,'waiting',f['w'].finding)
        self.assertIn('PM assignment',f['w'].finding)
        packet,value=planning.packet(f['c'])
        self.assertEqual(value['payload'],d.empty_planning_payload())
        self.assertFalse(Evidence.objects.filter(case=f['c'],kind__in=['plan','prd','sow','signature']).exists())
        self.assertFalse(Baseline.objects.filter(case=f['c']).exists())
        self.assertFalse(engagement.Identifier.objects.exists())
        self.assertTrue(FactoryAttempt.objects.filter(activity__work=f['w'],activity__kind='ACT04',phase='observed',result__has_key='investigation').exists())
        used=f['w'].budget_used;factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db();self.assertEqual(f['w'].budget_used,used)
        self.assertEqual(Case.objects.count(),1);self.assertEqual(FactoryWork.objects.count(),1)

    def test_route_b_human_assignment_planning_before_registration_exact_final_handoff(self):
        f=setup();factory.run_until_wait(f['w'].pk);assignment=assign(f);factory.run_until_wait(f['w'].pk)
        f['w'].refresh_from_db();n=d.native(f['w'],f['a'])
        self.assertEqual(n['assignment'],assignment.pk);self.assertIsNotNone(n['planning_work']);self.assertIsNone(n['registration'])
        self.assertFalse(Baseline.objects.exists());self.assertFalse(Evidence.objects.filter(kind='plan').exists())
        registration=register(f);factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db()
        self.assertEqual(f['w'].status,'verified',f['w'].finding)
        result=d.verified_output(f['w']);self.assertEqual(result['registration'],registration.pk)
        self.assertFalse(result['planning_complete']);self.assertFalse(result['signature_required']);self.assertFalse(result['external_master_verified'])
        self.assertEqual(FactoryWork.objects.count(),2);self.assertEqual(Case.objects.count(),1)
        self.assertEqual(Audit.objects.filter(action=d.LINKED).count(),1)
        self.assertEqual(engagement.Identifier.objects.count(),1)

    def test_route_c_preserves_native_product_paper_and_alias_history(self):
        f=setup(route='C');complete(f)
        self.assertEqual(d.capture_current(f['c']).data['route'],'C')
        register(f,'SYN-FACTORY-2','corrected-id');f['w'].refresh_from_db()
        with self.assertRaises(ValidationError):d.verified_output(f['w'])
        spent=f['w'].budget_used;d.reassess(f['a'],f['w'].pk,f['w'].revision,'Current native registration correction')
        factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db();d.verified_output(f['w'])
        self.assertEqual(engagement.Identifier.objects.count(),2);self.assertGreaterEqual(f['w'].budget_used,spent)
        self.assertEqual(FactoryWork.objects.count(),2);self.assertEqual(Audit.objects.filter(action=d.LINKED).count(),1)

    def test_missing_execution_profile_holds_only_agent_execution_not_source_capture(self):
        f=setup(configured=False);factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db()
        self.assertEqual(f['w'].status,'configuration_needed');self.assertEqual(f['w'].budget_used,0)
        self.assertEqual(engagement.Record.objects.filter(kind='capture').count(),1)
        self.assertFalse(planning.latest(f['c'],'packet'))
        activate(f['a'],f['c'],'OPS.factory_engagement_execution',f['values'],f['policy'])
        factory.manage(f['a'],f['w'].pk,f['w'].revision,'resume');factory.run_until_wait(f['w'].pk)
        self.assertIsNotNone(planning.latest(f['c'],'packet'))

    def test_duplicate_keys_fresh_forms_and_changed_payload_preserve_one_identity(self):
        f=setup();count=Evidence.objects.count()
        for key in ['ENG-1','NEW-FORM']:
            same=d.receive(f['a'],f['c'].pk,key,'B',f['e'].pk,'SYN-ENGAGEMENT',1)
            self.assertEqual(same.pk,f['w'].pk)
        self.assertEqual(Evidence.objects.count(),count);self.assertEqual(FactoryWork.objects.count(),1)
        with self.assertRaises(ValidationError):d.receive(f['a'],f['c'].pk,'ENG-1','C',f['e'].pk,'SYN-ENGAGEMENT',rev(f['c']))
        with self.assertRaises(ValidationError):d.start(f['a'],f['c'].pk,'ENG-1',d.capture_current(f['c']).pk,'CHANGED',rev(f['c']))

    def test_stale_initial_form_and_wrong_project_source_are_side_effect_free(self):
        a,c=setup_case(username='stale-engagement');e=add_evidence(a,c.pk,'engagement_source','Source','synthetic:source')
        count=Evidence.objects.count()
        with self.assertRaises(ValidationError):d.receive(a,c.pk,'STALE','B',e.pk,'stale',1)
        self.assertFalse(engagement.Record.objects.exists());self.assertEqual(Evidence.objects.count(),count)
        f=setup()
        with self.assertRaises(ValidationError):d.receive(a,c.pk,'FOREIGN','B',f['e'].pk,'foreign',rev(c))
        self.assertFalse(engagement.Record.objects.filter(case=c).exists())

    def test_actual_won_rfp_provenance_and_unknown_outcome_rejection(self):
        from tests import test_rfp as upstream
        a,c,e,t,route=upstream.fixture()
        with self.assertRaises(ValidationError):d.receive(a,c.pk,'RFP-NOT-WON','A',e['rfp_outcome'].pk,'won-rfp',rev(c),999999)
        response=upstream.response(a,c,e);upstream.approve(a,c,e,response);submission=upstream.submit(a,c,e,t,response)
        outcome=upstream.rfp.outcome(a,c.pk,submission.pk,'won',timezone.now(),'Client',e['rfp_outcome'].pk,'Actual synthetic won bid',rev(c))
        disposition=upstream.rfp.dispose(a,c.pk,outcome.pk,None,rev(c))
        w=d.receive(a,c.pk,'RFP-WON','A',e['rfp_outcome'].pk,'won-rfp',rev(c),disposition.pk)
        source=d.pointer(c,w.source_head);self.assertEqual(source.data['rfp_disposition'],disposition.pk)
        self.assertEqual(d.capture_current(c).pk,source.pk);self.assertFalse(Baseline.objects.filter(case=c,signed__isnull=False).exists())

    def test_existing_native_planning_work_reused_without_changing_its_owner(self):
        f=setup();factory.run_until_wait(f['w'].pk);assign(f)
        from apps.workflows.factory_planning import start
        packet,_=planning.packet(f['c']);other=get_user_model().objects.create_user(username='planning-owner')
        Grant.objects.bulk_create([Grant(case=f['c'],user=other,action=x) for x in ['case.read','planning.read','factory.start','factory.read']])
        child=start(other,f['c'].pk,'EXISTING',packet.pk,'Existing native plan',rev(f['c']))
        factory.run_until_wait(f['w'].pk)
        self.assertEqual(d.linked(f['w']).data['planning_work'],child.pk);child.refresh_from_db();self.assertEqual(child.actor_id,other.pk)
        self.assertEqual(FactoryWork.objects.count(),2)

    def test_source_withdrawal_and_assignment_revocation_invalidate_verified_output_and_sql(self):
        f=setup();complete(f)
        for action in ['engagement.capture','engagement.assign','engagement.register','planning.coordinate']:
            Grant.objects.filter(case=f['c'],user=f['a'],action=action).update(active=False)
            with self.assertRaises((ValidationError,PermissionDenied)):d.verified_output(f['w'])
            with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=f['w'].pk).update(status='verified')
            self.assertTrue(d.projection(f['a'],f['w'])['changed'])
            Grant.objects.filter(case=f['c'],user=f['a'],action=action).update(active=True)
        self.assertEqual(engagement.Identifier.objects.count(),1)

    def test_capture_successor_before_planning_can_be_reviewed_without_new_work(self):
        f=setup();factory.run_once(f['w'].pk);f['w'].refresh_from_db();spent=f['w'].budget_used
        e=add_evidence(f['a'],f['c'].pk,'engagement_source','Corrected actual source','synthetic:corrected')
        source=engagement.capture(f['a'],f['c'].pk,'B',e.pk,'corrected','corrected-capture')
        with self.assertRaises(ValidationError):d.native(f['w'],f['a'])
        d.reassess(f['a'],f['w'].pk,f['w'].revision,'Corrected source before any planning packet',source.pk)
        factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db()
        self.assertEqual(d.pointer(f['c'],f['w'].source_head).pk,source.pk)
        self.assertGreater(f['w'].budget_used,spent);self.assertEqual(FactoryWork.objects.count(),1)

    def test_capture_successor_after_handoff_holds_without_duplicate_planning_or_identifier(self):
        f=setup();complete(f)
        e=add_evidence(f['a'],f['c'].pk,'engagement_source','Corrected actual source','synthetic:corrected')
        source=engagement.capture(f['a'],f['c'].pk,'B',e.pk,'corrected','corrected-capture')
        with self.assertRaises(ValidationError):d.verified_output(f['w'])
        with self.assertRaisesMessage(ValidationError,'source-owned planning recovery'):d.reassess(f['a'],f['w'].pk,f['w'].revision,'Changed capture after handoff',source.pk)
        self.assertEqual(FactoryWork.objects.count(),2);self.assertEqual(engagement.Identifier.objects.count(),1)

    def test_planning_source_successor_requires_actual_child_adoption_before_reverification(self):
        f=setup();complete(f)
        packet=planning.latest(f['c'],'packet');new=planning.capture(f['a'],f['c'].pk,d.empty_planning_payload(),packet.pk)
        with self.assertRaises(ValidationError):d.verified_output(f['w'])
        d.reassess(f['a'],f['w'].pk,f['w'].revision,'Reviewed planning packet correction');factory.run_until_wait(f['w'].pk)
        f['w'].refresh_from_db();self.assertEqual(f['w'].status,'waiting')
        values=json.loads(Path('fixtures/factory-planning.json').read_text());values.pop('classification')
        activate(f['a'],f['c'],'OPS.factory_planning_execution',values,f['policy'])
        child=FactoryWork.objects.get(pk=d.linked(f['w']).data['planning_work']);factory.run_once(child.pk)
        child.refresh_from_db();self.assertEqual(child.source_head_id,new.pk)
        factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db();d.verified_output(f['w'])

    def test_premature_or_forged_verified_status_is_rejected_by_database(self):
        f=setup()
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=f['w'].pk).update(status='verified')
        activity=FactoryActivity.objects.create(work=f['w'],kind='ACT13',key='f'*64,plan_revision=1)
        FactoryAttempt.objects.create(activity=activity,number=1,phase='observed',fence=0,observation={},result={'verified':True})
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=f['w'].pk).update(status='verified')

    def test_console_human_actions_are_native_and_get_is_read_only_and_private(self):
        f=setup();factory.run_until_wait(f['w'].pk);assign(f);factory.run_until_wait(f['w'].pk)
        values=json.loads(Path('fixtures/engagement-intake.json').read_text());activate(f['a'],f['c'],REGISTER,values['registration'],f['policy'])
        plan=add_evidence(f['a'],f['c'].pk,'plan','Actual plan evidence','synthetic:console-plan')
        self.client.force_login(f['a']);url=reverse('factory_detail',args=[f['w'].pk]);f['w'].refresh_from_db();before=(Audit.objects.count(),Evidence.objects.count(),FactoryAttempt.objects.count(),rev(f['c']),f['w'].revision)
        response=self.client.get(url);self.assertContains(response,'Register the project during Planning');self.assertContains(response,'Continue the same project')
        self.assertEqual((Audit.objects.count(),Evidence.objects.count(),FactoryAttempt.objects.count(),rev(f['c']),FactoryWork.objects.get(pk=f['w'].pk).revision),before)
        self.assertFalse(public_evidence(Evidence.objects.filter(kind=d.KIND)).exists())
        self.assertFalse(public_agent_runs(AgentRun.objects.filter(case=f['c'],evidence__kind=d.KIND)).exists())
        self.assertFalse(public_timeline(f['c']).filter(action=d.LINKED).exists())
        response=self.client.post(url,{'action':'human','operation':'register','revision':f['w'].revision,'case_revision':rev(f['c']),'key':'UI-REGISTER','role':'PMO Lead','evidence_id':f['e'].pk,'plan_id':plan.pk,'value':'SYN-UI-ID'})
        self.assertEqual(response.status_code,302);self.assertEqual(engagement.latest(f['c'],'registration').actor_id,f['a'].pk)
        self.assertEqual(engagement.Identifier.objects.count(),1)
        with self.assertRaises(ValidationError):d.human(f['a'],f['w'].pk,f['w'].revision,rev(f['c']),'register',{})
        self.assertContains(self.client.get(reverse('factory_intake')),'Log an engagement and connect planning')
        self.assertContains(self.client.get(reverse('factory_create')+'?definition=engagement/v1&case='+str(f['c'].pk)),'Actual engagement source')

    def test_unauthorised_reader_and_native_decision_grants_are_not_inferred(self):
        f=setup();other,_=setup_case(username='other-engagement')
        self.client.force_login(other);self.assertEqual(self.client.get(reverse('factory_detail',args=[f['w'].pk])).status_code,404)
        Grant.objects.filter(case=f['c'],user=f['a'],action='engagement.assign').update(active=False)
        with self.assertRaises(PermissionDenied):d.human(f['a'],f['w'].pk,f['w'].revision,rev(f['c']),'assign',{})
        self.assertFalse(engagement.Record.objects.filter(case=f['c'],kind='assignment').exists())

    def test_cancel_retains_native_sources_and_prevents_handoff(self):
        f=setup();factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db();spent=f['w'].budget_used
        factory.manage(f['a'],f['w'].pk,f['w'].revision,'cancel');factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db()
        self.assertEqual(f['w'].status,'cancelled');self.assertEqual(f['w'].budget_used,spent)
        self.assertFalse(Audit.objects.filter(action=d.LINKED).exists());self.assertIsNotNone(planning.latest(f['c'],'packet'))

    def test_retained_planning_references_are_hidden_after_reader_visibility_is_revoked(self):
        f=setup();result=complete(f)
        reader=get_user_model().objects.create_user(username='engagement-reader')
        for action in ['case.read','factory.read','engagement.read','planning.read']:Grant.objects.create(case=f['c'],user=reader,action=action)
        self.client.force_login(reader);url=reverse('factory_detail',args=[f['w'].pk]);child_url=reverse('factory_detail',args=[result['planning_work']])
        self.assertContains(self.client.get(url),child_url)
        Grant.objects.filter(case=f['c'],user=reader,action='planning.read').update(active=False)
        response=self.client.get(url);self.assertEqual(response.status_code,200)
        self.assertNotContains(response,child_url);self.assertNotContains(response,"&#x27;planning_work&#x27;");self.assertNotContains(response,"&#x27;planning_packet&#x27;")
        self.assertEqual(self.client.get(child_url).status_code,404)
        Grant.objects.filter(case=f['c'],user=reader,action='engagement.read').update(active=False)
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertTrue(FactoryAttempt.objects.filter(activity__work=f['w'],result__planning_work=result['planning_work']).exists())

    def test_existing_human_packet_is_not_overwritten_and_contact_revocation_invalidates_sql(self):
        f=setup();payload=d.empty_planning_payload();payload['stakeholders'][0].update(contact_id=f['a'].pk,evidence_id=f['e'].pk)
        packet=planning.capture(f['a'],f['c'].pk,payload)
        complete(f);self.assertEqual(planning.latest(f['c'],'packet').pk,packet.pk)
        self.assertEqual(Evidence.objects.filter(case=f['c'],kind='planning_packet').count(),1)
        Grant.objects.filter(case=f['c'],user=f['a'],action='planning.participate').update(active=False)
        with self.assertRaises(PermissionDenied):d.verified_output(f['w'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=f['w'].pk).update(status='verified')
        Grant.objects.filter(case=f['c'],user=f['a'],action='planning.participate').update(active=True)
        d.verified_output(f['w'])

    def test_linked_planning_action_successor_invalidates_sql_without_replacing_evidence(self):
        from apps.pmo.meetings import create_action,change_action
        f=setup();e=add_evidence(f['a'],f['c'].pk,'meeting_notes','Actual action evidence','synthetic:action')
        item=create_action(f['a'],f['c'].pk,'GAP-1','Clarify source scope',f['a'].pk,None,e.pk,'Actual unresolved input',rev(f['c']))
        payload=d.empty_planning_payload();payload['questions']=[{'key':'gap','detail':'Scope question','state':'unresolved','action_id':item.pk,'evidence_id':e.pk}]
        packet=planning.capture(f['a'],f['c'].pk,payload);complete(f)
        change_action(f['a'],f['c'].pk,item.pk,'start',e.pk,'Owner started the actual action',rev(f['c']),item.current.number)
        with self.assertRaises(ValidationError):d.verified_output(f['w'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=f['w'].pk).update(status='verified')
        self.assertEqual(planning.latest(f['c'],'packet').pk,packet.pk)

    def test_current_identity_conflicts_and_hidden_other_case_block_python_and_sql(self):
        from apps.pmo import identity_resolution
        from apps.identity.actions import ACTIONS
        from apps.policy.identity_resolution_validators import COMPONENT
        f=setup();complete(f)
        other=Case.objects.create(tenant=f['c'].tenant,title='Actual identity candidate',kind='project',synthetic=True)
        Grant.objects.bulk_create([Grant(case=other,user=f['a'],action=x) for x in ACTIONS])
        e=add_evidence(f['a'],other.pk,'engagement_source','Other actual source','synthetic:identity')
        p=add_evidence(f['a'],other.pk,'policy_decision','Source owner identity rules','synthetic:identity-policy')
        roles(f['a'],other,p);engagement.capture(f['a'],other.pk,'B',e.pk,'other','other-capture')
        values=json.loads(Path('fixtures/engagement-identity-resolution.json').read_text());values.pop('classification')
        activate(f['a'],f['c'],COMPONENT,values,f['policy']);activate(f['a'],other,COMPONENT,values,p)
        for relation in ['unresolved','alias','distinct']:
            identity_resolution.resolve(f['a'],f['c'].pk,other.pk,relation,'PMO Lead',f['e'].pk,e.pk,'Actual human identity finding',relation)
            if relation!='distinct':
                with self.assertRaises(ValidationError):d.verified_output(f['w'])
                with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=f['w'].pk).update(status='verified')
            else:d.verified_output(f['w']);FactoryWork.objects.filter(pk=f['w'].pk).update(status='verified')
        Grant.objects.filter(case=other,user=f['a'],action='case.read').update(active=False)
        with self.assertRaises(ValidationError):d.verified_output(f['w'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=f['w'].pk).update(status='verified')
        self.assertEqual(FactoryWork.objects.count(),2);self.assertEqual(engagement.Identifier.objects.count(),1)

    def test_source_withdrawal_preserves_same_key_actor_and_source_binding(self):
        f=setup();old_count=Evidence.objects.count()
        other=get_user_model().objects.create_user(username='another-intake-actor')
        Grant.objects.bulk_create([Grant(case=f['c'],user=other,action=x) for x in ['case.read','factory.read','factory.start','engagement.read','engagement.capture']])
        with self.assertRaisesMessage(ValidationError,'IDEMPOTENCY_CONFLICT'):d.receive(other,f['c'].pk,'ENG-1','B',f['e'].pk,'SYN-ENGAGEMENT',rev(f['c']))
        e=add_evidence(f['a'],f['c'].pk,'engagement_source','New source','synthetic:successor')
        engagement.capture(f['a'],f['c'].pk,'B',e.pk,'SYN-ENGAGEMENT','capture-successor')
        with self.assertRaises(ValidationError):d.receive(f['a'],f['c'].pk,'ENG-1','B',f['e'].pk,'SYN-ENGAGEMENT',1)
        with self.assertRaises(ValidationError):d.receive(f['a'],f['c'].pk,'ENG-1','B',e.pk,'SYN-ENGAGEMENT',rev(f['c']))
        self.assertEqual(Evidence.objects.count(),old_count+1);self.assertEqual(FactoryWork.objects.count(),1)

    def test_interrupted_atomic_internal_handoff_rolls_back_and_recovers_once(self):
        from unittest.mock import patch
        f=setup();factory.run_until_wait(f['w'].pk);assign(f);real=d.event
        def interrupted(actor,case,action,**data):
            if action==d.LINKED:raise ValidationError('Synthetic interruption before atomic internal handoff commit')
            return real(actor,case,action,**data)
        with patch.object(d,'event',interrupted):factory.run_until_wait(f['w'].pk)
        self.assertEqual(FactoryWork.objects.count(),1);self.assertFalse(Audit.objects.filter(action=d.LINKED).exists())
        f['w'].refresh_from_db();spent=f['w'].budget_used
        factory.manage(f['a'],f['w'].pk,f['w'].revision,'resume');factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db()
        self.assertEqual(FactoryWork.objects.count(),2);self.assertEqual(Audit.objects.filter(action=d.LINKED).count(),1)
        self.assertGreater(f['w'].budget_used,spent)

    def test_agent_cannot_select_a_human_decision_or_skip_investigation(self):
        f=setup()
        class Forbidden:
            def choose(self,context):return {'activity':'ACT11','citations':context['evidence_ids'][:1]}
        factory.run_once(f['w'].pk,provider=Forbidden());f['w'].refresh_from_db()
        self.assertEqual(f['w'].status,'blocked');self.assertFalse(engagement.Record.objects.filter(kind='assignment').exists())
        self.assertFalse(engagement.Identifier.objects.exists());self.assertEqual(FactoryWork.objects.count(),1)

    def test_distinct_source_owner_performs_native_decisions_not_the_worker(self):
        from apps.identity.actions import ACTIONS
        f=setup();factory.run_until_wait(f['w'].pk)
        owner=get_user_model().objects.create_user(username='actual-pmo-owner')
        Grant.objects.bulk_create([Grant(case=f['c'],user=owner,action=x) for x in ACTIONS]);roles(owner,f['c'],f['policy'])
        values=json.loads(Path('fixtures/engagement-intake.json').read_text())
        activate(owner,f['c'],ASSIGN,values['assignment'],f['policy']);activate(owner,f['c'],REGISTER,values['registration'],f['policy'])
        f['w'].refresh_from_db();args={'pm_id':owner.pk,'role':'PMO Lead','evidence_id':f['e'].pk,'key':'OWNER-ASSIGN'}
        with self.assertRaises(PermissionDenied):d.human(f['a'],f['w'].pk,f['w'].revision,rev(f['c']),'assign',args)
        result=d.human(owner,f['w'].pk,f['w'].revision,rev(f['c']),'assign',args);self.assertEqual(result.actor_id,owner.pk)
        factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db()
        plan=add_evidence(owner,f['c'].pk,'plan','Actual owner planning document','synthetic:owner-plan')
        registration=d.human(owner,f['w'].pk,f['w'].revision,rev(f['c']),'register',{'value':'SYN-OWNER-ID','role':'PMO Lead','evidence_id':f['e'].pk,'plan_id':plan.pk,'key':'OWNER-REGISTER'})
        factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db();result=d.verified_output(f['w'])
        self.assertEqual(result['registration'],registration.pk);self.assertEqual(registration.actor_id,owner.pk)
        self.assertFalse(d.human_roles(f['a'],f['c'],'register'));self.assertEqual(f['w'].actor_id,f['a'].pk)

    def test_technical_case_intake_is_the_only_project_master(self):
        from datetime import timedelta
        from apps.identity import intake
        from apps.identity.intake_models import CaseIntake
        a=get_user_model().objects.create_user(username='technical-intake-user')
        admin=get_user_model().objects.create_superuser(username='synthetic-bootstrap',password='synthetic-only-password')
        actions=['case.read','factory.start','factory.read','engagement.read','engagement.capture','evidence.add']
        value={'format':'psl.tenant-access/v1','create_cases':True,'manage_access':False,'kinds':['project'],'allowed_actions':actions,'initial_actions':actions,'classification':'synthetic'}
        intake.provision(admin,a,'synthetic-incumbent-tenant',value,timezone.now()+timedelta(days=1),True,'Explicit synthetic technical authority')
        case=intake.create_case(a,'synthetic-incumbent-tenant','incumbent-reference','Existing incumbent engagement','project')
        e=add_evidence(a,case.pk,'engagement_source','Source for the incumbent workspace','synthetic:incumbent')
        work=d.receive(a,case.pk,'TECH-ENG','B',e.pk,'incumbent-engagement',rev(case))
        same=intake.create_case(a,'synthetic-incumbent-tenant','incumbent-reference','Existing incumbent engagement','project')
        self.assertEqual(work.case_id,same.pk);self.assertEqual(Case.objects.count(),1);self.assertEqual(CaseIntake.objects.count(),1)
        self.assertFalse(engagement.Identifier.objects.exists());self.assertFalse(engagement.Record.objects.filter(kind='assignment').exists())

    def test_typed_source_ids_do_not_accept_boolean_aliases(self):
        f=setup();capture=d.capture_current(f['c'])
        with self.assertRaises(ValidationError):d.start(f['a'],f['c'].pk,'BOOL',True,'bool',rev(f['c']))
        with self.assertRaises(ValidationError):d.receive(f['a'],f['c'].pk,'BOOL','B',True,'bool',rev(f['c']))
        with self.assertRaises(ValidationError):d.receive(f['a'],f['c'].pk,'BOOL','A',f['e'].pk,'bool',rev(f['c']),True)
        self.assertEqual(FactoryWork.objects.count(),1);self.assertEqual(d.capture_current(f['c']).pk,capture.pk)

    def test_reviewed_execution_recovery_preserves_starter_and_revocation_blocks_sql(self):
        from datetime import timedelta
        from apps.identity.actions import ACTIONS
        from apps.workflows import factory_execution
        from apps.policy.factory_recovery_validators import COMPONENT,METHOD
        f=setup();factory.run_until_wait(f['w'].pk);assign(f);factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db()
        worker=get_user_model().objects.create_user(username='reviewed-engagement-worker')
        Grant.objects.bulk_create([Grant(case=f['c'],user=worker,action=x) for x in ACTIONS])
        now=timezone.now();rule={'definition':d.DEFINITION,'method':METHOD,'principal_id':worker.pk,'reviewer_id':f['a'].pk,'review_role':'PMO Lead',
            'independent_of_worker':True,'valid_from':now.isoformat(),'valid_until':(now+timedelta(hours=1)).isoformat()}
        policy=activate(f['a'],f['c'],COMPONENT,{'rules':[rule]},f['policy'])
        spent=f['w'].budget_used;grants=list(Grant.objects.filter(case=f['c']).order_by('pk').values())
        binding=factory_execution.bind(f['a'],f['w'].pk,f['w'].revision,f['policy'].pk,'Actual reviewed synthetic worker replacement')
        f['w'].refresh_from_db();self.assertEqual(f['w'].actor_id,f['a'].pk);self.assertEqual(f['w'].execution_actor_id,worker.pk)
        self.assertEqual(f['w'].budget_used,spent);self.assertEqual(list(Grant.objects.filter(case=f['c']).order_by('pk').values()),grants)
        register(f);Grant.objects.filter(case=f['c'],user=f['a'],action='factory.execute').update(active=False)
        factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db();d.verified_output(f['w'])
        self.assertEqual(f['w'].execution_binding_id,binding.pk);self.assertEqual(f['w'].actor_id,f['a'].pk)
        Grant.objects.filter(case=f['c'],user=f['a'],action='factory.manage').update(active=False)
        with self.assertRaises(PermissionDenied):d.verified_output(f['w'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=f['w'].pk).update(status='verified')
        Grant.objects.filter(case=f['c'],user=f['a'],action='factory.manage').update(active=True)
        d.verified_output(f['w']);transition(f['a'],policy.pk,'revoked')
        with self.assertRaises(ValidationError):d.verified_output(f['w'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=f['w'].pk).update(status='verified')
        self.assertEqual(f['w'].execution_binding_id,binding.pk)


class FactoryEngagementConcurrencyTests(TransactionTestCase):
    def test_duplicate_concurrent_intake_and_handoff_converge(self):
        f=setup();barrier=Barrier(2)
        def duplicate(_):
            close_old_connections()
            try:barrier.wait(timeout=30);return d.receive(f['a'],f['c'].pk,'ENG-1','B',f['e'].pk,'SYN-ENGAGEMENT',1).pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(duplicate,range(2)))
        self.assertEqual(ids,[f['w'].pk,f['w'].pk]);self.assertEqual(FactoryWork.objects.count(),1)
        factory.run_until_wait(f['w'].pk);assign(f);barrier=Barrier(2)
        def progress(_):
            close_old_connections()
            try:barrier.wait(timeout=30);factory.run_until_wait(f['w'].pk)
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(progress,range(2)))
        self.assertEqual(Audit.objects.filter(action=d.LINKED).count(),1);self.assertEqual(FactoryWork.objects.count(),2)


    def test_first_concurrent_intake_creates_one_native_capture_and_work(self):
        a,c=setup_case(username='first-concurrent-engagement');e=add_evidence(a,c.pk,'engagement_source','Actual initial source','synthetic:first-intake');revision=rev(c);barrier=Barrier(2)
        def first(_):
            close_old_connections()
            try:barrier.wait(timeout=30);return d.receive(a,c.pk,'SAME-FIRST','B',e.pk,'FIRST',revision).pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(first,range(2)))
        self.assertEqual(ids[0],ids[1]);self.assertEqual(FactoryWork.objects.count(),1);self.assertEqual(engagement.Record.objects.filter(kind='capture').count(),1)
        self.assertEqual(Evidence.objects.filter(kind=d.KIND).count(),1);self.assertEqual(Case.objects.count(),1)
