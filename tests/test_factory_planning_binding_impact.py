from copy import copy
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import PermissionDenied,ValidationError
from django.contrib.auth import get_user_model
from django.apps import apps
from apps.identity.models import Grant
from apps.policy import impact
from apps.policy.models import ImpactAssessment
from adapters import policy_impact as adapter
from adapters.factory_planning_binding_impact import KEY,COMPONENT,project
from tests.factory_planning_binding804_helpers import fixture,policy,bind

class PlanningBindingImpactTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.f=fixture()
    def capture(self,new=None):
        f=self.f;new=new or policy(f)
        return impact.capture(f['a'],f['c'].pk,f['policy'].pk,new.pk,[KEY],f['e']['policy_decision'].pk,'Historical planning binding only')
    def facts(self):
        return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label in ('finance','pmo','core','documents','workflows','agents')}
    def test_closed_exact_projection_deferred_private_fields(self):
        f=self.f;before=self.facts();rows=list(adapter.query(f['policy'],KEY,actor=f['a']))
        self.assertEqual([r.pk for r in rows],[f['binding'].pk]);self.assertTrue({'rule','reason','principal_id','reviewer_id','evidence_id'}<=rows[0].get_deferred_fields())
        self.assertEqual(set(project(rows[0])),{'id','kind','metadata_only','domain_route','sequence','configuration','state','effects_performed'})
        self.assertEqual(before,self.facts())
    def test_wrong_component_definition_and_other_case(self):
        f=self.f;other=fixture(username='impact804-other')
        Grant.objects.bulk_create([Grant(case=other['c'],user=f['a'],action=g.action) for g in Grant.objects.filter(case=other['c'],user=other['a'])])
        self.assertEqual(list(adapter.query(other['policy'],KEY,actor=f['a'])),[other['binding']])
        with self.assertRaises(PermissionDenied):adapter.authorize_row(f['a'],other['c'],KEY,f['binding'])
        wrong=copy(f['policy']);wrong.component='OPS.factory_planning_execution';self.assertFalse(adapter.query(wrong,KEY,actor=f['a']).exists())
        row=copy(f['binding']);row.work=copy(f['work']);row.work.definition='not-planning'
        with self.assertRaises(PermissionDenied):adapter.authorize_row(f['a'],f['c'],KEY,row)
    def test_minimal_observer_and_revocation_before_lookup(self):
        f=self.f;r=get_user_model().objects.create_user(username='impact804-reader')
        for action in ('case.read','planning.read','factory.read','policy.read'):Grant.objects.create(case=f['c'],user=r,action=action)
        self.assertEqual(list(adapter.query(f['policy'],KEY,actor=r)),[f['binding']])
        for action in ('case.read','planning.read','factory.read','policy.read'):
            Grant.objects.filter(case=f['c'],user=r,action=action).update(active=False)
            with patch('adapters.factory_planning_binding_impact.FactoryExecutionBinding.objects.filter',side_effect=AssertionError('No lookup')):
                with self.assertRaises(PermissionDenied):adapter.query(f['policy'],KEY,actor=r)
            Grant.objects.filter(case=f['c'],user=r,action=action).update(active=True)
        r.is_active=False;r.save()
        with self.assertRaises(PermissionDenied):adapter.query(f['policy'],KEY,actor=r)
        with self.assertRaises(PermissionDenied):adapter.query(f['policy'],KEY)
    def test_history_retained_after_new_binding_and_policy(self):
        f=self.f;old=dict(type(f['binding']).objects.values().get(pk=f['binding'].pk));new=policy(f);second=bind(f)
        self.assertEqual(list(adapter.query(f['policy'],KEY,actor=f['a'])),[f['binding']])
        self.assertEqual(list(adapter.query(new,KEY,actor=f['a'])),[second]);self.assertEqual(second.previous_id,f['binding'].pk)
        self.assertEqual(dict(type(f['binding']).objects.values().get(pk=f['binding'].pk)),old)
    def test_capture_review_agent_audit_only_and_saved_revocation(self):
        from scripts.impact795_upgrade_lifecycle import unchanged_except_capture_audit
        from apps.agents.policy_impact import investigate
        f=self.f;new=policy(f);before=self.facts();row=self.capture(new)
        unchanged_except_capture_audit(before,self.facts(),actor=f['a'].pk,case=f['c'].pk,assessment=row.pk,previous=f['policy'].pk,successor=new.pk)
        r=get_user_model().objects.create_user(username='impact804-reviewer');Grant.objects.bulk_create([Grant(case=f['c'],user=r,action=g.action) for g in Grant.objects.filter(case=f['c'],user=f['a'])])
        before=self.facts();review=impact.review(r,f['c'].pk,row.pk,'accept',f['e']['policy_decision'].pk,'Independent historical review')
        result=investigate(r,f['c'].pk,row.pk);self.assertEqual(result['effect_tools'],[]);self.assertFalse(result['business_approval'])
        after=self.facts();ids={x['id'] for x in before['core.Audit']};added=[x for x in after['core.Audit'] if x['id'] not in ids]
        self.assertEqual(len(added),1);self.assertEqual((added[0]['actor_id'],added[0]['case_id'],added[0]['action'],added[0]['data']),(r.pk,f['c'].pk,'policy.impact.reviewed',{'assessment':row.pk,'review':review.pk,'verdict':'accept'}))
        after['core.Audit']=[x for x in after['core.Audit'] if x['id'] in ids];self.assertEqual(before,after)
        Grant.objects.filter(case=f['c'],user=r,action='factory.read').update(active=False)
        for call in (impact.inspect,investigate):
            with self.assertRaises(PermissionDenied):call(r,f['c'].pk,row.pk)
    def test_pagination_budget_and_sql_closed_list(self):
        from django.db import transaction,DatabaseError
        f=self.f;second=bind(f);first=impact.page(f['a'],f['c'].pk,f['policy'].pk,KEY,limit=1)
        self.assertEqual([x['id'] for x in first['records']],[f['binding'].pk])
        last=impact.page(f['a'],f['c'].pk,f['policy'].pk,KEY,cursor=first['next_cursor'],limit=1)
        self.assertEqual([x['id'] for x in last['records']],[second.pk]);self.assertIsNone(last['next_cursor'])
        new=policy(f);before=ImpactAssessment.objects.count();business_before=self.facts()
        policy_before={m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label in ('policy','identity')}
        with patch.object(impact,'SNAPSHOT_LIMIT',1),self.assertRaisesMessage(ValidationError,'snapshot exceeds'):self.capture(new)
        self.assertEqual(before,ImpactAssessment.objects.count());self.assertEqual(business_before,self.facts())
        self.assertEqual(policy_before,{m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label in ('policy','identity')})
        row=self.capture(new)
        base={k:v for k,v in ImpactAssessment.objects.values().get(pk=row.pk).items() if k not in ('id','created_at')}
        for i,keys in enumerate([[],[KEY,KEY],[KEY+'.unknown'],[KEY]*29]):
            with self.assertRaises(DatabaseError),transaction.atomic():ImpactAssessment.objects.create(**dict(base,adapters=keys,operation_key=impact.digest(['bad804',i])))

    def test_inherited_source_permission_before_query_and_saved_read(self):
        from tests.helpers import setup_case,roles
        from apps.core.services import add_evidence
        from apps.policy.operator_drafts import draft_operator_policy
        from apps.policy import scopes
        from apps.policy.services import transition
        from django.utils import timezone
        f=self.f;a,source=setup_case(username='impact804-origin')
        Grant.objects.bulk_create([Grant(case=source,user=f['a'],action=g.action) for g in Grant.objects.filter(case=source,user=a)])
        e=add_evidence(f['a'],source.pk,'policy_decision','Synthetic source profile','synthetic:802')
        roles(f['a'],source,e)
        for action in ('case.read','planning.read','factory.read','factory.execute','policy.read'):
            Grant.objects.create(case=source,user_id=f['rule']['principal_id'],action=action)
        draft=draft_operator_policy(f['a'],source.pk,COMPONENT,{'rules':[f['rule']]},e.pk,timezone.now());transition(f['a'],draft.pk,'validated')
        src=scopes.create(f['a'],draft.pk,'organization',source.tenant,[]);scopes.transition(f['a'],src.pk,'validated');scopes.transition(f['a'],src.pk,'active')
        applied=scopes.apply(f['a'],src.pk,f['c'].pk,f['e']['policy_decision'].pk,[]);transition(f['a'],applied.pk,'validated');transition(f['a'],applied.pk,'active')
        w=bind(f)
        new=policy(f);row=impact.capture(f['a'],f['c'].pk,applied.pk,new.pk,[KEY],f['e']['policy_decision'].pk,'Inherited profile observation')
        self.assertEqual(list(adapter.query(applied,KEY,actor=f['a'])),[w])
        Grant.objects.filter(user=f['a'],case=source,action='policy.read').update(active=False)
        with patch('adapters.factory_planning_binding_impact.FactoryExecutionBinding.objects.filter',side_effect=AssertionError('No lookup')):
            with self.assertRaises(PermissionDenied):adapter.query(applied,KEY,actor=f['a'])
        from apps.agents.policy_impact import investigate
        for call in (impact.inspect,investigate):
            with self.assertRaises(PermissionDenied):call(f['a'],f['c'].pk,row.pk)

    def test_cursor_namespace_tamper_and_other_configuration_exclusion(self):
        f=self.f;bind(f)
        token=impact.page(f['a'],f['c'].pk,f['policy'].pk,KEY,limit=1)['next_cursor']
        self.assertTrue(token)
        reader=get_user_model().objects.create_user(username='impact804-cursor-reader')
        for action in ('case.read','planning.read','factory.read','policy.read'):
            Grant.objects.create(case=f['c'],user=reader,action=action)
        new=policy(f)
        self.assertFalse(adapter.query(new,KEY,actor=f['a']).exists())
        other=fixture(username='impact804-cursor-other')
        Grant.objects.bulk_create([Grant(case=other['c'],user=f['a'],action=g.action) for g in Grant.objects.filter(case=other['c'],user=other['a'])])
        before=self.facts()
        cases=[(reader,f['c'],f['policy'],KEY,token),
            (f['a'],f['c'],new,KEY,token),
            (f['a'],other['c'],other['policy'],KEY,token),
            (f['a'],f['c'],f['policy'],'workflows.factory_planning_profiles',token),
            (f['a'],f['c'],f['policy'],KEY,token+'tampered')]
        for actor,case,config,key,cursor in cases:
            with self.assertRaisesMessage(ValidationError,'page link'):
                impact.page(actor,case.pk,config.pk,key,cursor=cursor,limit=1)
        self.assertEqual(before,self.facts())
