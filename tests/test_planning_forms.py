import copy
from django.test import TestCase,Client
from django.urls import reverse
from apps.identity.models import Grant
from apps.core.models import Audit
from apps.pmo import planning
from tests import planning_helpers as h
from tests.helpers import setup_case

class PlanningFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.f=h.fixture()

    def values(self,questions=None):
        f=self.f;p=f['payload'];questions=questions or []
        values={'action':'capture_fields','packet-predecessor':f['packet'].pk,
            'stakeholders-TOTAL_FORMS':'4','stakeholders-INITIAL_FORMS':'4','stakeholders-MIN_NUM_FORMS':'4','stakeholders-MAX_NUM_FORMS':'4',
            'questions-TOTAL_FORMS':str(max(1,len(questions))),'questions-INITIAL_FORMS':'0','questions-MIN_NUM_FORMS':'0','questions-MAX_NUM_FORMS':'100'}
        for key in ['prd_id','scope_id','engineering_estimate_id','security_estimate_id']:values['packet-'+key]=p[key] or ''
        values.update({'correlations-TOTAL_FORMS':str(len(p['source_correlations'])),'correlations-INITIAL_FORMS':str(len(p['source_correlations'])),'correlations-MIN_NUM_FORMS':'0','correlations-MAX_NUM_FORMS':'50'})
        for index,row in enumerate(p['source_correlations']):
            for key,value in row.items():values[f'correlations-{index}-{key}']=value or ''
        for index,row in enumerate(p['stakeholders']):
            for key,value in row.items():values[f'stakeholders-{index}-{key}']=value or ''
        for index,row in enumerate(questions):
            for key,value in row.items():values[f'questions-{index}-{key}']=value or ''
        return values

    def client_for(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.f['a'])
        url=reverse('planning',args=[self.f['c'].pk]);response=client.get(url)
        self.assertContains(response,'Capture planning sources and questions');self.assertContains(response,'Unknown / not supplied')
        return client,url,client.cookies['csrftoken'].value

    def test_actual_source_and_contact_selectors_capture_unknowns_without_owner_defaults(self):
        f=self.f;client,url,csrf=self.client_for();values=self.values()
        values['packet-prd_id']='';values['stakeholders-0-contact_id']=f['owners']['scope'].pk
        values['stakeholders-0-evidence_id']=f['e']['requirements'].pk
        self.assertEqual(client.post(url,values).status_code,403)
        values['csrfmiddlewaretoken']=csrf;self.assertEqual(client.post(url,values).status_code,302)
        item,data=planning.packet(f['c']);self.assertNotEqual(item.pk,f['packet'].pk)
        self.assertIsNone(data['payload']['prd_id']);self.assertEqual(data['payload']['stakeholders'][0]['contact_id'],f['owners']['scope'].pk)
        self.assertTrue(all(x['contact_id'] is None for x in data['payload']['stakeholders'][1:]));self.assertEqual(data['payload']['questions'],[])
        self.assertEqual(planning.report(f['a'],f['c'].pk)['status'],'dependent_readiness_held')

    def test_preview_rows_preserve_inputs_and_write_nothing_then_capture_all_questions(self):
        f=self.f;client,url,csrf=self.client_for()
        question={'key':'Q-UI','detail':'Actual typed UI question','state':'unresolved','action_id':None,'evidence_id':f['e']['requirements'].pk}
        values=self.values([question]);values.update(csrfmiddlewaretoken=csrf,edit_rows='add_question')
        before=(f['c'].evidence.count(),Audit.objects.count())
        response=client.post(url,values);self.assertEqual(response.status_code,200)
        self.assertContains(response,'questions-1-key');self.assertContains(response,'Actual typed UI question')
        self.assertEqual(before,(f['c'].evidence.count(),Audit.objects.count()))
        values.pop('edit_rows');values['questions-TOTAL_FORMS']='2'
        values.update({'questions-1-key':'Q-SECOND','questions-1-detail':'A second independent clarification','questions-1-state':'deferred'})
        self.assertEqual(client.post(url,values).status_code,302)
        self.assertEqual([x['key'] for x in planning.packet(f['c'])[1]['payload']['questions']],['Q-UI','Q-SECOND'])

    def test_foreign_sources_contacts_private_records_and_management_count_tampering_are_held(self):
        from django.contrib.auth import get_user_model
        from apps.core.services import add_evidence
        f=self.f;client,url,csrf=self.client_for();other_actor,other=setup_case(username='foreign-form')
        foreign=add_evidence(other_actor,other.pk,'requirements','Foreign source must not appear','synthetic:foreign')
        private=f['packet'];unassigned=get_user_model().objects.create_user('unassigned-form-contact')
        for changes in [
            {'packet-prd_id':foreign.pk},{'packet-prd_id':private.pk},
            {'stakeholders-0-contact_id':unassigned.pk},{'stakeholders-0-team':'Unapproved team'},
            {'questions-TOTAL_FORMS':'100000'},{'stakeholders-TOTAL_FORMS':'100000'}]:
            values=self.values();values.update(changes,csrfmiddlewaretoken=csrf)
            count=f['c'].evidence.count();response=client.post(url,values)
            self.assertEqual(response.status_code,200);self.assertEqual(f['c'].evidence.count(),count)
            self.assertNotContains(response,'Foreign source must not appear')

    def test_stale_predecessor_current_contact_and_coordination_permission_cannot_be_bypassed(self):
        f=self.f;client,url,csrf=self.client_for();values=self.values();values['csrfmiddlewaretoken']=csrf
        successor=planning.capture(f['a'],f['c'].pk,copy.deepcopy(f['payload']),f['packet'].pk)
        count=f['c'].evidence.count();self.assertContains(client.post(url,values),'Explicit latest packet predecessor required')
        self.assertEqual(f['c'].evidence.count(),count)
        values['packet-predecessor']=successor.pk;values['stakeholders-0-contact_id']=f['owners']['scope'].pk
        Grant.objects.filter(case=f['c'],user=f['owners']['scope'],action='planning.participate').update(active=False)
        self.assertEqual(client.post(url,values).status_code,200);self.assertEqual(f['c'].evidence.count(),count)
        Grant.objects.filter(case=f['c'],user=f['a'],action='planning.coordinate').update(active=False)
        self.assertEqual(client.post(url,values).status_code,403)
        self.assertEqual(f['c'].evidence.count(),count)

    def test_preview_limit_and_question_omission_preserve_old_packet_history(self):
        f=self.f;client,url,csrf=self.client_for()
        values=self.values([{'key':'Q-HISTORY','detail':'Retained in immutable prior packet','state':'unresolved','action_id':None,'evidence_id':None}])
        values['csrfmiddlewaretoken']=csrf;self.assertEqual(client.post(url,values).status_code,302)
        old,data=planning.packet(f['c']);values['packet-predecessor']=old.pk
        values['questions-INITIAL_FORMS']='1';values['questions-0-DELETE']='on'
        self.assertEqual(client.post(url,values).status_code,302)
        self.assertEqual(planning.packet(f['c'])[1]['payload']['questions'],[])
        self.assertIn('Q-HISTORY',f['c'].evidence.get(pk=old.pk).body)
        count=f['c'].evidence.count();values.update(edit_rows='add_question')
        values['questions-TOTAL_FORMS']='100'
        self.assertContains(client.post(url,values),'At most 100 question rows')
        self.assertEqual(f['c'].evidence.count(),count)
