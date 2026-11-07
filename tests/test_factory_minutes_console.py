"""P43 typed human console, using real native services and synthetic local fixtures."""
from django import forms
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo.models import Meeting,MeetingVersion,ActionItem
from apps.pmo.meetings import record_meeting,create_action
from apps.workflows import factory_minutes as flow
from .helpers import rev
from . import test_factory_minutes as support

class FactoryMinutesConsoleTests(TestCase):
    setUp=support.FactoryMinutesTests.setUp
    start=support.FactoryMinutesTests.start
    advance=support.FactoryMinutesTests.advance
    fields=support.FactoryMinutesTests.fields
    confirm=support.FactoryMinutesTests.confirm
    rows=support.FactoryMinutesTests.rows

    def page(self):
        self.client.force_login(self.actor)
        return self.client.get('/work/'+str(self.work.pk)+'/')

    def browser_payload(self,response):
        payload={'action':'confirm','revision':self.work.revision,'case_revision':rev(self.case)}
        for form in [response.context['confirm_form'],response.context['decision_forms'].management_form,*response.context['decision_forms'],response.context['commitment_forms'].management_form,*response.context['commitment_forms']]:
            for field in form:
                value=field.value()
                if isinstance(field.field.widget,forms.DateTimeInput):value=field.field.widget.format_value(value)
                if isinstance(field.field.widget,forms.CheckboxInput):
                    if value:payload[field.html_name]='on'
                elif isinstance(field.field.widget,forms.CheckboxSelectMultiple):
                    if value:payload[field.html_name]=value
                else:payload[field.html_name]='' if value is None else value
        return payload

    def new_payload(self,response):
        data=self.browser_payload(response)
        data.update(kind='status',occurred_at='2026-11-06T09:30:00',purpose='Confirm delivery plan',summary='People agreed to confirm the plan and investigate the dependency.',participants=[str(self.actor.pk)],note='I checked the actual speakers and commitments against the selected notes.')
        data.update({'decisions-0-text':'Confirm the current delivery plan.','commitments-0-reference':'HTTP-ACTION','commitments-0-description':'Investigate the dependency before the next review.','commitments-0-owner':str(self.actor.pk),'commitments-0-due_at':'2026-11-09T17:00:00','commitments-0-reason':'Actual human commitment supported by the selected notes.'})
        return data

    def post(self,data):return self.client.post('/work/'+str(self.work.pk)+'/',data)
    def business_rows(self):return {k:v for k,v in self.rows().items() if k!='django_session'}

    def test_normal_typed_confirmation_and_readable_minutes_no_write_gets(self):
        self.start();self.advance();response=self.page();before=self.rows()
        response=self.client.get('/work/'+str(self.work.pk)+'/');self.assertEqual(before,self.rows())
        self.assertNotContains(response,'name="fields"');self.assertContains(response,'People who actually participated')
        self.assertContains(response,'Owner unassigned / not agreed');self.assertContains(response,'Local time in Africa/Lagos')
        self.assertFalse(response.context['confirm_form'].initial.get('purpose'));self.assertEqual(response.context['decision_forms'].initial,[])
        payload=self.new_payload(response);response=self.post(payload);self.assertEqual(response.status_code,302)
        self.work.refresh_from_db();meeting=Meeting.objects.get(reference='FORMAL-1');item=ActionItem.objects.get(reference='HTTP-ACTION')
        self.assertEqual(meeting.current.participant_ids,[self.actor.pk]);self.assertEqual(item.current.owner_id,self.actor.pk)
        self.assertEqual(timezone.localtime(meeting.current.occurred_at).hour,9);self.assertEqual(timezone.localtime(item.current.due_at).hour,17)
        self.assertEqual(meeting.current.decisions[0]['evidence_id'],self.notes.pk)
        self.advance();before=self.rows();response=self.client.get('/work/'+str(self.work.pk)+'/');self.assertEqual(before,self.rows())
        self.assertContains(response,'Confirm delivery plan');self.assertContains(response,'<h3>',count=len(flow.document(self.work).version.payload['sections']))
        self.assertNotContains(response,'&#x27;evidence_ids&#x27;');self.assertNotContains(response,'&#x27;heading&#x27;');self.assertEqual(item.current.status,'open')

    def test_unknown_commitment_fields_are_explicit(self):
        self.start();response=self.page();data=self.new_payload(response);data['commitments-0-owner']='';data['commitments-0-due_at']=''
        self.assertEqual(self.post(data).status_code,302);state=ActionItem.objects.get().current
        self.assertIsNone(state.owner_id);self.assertIsNone(state.due_at)

    def test_blank_optional_rows_record_no_invented_decisions_or_actions(self):
        self.start();response=self.page();data=self.browser_payload(response)
        data.update(kind='status',occurred_at='2026-11-06T09:30:00',purpose='Informational meeting',summary='No decisions or commitments were made.',note='Human confirms there was no agreement to record.')
        response=self.post(data);self.assertEqual(response.status_code,302)
        self.assertEqual(Meeting.objects.get(reference='FORMAL-1').current.decisions,[]);self.assertFalse(ActionItem.objects.exists())

    def test_add_rows_preserves_draft_and_has_no_business_writes(self):
        self.start();response=self.page();data=self.new_payload(response);before=self.business_rows();data['action']='add_decision'
        response=self.post(data);self.assertEqual(response.status_code,200);self.assertEqual(self.business_rows(),before)
        self.assertEqual(response.context['decision_forms'].total_form_count(),2);self.assertEqual(response.context['confirm_form']['purpose'].value(),'Confirm delivery plan')
        data=self.browser_payload(response);data['action']='add_commitment';response=self.post(data)
        self.assertEqual(response.context['commitment_forms'].total_form_count(),2);self.assertEqual(self.business_rows(),before)
        data=self.browser_payload(response);data['decisions-1-text']='Second human decision';data['decisions-0-DELETE']='on'
        self.assertEqual(self.post(data).status_code,302);self.assertEqual(Meeting.objects.get(reference='FORMAL-1').current.decisions[0]['text'],'Second human decision');self.assertEqual(ActionItem.objects.count(),1)

    def test_forged_foreign_and_ungranted_selections_never_write(self):
        self.start();response=self.page();data=self.new_payload(response)
        other=Case.objects.create(tenant='other-console',kind='project',title='Other synthetic project',synthetic=True)
        person=get_user_model().objects.create_user('other-console-owner')
        for action in ['action.own','meeting.participate']:Grant.objects.create(case=other,user=person,action=action)
        for action in ['meeting.record','action.manage','evidence.add']:Grant.objects.create(case=other,user=self.actor,action=action)
        notes=add_evidence(self.actor,other.pk,'meeting_notes','Foreign note','synthetic:foreign')
        foreign_action=create_action(self.actor,other.pk,'FOREIGN','Foreign commitment',person.pk,None,notes.pk,'Actual foreign commitment',rev(other))
        change=add_evidence(self.actor,other.pk,'change_request','Foreign change','synthetic:foreign')
        before=self.business_rows()
        variants=[{'participants':[str(person.pk)]},{'commitments-0-owner':str(person.pk)},{'existing_actions':[str(foreign_action.pk)]},{'decisions-0-change_evidence':str(change.pk)},{'commitments-0-change_evidence':str(change.pk)},{'participants':['not-an-id']},{'decisions-0-evidence_id':str(notes.pk)},{'fields':'{}'},{'source_head_id':notes.pk},{'predecessor_id':self.previous.pk},{'extraction_id':'999999'}]
        for variant in variants:
            with self.subTest(variant=variant):self.assertEqual(self.post(dict(data,**variant)).status_code,200);self.assertEqual(self.business_rows(),before)
        Grant.objects.filter(case=self.case,user=self.actor,action='action.own').update(active=False);before=self.business_rows()
        self.assertEqual(self.post(data).status_code,200);self.assertEqual(self.business_rows(),before)

    def test_malformed_dates_counts_and_stale_commands_do_not_write(self):
        self.start();response=self.page();data=self.new_payload(response);before=self.business_rows()
        variants=[{'occurred_at':'2026-11-06T09:30:00+01:00'},{'occurred_at':'yesterday'},{'commitments-0-due_at':'2026-11-06T17:00:00Z'},{'time_zone':'UTC'},{'decisions-TOTAL_FORMS':'50000'},{'commitments-TOTAL_FORMS':'broken'},{'revision':self.work.revision+1},{'case_revision':rev(self.case)+1},{'decisions-49-text':'Unsubmitted row'}]
        for variant in variants:
            with self.subTest(variant=variant):self.assertEqual(self.post(dict(data,**variant)).status_code,200);self.assertEqual(self.business_rows(),before)
        missing=data.copy();missing.pop('decisions-TOTAL_FORMS');self.assertEqual(self.post(missing).status_code,200);self.assertEqual(self.business_rows(),before)

    def test_unchanged_correction_preserves_exact_instant_and_existing_action_state(self):
        self.start();fields=self.fields();fields['occurred_at']='2026-11-06T00:30:58.123456+02:00';self.confirm(fields=fields);self.advance()
        meeting=Meeting.objects.get(reference='FORMAL-1');original=meeting.current.occurred_at;item=ActionItem.objects.get();state=item.current_id;budget=self.work.budget_used
        selected=dict(self.data,meeting_version_id=meeting.current_id)
        flow.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),selected,'Recheck actual attribution without changing commitments');self.work.refresh_from_db()
        response=self.page();data=self.browser_payload(response);self.assertEqual(data['occurred_at'],'2026-11-05T23:30:58')
        self.assertContains(response,'value="2026-11-05T23:30:58"');self.assertNotContains(response,'2026-11-05T23:30:58+01:00')
        self.assertContains(response,'ACTION-1');self.assertEqual([int(x) for x in data['existing_actions']],[item.pk]);self.assertEqual(data['commitments-0-reference'],'')
        data['note']='Human rechecked source attribution; original commitments remain unchanged.'
        self.assertEqual(self.post(data).status_code,302);meeting.refresh_from_db();item.refresh_from_db();self.work.refresh_from_db()
        self.assertEqual(meeting.current.occurred_at,original);self.assertEqual(item.current_id,state);self.assertEqual(ActionItem.objects.count(),1);self.assertEqual(self.work.budget_used,budget)
        self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)

    def test_selected_predecessor_is_not_replaced_by_newer_native_meeting(self):
        self.data['meeting_version_id']=self.previous.pk
        self.work=flow.start(self.actor,self.case.pk,'HTTP-EXISTING','STATUS-001',self.data,rev(self.case));response=self.page();data=self.browser_payload(response)
        newer=record_meeting(self.actor,self.case.pk,'STATUS-001','status',timezone.now(),'Newer native purpose','Newer native summary',[],[],self.notes.pk,rev(self.case),self.previous.meeting_id)
        data['case_revision']=rev(self.case);data['note']='This request still names the old selected predecessor.';before=self.business_rows()
        self.assertEqual(self.post(data).status_code,200);self.assertEqual(self.business_rows(),before);self.assertEqual(Meeting.objects.get(pk=newer.meeting_id).current_id,newer.pk)
