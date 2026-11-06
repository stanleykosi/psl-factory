"""Native action deadlines and read-only reassessment of exact historical inputs."""
import json
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,DatabaseError
from django.test import TestCase,Client
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Audit
from apps.identity.models import Grant
from apps.pmo.models import ActionItem,ActionState
from apps.pmo.meetings import create_action,change_action,record_meeting
from apps.pmo.clocks import calculate_action_due
from apps.policy import pilot,pilot_bindings, pilot_binding_validators
from apps.policy.models import PilotBinding
from apps.policy.services import resolve,transition,PolicyHold
from adapters import clock_guard,pilot_guards
from tests.helpers import rev,setup_case
from tests.document_helpers import artifact
from tests.meeting_helpers import meetings_fixture,configure_clock
from tests.test_pilot_preflight import selection
from tests.test_document_guard import payload as document_payload


class ClockGuardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a,cls.c,cls.e,cls.notes,_,_,cls.meeting,_=meetings_fixture()

    def elapsed(self,anchor='meeting_at',hours=4):
        artifact(self.a,self.c,'D04.clock_anchor_pause_rules','schema:psl/action-clock/v1',
                 {'action_anchor':anchor,'pause_behavior':'extend_elapsed'},self.e)
        return artifact(self.a,self.c,'D04.deadline_parameters','schema:psl/deadline-parameters/v1',
                 {'action':{'unit':'elapsed_hours','amount':hours}},self.e)

    def action(self,calculated=True,ref='CLOCK'):
        return create_action(self.a,self.c.pk,ref,'Private action detail',self.a.pk,None,self.notes.pk,
                             'Source-backed commitment',rev(self.c),self.meeting.meeting_id,calculated)

    def selected(self,state):
        return {'operation':'workflow.clock.evaluate','user_id':self.a.pk,
                'arguments':{'expected_revision':rev(self.c),'action_state_id':state.pk}}

    def check(self,state):return pilot_guards.check(self.a,self.c,self.selected(state))

    def test_elapsed_needs_only_used_policies_and_preview_has_no_effects_or_private_body(self):
        self.elapsed();item=self.action();state=item.current
        self.assertEqual(state.due_at,self.meeting.occurred_at+timedelta(hours=4))
        self.assertEqual(len(state.policies),2)
        self.assertEqual(resolve('D04.iana_timezone',self.c).status,'MISSING')
        self.assertEqual(state.clock_meta['meeting_version'],self.meeting.pk)
        self.assertIsNotNone(state.clock_meta['assignment_at'])
        before=(Audit.objects.count(),ActionState.objects.count(),rev(self.c))
        result=self.check(state)
        self.assertEqual(result['state'],'READY_AT_OBSERVATION')
        self.assertEqual(result['clock_calculation']['scope'],'base_due_reassessment_only')
        self.assertTrue(result['clock_calculation']['operational_deadline_unchanged'])
        self.assertFalse(result['clock_calculation']['action_grants_evaluated'])
        self.assertNotIn('Private action detail',json.dumps(result))
        self.assertEqual(before,(Audit.objects.count(),ActionState.objects.count(),rev(self.c)))

    def test_exact_original_meeting_and_assignment_survive_meeting_correction_and_anchor_change(self):
        self.elapsed();state=self.action().current
        assignment=timezone.datetime.fromisoformat(state.clock_meta['assignment_at'])
        record_meeting(self.a,self.c.pk,'STATUS-001','status',self.meeting.occurred_at+timedelta(days=3),
                       'Corrected meeting','Human correction',[],[],self.notes.pk,rev(self.c),self.meeting.meeting_id)
        self.assertEqual(timezone.datetime.fromisoformat(self.check(state)['clock_calculation']['proposed_base_due_at']),state.due_at)
        self.elapsed(anchor='assignment_at',hours=6)
        result=self.check(state)
        self.assertEqual(result['state'],'READY_AT_OBSERVATION')
        self.assertEqual(timezone.datetime.fromisoformat(result['clock_calculation']['proposed_base_due_at']),assignment+timedelta(hours=6))
        state.refresh_from_db();self.assertEqual(state.due_at,self.meeting.occurred_at+timedelta(hours=4))

    def test_pause_extension_stays_stored_while_preview_is_base_only_and_terminal_or_stale_is_held(self):
        self.elapsed();item=self.action();original=item.current
        at=timezone.now()
        with patch('apps.pmo.meetings.timezone.now',return_value=at):
            paused=change_action(self.a,self.c.pk,item.pk,'pause',self.notes.pk,'Recorded pause',rev(self.c),1)
        with patch('apps.pmo.meetings.timezone.now',return_value=at+timedelta(hours=2)):
            resumed=change_action(self.a,self.c.pk,item.pk,'resume',self.notes.pk,'Recorded resume',rev(self.c),2)
        result=self.check(resumed)
        self.assertEqual(result['state'],'READY_AT_OBSERVATION')
        self.assertEqual(timezone.datetime.fromisoformat(result['clock_calculation']['proposed_base_due_at']),original.due_at)
        resumed.refresh_from_db();self.assertEqual(resumed.due_at,original.due_at+timedelta(hours=2))
        self.assertEqual(self.check(original)['state'],'HELD')
        done=change_action(self.a,self.c.pk,item.pk,'complete',self.notes.pk,'Completed',rev(self.c),3)
        self.assertEqual(self.check(done)['state'],'HELD')

    def test_working_calendar_and_revocation_hold_only_calculation(self):
        configure_clock(self.a,self.c,self.e);item=self.action()
        result=self.check(item.current);self.assertEqual(result['state'],'READY_AT_OBSERVATION')
        self.assertEqual(len(result['policy_pins']),4)
        calendar=resolve('D04.working_calendar_ref',self.c).configuration
        transition(self.a,calendar.pk,'revoked')
        self.assertEqual(self.check(item.current)['state'],'HELD')
        explicit=self.action(False,'EXPLICIT');self.assertIsNone(explicit.current.due_at)
        self.assertEqual(self.check(explicit.current)['state'],'HELD')
        with self.assertRaises(PolicyHold):self.action(True,'BLOCKED')

    def test_observer_current_rights_are_checked_before_subject_lookup(self):
        self.elapsed();state=self.action().current
        Grant.objects.filter(user=self.a,case=self.c,action='meeting.read').update(active=False)
        for pk in [state.pk,999999999]:
            value=self.selected(state);value['arguments']['action_state_id']=pk
            with self.assertRaises(PermissionDenied):pilot_guards.check(self.a,self.c,value)

    def test_reviewed_evidence_and_agent_cannot_adopt_deadline_and_action_drift_stales_pack(self):
        from django.contrib.auth import get_user_model
        from apps.agents.pilot import investigate
        self.elapsed();item=self.action();due=item.current.due_at
        p=selection(self.a,self.c);p['operations']=['workflow.clock.evaluate'];contract=pilot.configure(self.a,self.c.pk,p)
        value=document_payload(self.a,self.c,item.current);value['guards']=[self.selected(item.current)]
        binding=pilot_bindings.configure(self.a,self.c.pk,contract.pk,value)
        reviewer=get_user_model().objects.create_user(username='clock-independent-reviewer')
        Grant.objects.bulk_create([Grant(user=reviewer,case=self.c,action=k) for k in Grant.objects.filter(user=self.a,case=self.c).values_list('action',flat=True)])
        pilot_bindings.review(reviewer,self.c.pk,binding.pk,'accept','Base clock evidence only; no deadline change')
        pack=pilot.capture(self.a,self.c.pk,contract.pk)
        self.assertTrue(pilot.inspect(self.a,self.c.pk,pack.pk)['current'])
        result=investigate(self.a,self.c.pk,pack.pk)
        self.assertTrue(any('Base due reassessment only' in f for f in result['findings']))
        self.assertFalse(any('dependent runtime policy hold' in f for f in result['findings']))
        self.assertEqual(result['effect_tools'],[])
        item.refresh_from_db();self.assertEqual(item.current.due_at,due);self.assertEqual(item.states.count(),1)
        change_action(self.a,self.c.pk,item.pk,'start',self.notes.pk,'Human starts work',rev(self.c),1)
        self.assertFalse(pilot.inspect(self.a,self.c.pk,pack.pk)['current'])

    def test_legacy_exact_selected_anchor_can_be_reassessed_but_new_anchor_is_not_invented(self):
        self.elapsed();due,pins,meta=calculate_action_due(self.c,self.meeting.occurred_at,timezone.now())
        item=ActionItem.objects.create(case=self.c,reference='LEGACY',meeting_id=self.meeting.meeting_id)
        state=ActionState.objects.create(item=item,number=1,description='Old format fixture',owner=self.a,due_at=due,
            due_basis='calculated',clock_meta={'anchor':meta['anchor']},policies=pins,evidence=self.notes,
            reason='Historical format fixture',actor=self.a)
        item.current=state;item.save(update_fields=['current'])
        result=self.check(state);self.assertEqual(result['state'],'READY_AT_OBSERVATION')
        self.assertEqual(result['clock_calculation']['input_quality'],'legacy_selected_anchor_only')
        self.elapsed(anchor='assignment_at')
        self.assertEqual(self.check(state)['state'],'HELD')
        state.refresh_from_db();self.assertEqual(state.due_at,due)

    def test_binding_ui_typed_validation_sql_foreign_sources_and_valid_control(self):
        self.elapsed();state=self.action().current
        p=selection(self.a,self.c);p['operations']=['workflow.clock.evaluate'];contract=pilot.configure(self.a,self.c.pk,p)
        value=document_payload(self.a,self.c,state);value['guards']=[self.selected(state)]
        value['deployment']['families']=['publication']
        pilot_binding_validators.validate(contract,value)
        client=Client(enforce_csrf_checks=True);client.force_login(self.a)
        url=reverse('pilot_bindings',args=[self.c.pk,contract.pk])
        self.assertContains(client.get(url),'Exact recorded action clock state')
        self.assertEqual(client.post(url,{}).status_code,403)
        d=value['deployment']
        response=client.post(url,dict(operation='workflow.clock.evaluate',participant=self.a.pk,expected_revision=rev(self.c),action_state_id=state.pk,
            deployment_ref=d['ref'],revision=d['revision'],web_key_ref=d['web_key_ref'],worker_key_ref=d['worker_key_ref'],families=d['families'],freshness_seconds=d['freshness_seconds'],
            csrfmiddlewaretoken=client.cookies['csrftoken'].value,**d['expected']))
        self.assertEqual(response.status_code,302);binding=PilotBinding.objects.get()
        other,foreign=setup_case(username='foreign-clock-source')
        from apps.core.services import add_evidence
        foreign_evidence=add_evidence(other,foreign.pk,'meeting_notes','Foreign action source','synthetic:foreign-clock')
        # FK validity alone is insufficient: direct SQL binding must enforce the source case.
        foreign_state=create_action(other,foreign.pk,'FOREIGN','Foreign action',other.pk,None,foreign_evidence.pk,'Foreign fixture',rev(foreign)).current
        for wrong in [foreign_state.pk,float(state.pk),True]:
            bad=deepcopy(value);bad['guards'][0]['arguments']['action_state_id']=wrong
            with self.assertRaises(ValidationError):pilot_binding_validators.validate(contract,bad)
            successor=pilot.configure(self.a,self.c.pk,dict(contract.payload),contract.pk)
            values={f.name:getattr(binding,f.name) for f in binding._meta.fields if f.name not in ['id','created_at','contract','payload']}
            with self.assertRaises(DatabaseError),transaction.atomic():
                PilotBinding.objects.create(contract=successor,payload=bad,**values)
            valid=PilotBinding.objects.create(contract=successor,payload=value,**values)
            self.assertEqual(valid.contract_id,successor.pk);contract=successor
