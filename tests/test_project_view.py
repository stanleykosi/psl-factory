import copy,json,time
from pathlib import Path
from django.test import TestCase,Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from apps.identity.models import Grant
from apps.core.models import Audit
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition,active_component
from apps.policy.project_view_validators import COMPONENT
from apps.pmo import project_view as d
from apps.agents.project_view import investigate

class ProjectViewTests(TestCase):
    @classmethod
    def configure(cls,value):
        p=draft_operator_policy(cls.a,cls.c.pk,COMPONENT,value,cls.e['policy_decision'].pk,timezone.now())
        transition(cls.a,p.pk,'validated');transition(cls.a,p.pk,'active');return p

    @classmethod
    def setUpTestData(cls):
        from tests.test_delivery import DeliveryFixture
        from tests.helpers import rev
        from apps.pmo.meetings import create_action
        from apps.pmo.services import complete_milestone
        helper=DeliveryFixture();helper.setup_delivery();helper.plan()
        cls.a,cls.c,cls.e=helper.actor,helper.case,helper.e
        cls.item=create_action(cls.a,cls.c.pk,'VIEW-ACTION','PRIVATE ACTION DESCRIPTION',cls.a.pk,None,cls.e['requirements'].pk,'Recorded source obligation',rev(cls.c))
        complete_milestone(cls.a,cls.c.pk,'Recorded <script>milestone</script>',cls.e['completion'].pk,rev(cls.c))
        cls.b=get_user_model().objects.create_user('metadata-recipient')
        for action in ['project.view','agent.project_view']:Grant.objects.create(case=cls.c,user=cls.b,action=action)
        cls.values=json.loads(Path('fixtures/project-view.json').read_text(encoding='utf-8'))['value']
        cls.values['discloser_id']=cls.a.pk;cls.values['profiles'][0]['recipient_ids']=[cls.b.pk]
        cls.policy=cls.configure(cls.values)

    def test_real_source_projection_without_case_read_and_internal_agent_and_ui(self):
        before=Audit.objects.count();value=d.projection(self.b,self.c.pk,'synthetic_team')
        self.assertEqual(set(value['groups']),set(self.values['profiles'][0]['groups']))
        self.assertEqual(value['groups']['actions']['items'][0]['id'],self.item.pk)
        self.assertIsNone(value['groups']['actions']['items'][0]['due_at'])
        self.assertEqual(value['groups']['identifiers']['coverage'],'unknown_no_recorded_source')
        self.assertTrue(value['groups']['delivery_events']['items']);self.assertTrue(value['groups']['milestones']['items'])
        self.assertNotIn('PRIVATE ACTION DESCRIPTION',json.dumps(value));self.assertNotIn(self.e['costing'].body,json.dumps(value))
        self.assertEqual(investigate(self.b,self.c.pk,'synthetic_team')['actions_with_unknown_deadline'],[self.item.pk])
        self.assertEqual(Audit.objects.count(),before);self.assertEqual(value['effect_tools'],[])
        client=Client();client.force_login(self.b)
        self.assertEqual(client.get(reverse('case',args=[self.c.pk])).status_code,404)
        self.assertEqual(client.get('/cases/'+str(self.c.pk)+'/documents/').status_code,404)
        self.assertEqual(client.get(reverse('project_view_configuration',args=[self.c.pk])).status_code,404)
        self.assertContains(client.get(reverse('project_views')),'synthetic_team')
        result=client.get(reverse('project_audience',args=[self.c.pk,'synthetic_team']))
        self.assertContains(result,'&lt;script&gt;milestone');self.assertNotContains(result,'<script>milestone')
        self.assertEqual(result['Cache-Control'],'no-store')
        self.assertContains(result,'Recorded actions');self.assertContains(result,'Unknown / not recorded')
        self.assertEqual(client.get(reverse('project_audience',args=[self.c.pk,'synthetic_team']),{'inspect':'1'}).json()['effect_tools'],[])

    def test_current_recipient_discloser_source_and_policy_changes(self):
        for principal,action in [(self.b,'project.view'),(self.a,'project.share'),(self.a,'meeting.read')]:
            Grant.objects.filter(case=self.c,user=principal,action=action).update(active=False)
            with self.assertRaises(PermissionDenied):d.projection(self.b,self.c.pk,'synthetic_team')
            self.assertFalse(d.discover(self.b))
            Grant.objects.filter(case=self.c,user=principal,action=action).update(active=True)
        get_user_model().objects.filter(pk=self.a.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):d.projection(self.b,self.c.pk,'synthetic_team')
        get_user_model().objects.filter(pk=self.a.pk).update(is_active=True)
        transition(self.a,self.policy.pk,'revoked')
        with self.assertRaises(ValidationError):d.projection(self.b,self.c.pk,'synthetic_team')
        self.assertFalse(d.discover(self.b))
        client=Client();client.force_login(self.a)
        self.assertEqual(client.get(reverse('case',args=[self.c.pk])).status_code,200)

    def test_audience_successor_and_cached_inactive_recipient_do_not_retain_disclosure(self):
        old=self.policy.pk
        replacement=get_user_model().objects.create_user('new-metadata-recipient')
        Grant.objects.create(case=self.c,user=replacement,action='project.view')
        values=copy.deepcopy(self.values);values['profiles'][0]['recipient_ids']=[replacement.pk]
        self.configure(values)
        with self.assertRaises(PermissionDenied):d.projection(self.b,self.c.pk,'synthetic_team')
        self.assertFalse(d.discover(self.b))
        self.assertTrue(d.projection(replacement,self.c.pk,'synthetic_team')['groups'])
        client=Client();client.force_login(replacement)
        self.assertNotContains(client.get(reverse('project_audience',args=[self.c.pk,'synthetic_team'])),'?inspect=1')
        with self.assertRaises(PermissionDenied):investigate(replacement,self.c.pk,'synthetic_team')
        get_user_model().objects.filter(pk=replacement.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):d.projection(replacement,self.c.pk,'synthetic_team')
        from apps.policy.models import Configuration
        self.assertTrue(Configuration.objects.filter(pk=old).exists())

    def test_profile_selection_never_unions_or_exposes_other_audience(self):
        values=copy.deepcopy(self.values);values['profiles'][0]['groups']=['actions']
        other=copy.deepcopy(values['profiles'][0]);other.update(key='identifiers_only',groups=['identifiers'])
        values['profiles'].append(other);self.configure(values)
        Grant.objects.filter(case=self.c,user=self.a,action='engagement.read').update(active=False)
        self.assertEqual(set(d.projection(self.b,self.c.pk,'synthetic_team')['groups']),{'actions'})
        self.assertEqual([x['audience'] for x in d.discover(self.b)],['synthetic_team'])
        with self.assertRaises(PermissionDenied):d.projection(self.b,self.c.pk,'identifiers_only')
        with self.assertRaises(PermissionDenied):d.projection(self.b,self.c.pk,'unconfigured')
        from tests.helpers import setup_case
        _,other_case=setup_case(username='other-project')
        with self.assertRaises(PermissionDenied):d.projection(self.b,other_case.pk,'synthetic_team')

    def test_missing_stale_and_bounded_source_semantics(self):
        values=copy.deepcopy(self.values);profile=values['profiles'][0]
        profile.update(groups=['identifiers'],missing_behavior='hold');self.configure(values)
        with self.assertRaises(ValidationError):d.projection(self.b,self.c.pk,'synthetic_team')
        profile.update(groups=['delivery_events'],missing_behavior='mark_unknown',max_records=1,max_age_seconds=1,stale_behavior='mark_recorded_facts')
        self.configure(values);time.sleep(1.05)
        view=d.projection(self.b,self.c.pk,'synthetic_team');group=view['groups']['delivery_events']
        self.assertTrue(group['truncated']);self.assertEqual(len(group['items']),1)
        self.assertEqual(group['items'][0]['freshness'],'outside_recorded_age')
        profile['stale_behavior']='hold';self.configure(values)
        with self.assertRaises(ValidationError):d.projection(self.b,self.c.pk,'synthetic_team')

    def test_typed_policy_validation_and_configuration_ui_csrf(self):
        invalid=[]
        for key,value in [('groups',['financial_payload']),('max_records',101),('max_age_seconds',0),('recipient_ids',[999999])]:
            v=copy.deepcopy(self.values);v['profiles'][0][key]=value;invalid.append(v)
        v=copy.deepcopy(self.values);v['profiles']*=2;invalid.append(v)
        v=copy.deepcopy(self.values);v['allow_synthetic']=False;invalid.append(v)
        for values in invalid:
            with self.assertRaises(ValidationError),transaction.atomic():self.configure(values)
        client=Client(enforce_csrf_checks=True);client.force_login(self.a)
        url=reverse('project_view_configuration',args=[self.c.pk]);self.assertContains(client.get(url),'Configuration guide')
        payload={'content':json.dumps(self.values),'evidence':self.e['policy_decision'].pk}
        self.assertEqual(client.post(url,payload).status_code,403)
        payload['csrfmiddlewaretoken']=client.cookies['csrftoken'].value
        self.assertEqual(client.post(url,payload).status_code,302)
        self.assertEqual(active_component(COMPONENT,self.c).pk,self.policy.pk)
        self.assertContains(client.get(reverse('case',args=[self.c.pk])),'Sharing and audiences')

    def test_recorded_identifiers_use_real_registered_source(self):
        from tests.test_engagement_intake import EngagementIntakeTests
        from apps.pmo import engagement
        a,c,e,plan,proof,values=EngagementIntakeTests().ready('view-identity-source')
        engagement.register(a,c.pk,'SYN-VIEW-ID','PMO Lead',e.pk,plan.pk,'view-id')
        Grant.objects.create(case=c,user=self.b,action='project.view')
        config=copy.deepcopy(self.values);config['discloser_id']=a.pk;config['profiles'][0]['groups']=['identifiers']
        p=draft_operator_policy(a,c.pk,COMPONENT,config,proof.pk,timezone.now());transition(a,p.pk,'validated');transition(a,p.pk,'active')
        self.assertEqual(d.projection(self.b,c.pk,'synthetic_team')['groups']['identifiers']['items'][0]['value'],'SYN-VIEW-ID')
