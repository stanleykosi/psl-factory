from copy import copy
from unittest.mock import patch
from django.test import TestCase,TransactionTestCase
from django.core.exceptions import PermissionDenied,ValidationError
from django.apps import apps
from django.contrib.auth import get_user_model
from apps.identity.models import Grant
from apps.policy import impact
from apps.policy.models import ImpactAssessment
from apps.workflows import factory
from apps.workflows.models import FactoryWork
from adapters import policy_impact as adapter
from adapters.factory_planning_policy_impact import KEY,COMPONENT,project
from tests.factory_planning_impact802_helpers import fixture,policy

class FactoryPlanningImpactTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.f=fixture()
    def facts(self):
        return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label in ('pmo','core','documents','finance','workflows','agents')}
    def capture(self,new=None):
        f=self.f;new=new or policy(f)
        return impact.capture(f['a'],f['c'].pk,f['policy'].pk,new.pk,[KEY],f['e']['policy_decision'].pk,'Selected planning profile metadata')
    def test_exact_native_binding_and_closed_metadata_without_body_hydration(self):
        f=self.f;before=self.facts();rows=list(adapter.query(f['policy'],KEY,actor=f['a']))
        self.assertEqual([r.pk for r in rows],[f['work'].pk]);self.assertTrue({'request','finding','source_head_id','business_key'}<=rows[0].get_deferred_fields())
        with patch.object(factory,'profile',side_effect=AssertionError('No current execution check')):
            value=project(rows[0])
        self.assertEqual(set(value),{'id','kind','metadata_only','domain_route','definition','status','revision','policy','state','worker_started','authority_rebound','effects_performed'})
        self.assertEqual(value['policy'],f['policy'].pk)
        for key in ('worker_started','authority_rebound','effects_performed'):self.assertFalse(value[key])
        self.assertEqual(before,self.facts())
    def test_null_and_wrong_component_definition_excluded(self):
        other=fixture(username='impact802-null',bind=False)
        self.assertFalse(adapter.query(other['policy'],KEY,actor=other['a']).exists())
        wrong=copy(self.f['policy']);wrong.component='OPS.factory_execution'
        self.assertFalse(adapter.query(wrong,KEY,actor=self.f['a']).exists())
        detached=copy(self.f['work']);detached.definition='pmo-finance/v1'
        with self.assertRaises(PermissionDenied):adapter.authorize_row(self.f['a'],self.f['c'],KEY,detached)
    def test_same_component_case_isolation_with_dual_grants(self):
        f=self.f;other=fixture(username='impact802-other')
        Grant.objects.bulk_create([Grant(case=other['c'],user=f['a'],action=g.action) for g in Grant.objects.filter(case=other['c'],user=other['a'])])
        self.assertEqual(list(adapter.query(other['policy'],KEY,actor=f['a'])),[other['work']])
        self.assertEqual(list(adapter.query(f['policy'],KEY,actor=f['a'])),[f['work']])
        with self.assertRaises(PermissionDenied):adapter.authorize_row(f['a'],other['c'],KEY,f['work'])
    def test_minimal_observer_not_worker_or_source_reader(self):
        f=self.f;r=get_user_model().objects.create_user(username='impact802-reader')
        for action in ('case.read','planning.read','factory.read','policy.read'):Grant.objects.create(user=r,case=f['c'],action=action)
        self.assertEqual(list(adapter.query(f['policy'],KEY,actor=r)),[f['work']]);adapter.authorize_row(r,f['c'],KEY,f['work'])
        self.assertFalse(Grant.objects.filter(user=r,action__in=['factory.execute','factory.manage','planning.coordinate','approval.read']).exists())
    def test_observer_revocation_none_inactive_before_lookup(self):
        f=self.f
        for action in ('case.read','planning.read','factory.read','policy.read'):
            g=Grant.objects.get(user=f['a'],case=f['c'],action=action);g.active=False;g.save()
            with patch('adapters.factory_planning_policy_impact.FactoryWork.objects.filter',side_effect=AssertionError('No lookup')):
                with self.assertRaises(PermissionDenied):adapter.query(f['policy'],KEY,actor=f['a'])
            g.active=True;g.save()
        f['a'].is_active=False;f['a'].save()
        with patch('adapters.factory_planning_policy_impact.FactoryWork.objects.filter',side_effect=AssertionError('No lookup')):
            with self.assertRaises(PermissionDenied):adapter.query(f['policy'],KEY,actor=f['a'])
            with self.assertRaises(PermissionDenied):adapter.query(f['policy'],KEY)
    def test_profile_successor_not_adopted_and_native_adoption_changes_match_only(self):
        f=self.f;new=policy(f);row=self.capture(new);old_observation=row.observation
        self.assertEqual(list(adapter.query(f['policy'],KEY,actor=f['a'])),[f['work']])
        w=factory.adopt_profile(f['a'],f['work'].pk,f['work'].revision,new.pk,'Explicit synthetic successor selection')
        self.assertFalse(adapter.query(f['policy'],KEY,actor=f['a']).exists());self.assertEqual(list(adapter.query(new,KEY,actor=f['a'])),[w])
        row.refresh_from_db();self.assertEqual(row.observation,old_observation);self.assertEqual(w.budget_used,0);self.assertEqual(w.fence,0);self.assertIsNone(w.lease_until)
    def test_inherited_source_permission_before_query_and_saved_read(self):
        from tests.helpers import setup_case
        from apps.core.services import add_evidence
        from apps.policy.operator_drafts import draft_operator_policy
        from apps.policy import scopes
        from apps.policy.services import transition
        from django.utils import timezone
        f=self.f;a,source=setup_case(username='impact802-origin')
        Grant.objects.bulk_create([Grant(case=source,user=f['a'],action=g.action) for g in Grant.objects.filter(case=source,user=a)])
        e=add_evidence(f['a'],source.pk,'policy_decision','Synthetic source profile','synthetic:802')
        draft=draft_operator_policy(f['a'],source.pk,COMPONENT,f['values'],e.pk,timezone.now());transition(f['a'],draft.pk,'validated')
        src=scopes.create(f['a'],draft.pk,'organization',source.tenant,[]);scopes.transition(f['a'],src.pk,'validated');scopes.transition(f['a'],src.pk,'active')
        applied=scopes.apply(f['a'],src.pk,f['c'].pk,f['e']['policy_decision'].pk,[]);transition(f['a'],applied.pk,'validated');transition(f['a'],applied.pk,'active')
        w=factory.adopt_profile(f['a'],f['work'].pk,f['work'].revision,applied.pk,'Explicit source-backed synthetic profile')
        new=policy(f);row=impact.capture(f['a'],f['c'].pk,applied.pk,new.pk,[KEY],f['e']['policy_decision'].pk,'Inherited profile observation')
        self.assertEqual(list(adapter.query(applied,KEY,actor=f['a'])),[w])
        Grant.objects.filter(user=f['a'],case=source,action='policy.read').update(active=False)
        with patch('adapters.factory_planning_policy_impact.FactoryWork.objects.filter',side_effect=AssertionError('No lookup')):
            with self.assertRaises(PermissionDenied):adapter.query(applied,KEY,actor=f['a'])
        from apps.agents.policy_impact import investigate
        for call in (impact.inspect,investigate):
            with self.assertRaises(PermissionDenied):call(f['a'],f['c'].pk,row.pk)
    def test_capture_review_agent_exact_audit_only_and_saved_revocation(self):
        from scripts.impact795_upgrade_lifecycle import unchanged_except_capture_audit
        from apps.agents.policy_impact import investigate
        f=self.f;new=policy(f);before=self.facts();row=self.capture(new)
        unchanged_except_capture_audit(before,self.facts(),actor=f['a'].pk,case=f['c'].pk,assessment=row.pk,previous=f['policy'].pk,successor=new.pk)
        r=get_user_model().objects.create_user(username='impact802-reviewer');Grant.objects.bulk_create([Grant(case=f['c'],user=r,action=g.action) for g in Grant.objects.filter(case=f['c'],user=f['a'])])
        before=self.facts();review=impact.review(r,f['c'].pk,row.pk,'accept',f['e']['policy_decision'].pk,'Independent planning metadata review')
        result=investigate(r,f['c'].pk,row.pk);self.assertEqual(result['effect_tools'],[]);self.assertFalse(result['business_approval'])
        after=self.facts();ids={x['id'] for x in before['core.Audit']};added=[x for x in after['core.Audit'] if x['id'] not in ids]
        self.assertEqual(len(added),1);self.assertEqual((added[0]['actor_id'],added[0]['case_id'],added[0]['action'],added[0]['data']),(r.pk,f['c'].pk,'policy.impact.reviewed',{'assessment':row.pk,'review':review.pk,'verdict':'accept'}))
        after['core.Audit']=[x for x in after['core.Audit'] if x['id'] in ids];self.assertEqual(before,after)
        for action in ('case.read','planning.read','factory.read','policy.read'):
            Grant.objects.filter(user=r,case=f['c'],action=action).update(active=False)
            for call in (impact.inspect,investigate):
                with self.assertRaises(PermissionDenied):call(r,f['c'].pk,row.pk)
            Grant.objects.filter(user=r,case=f['c'],action=action).update(active=True)
    def test_sql_closed_registry_and_budget(self):
        from django.db import transaction,DatabaseError
        f=self.f
        with patch.object(impact,'SNAPSHOT_LIMIT',1):row=self.capture()
        before=ImpactAssessment.objects.count()
        with patch.object(impact,'SNAPSHOT_LIMIT',0),self.assertRaisesMessage(ValidationError,'snapshot exceeds'):self.capture()
        self.assertEqual(before,ImpactAssessment.objects.count())
        base={k:v for k,v in ImpactAssessment.objects.values().get(pk=row.pk).items() if k not in ('id','created_at')}
        for i,keys in enumerate([[],[KEY,KEY],[KEY+'.unknown'],[KEY]*28]):
            with self.assertRaises(DatabaseError),transaction.atomic():ImpactAssessment.objects.create(**dict(base,adapters=keys,operation_key=impact.digest(['bad802',i])))
    def test_paged_investigation_has_only_closed_live_metadata(self):
        from apps.pmo import engagement,planning
        from apps.workflows import factory_planning
        from apps.core.services import add_evidence
        from tests.helpers import rev
        f=self.f
        source=add_evidence(f['a'],f['c'].pk,'engagement_source','Synthetic second direct engagement','synthetic:802')
        engagement.capture(f['a'],f['c'].pk,'B',source.pk,'impact802-second','impact802-second')
        packet=planning.capture(f['a'],f['c'].pk,f['payload'],f['packet'].pk)
        w=factory_planning.start(f['a'],f['c'].pk,'impact802-second',packet.pk,'Second native planning intent',rev(f['c']))
        w=factory.adopt_profile(f['a'],w.pk,w.revision,f['policy'].pk,'Explicit second fresh synthetic profile')
        self.assertNotEqual(w.pk,f['work'].pk)
        before=self.facts()
        first=impact.page(f['a'],f['c'].pk,f['policy'].pk,KEY,limit=1)
        self.assertEqual([r['id'] for r in first['records']],[f['work'].pk]);self.assertTrue(first['next_cursor'])
        second=impact.page(f['a'],f['c'].pk,f['policy'].pk,KEY,cursor=first['next_cursor'],limit=1)
        self.assertEqual([r['id'] for r in second['records']],[w.pk]);self.assertIsNone(second['next_cursor'])
        self.assertEqual(before,self.facts())
        for result in (first,second):
            self.assertNotIn('source_head',str(result));self.assertNotIn('request_hash',str(result));self.assertNotIn('budget_limit',str(result))
        # Cursor is actor/configuration scoped, not a transferable source grant.
        r=get_user_model().objects.create_user(username='impact802-page-reader')
        for action in ('case.read','planning.read','factory.read','policy.read'):Grant.objects.create(user=r,case=f['c'],action=action)
        with self.assertRaisesMessage(ValidationError,'page link'):impact.page(r,f['c'].pk,f['policy'].pk,KEY,cursor=first['next_cursor'],limit=1)
        new=policy(f)
        with self.assertRaisesMessage(ValidationError,'page link'):impact.page(f['a'],f['c'].pk,new.pk,KEY,cursor=first['next_cursor'],limit=1)
        before=ImpactAssessment.objects.count()
        with patch.object(impact,'SNAPSHOT_LIMIT',1),self.assertRaisesMessage(ValidationError,'snapshot exceeds'):self.capture(new)
        self.assertEqual(before,ImpactAssessment.objects.count())

class FactoryPlanningImpactLockTests(TransactionTestCase):
    def setUp(self):
        self.f=fixture(username='impact802-lock')
        self.job=self.f['work'];self.old=self.f['policy'];self.new=policy(self.f)
    def capture(self):
        f=self.f
        return impact.capture(f['a'],f['c'].pk,self.old.pk,self.new.pk,[KEY],f['e']['policy_decision'].pk,'Locked routing observation')
    def test_actual_query_locks_before_hydration(self):
        from django.db import connection
        selects=[]
        def wrapper(execute,sql,params,many,context):
            if 'FROM "workflows_factorywork"' in sql:selects.append(sql)
            return execute(sql,params,many,context)
        with connection.execute_wrapper(wrapper):row=self.capture()
        self.assertTrue(selects, 'Expected a routing-job SELECT')
        self.assertIn('FOR UPDATE',selects[0])
        self.assertIn('NOWAIT',selects[0])
        self.assertEqual(row.observation['domains'][KEY][0]['status'],self.job.status)
    def test_other_connection_lock_holds_without_partial_assessment(self):
        from threading import Event,Thread
        from django.db import transaction,connections,close_old_connections
        from apps.policy.models import ImpactAssessment
        ready=Event();release=Event();errors=[]
        def holder():
            close_old_connections()
            try:
                with transaction.atomic():
                    FactoryWork.objects.select_for_update().get(pk=self.job.pk)
                    ready.set()
                    if not release.wait(10):raise RuntimeError('Bounded lock fixture timeout')
            except BaseException as exc:errors.append(exc);ready.set()
            finally:connections.close_all()
        thread=Thread(target=holder);thread.start()
        try:
            self.assertTrue(ready.wait(5));self.assertFalse(errors)
            before=ImpactAssessment.objects.count()
            from apps.core.models import Audit
            audit_before=list(Audit.objects.order_by('pk').values())
            with self.assertRaisesMessage(ValidationError,'being reconciled'):self.capture()
            self.assertEqual(before,ImpactAssessment.objects.count())
            self.assertEqual(audit_before,list(Audit.objects.order_by('pk').values()))
        finally:release.set();thread.join(12)
        self.assertFalse(thread.is_alive());self.assertFalse(errors)
