from copy import copy
from unittest.mock import patch
from django.test import TestCase
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from apps.identity.models import Grant
from apps.workflows import factory
from adapters import factory_engagement_policy_impact as adapter
from tests.engagement_profile805_helpers import fixture,policy

class EngagementProfileImpactTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.f=fixture()
    def facts(self):
        return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label in ('finance','core','pmo','documents','workflows','agents','policy','identity')}
    def test_exact_closed_deferred_metadata_no_effect(self):
        f=self.f;before=self.facts();rows=list(adapter.query(f['a'],f['policy']))
        self.assertEqual([r.pk for r in rows],[f['work'].pk]);self.assertTrue({'request','finding','business_key','source_head_id'}<=rows[0].get_deferred_fields())
        self.assertEqual(set(adapter.project(rows[0])),{'id','kind','metadata_only','domain_route','definition','status','revision','policy','state','worker_started','authority_rebound','effects_performed'})
        self.assertEqual(before,self.facts())
    def test_null_other_component_definition_and_case(self):
        f=self.f;other=fixture(username='impact805-other',bind=False)
        self.assertFalse(adapter.query(other['a'],other['policy']).exists())
        # In-memory wrong-kind probes exercise Python guards only, not persisted fixtures.
        wrong=copy(f['policy']);wrong.component='OPS.factory_planning_execution';self.assertFalse(adapter.query(f['a'],wrong).exists())
        row=copy(f['work']);row.definition='planning/v1'
        with self.assertRaises(PermissionDenied):adapter.authorize_row(f['a'],f['c'],row)
        Grant.objects.bulk_create([Grant(case=other['c'],user=f['a'],action=g.action) for g in Grant.objects.filter(case=other['c'],user=other['a'])])
        with self.assertRaises(PermissionDenied):adapter.authorize_row(f['a'],other['c'],f['work'])
    def test_minimal_observer_and_revocation_before_lookup(self):
        f=self.f;r=get_user_model().objects.create_user(username='impact805-reader')
        for action in ('case.read','engagement.read','factory.read','policy.read'):Grant.objects.create(user=r,case=f['c'],action=action)
        self.assertEqual(list(adapter.query(r,f['policy'])),[f['work']])
        for action in ('case.read','engagement.read','factory.read','policy.read'):
            Grant.objects.filter(user=r,case=f['c'],action=action).update(active=False)
            with patch('adapters.factory_engagement_policy_impact.FactoryWork.objects.filter',side_effect=AssertionError('No lookup')):
                with self.assertRaises(PermissionDenied):adapter.query(r,f['policy'])
            Grant.objects.filter(user=r,case=f['c'],action=action).update(active=True)
        r.is_active=False;r.save()
        with self.assertRaises(PermissionDenied):adapter.query(r,f['policy'])
        with self.assertRaises(PermissionDenied):adapter.query(None,f['policy'])
    def test_native_successor_changes_exact_match_not_history(self):
        f=self.f;before=adapter.project(list(adapter.query(f['a'],f['policy']))[0]);new=policy(f)
        self.assertFalse(adapter.query(f['a'],new).exists())
        work=factory.adopt_profile(f['a'],f['work'].pk,f['work'].revision,new.pk,'Explicit synthetic successor')
        self.assertFalse(adapter.query(f['a'],f['policy']).exists());self.assertEqual(list(adapter.query(f['a'],new)),[work])
        self.assertEqual(before['policy'],f['policy'].pk)
    def test_native_singleton_not_fabricated_pagination(self):
        f=self.f
        from apps.workflows import factory_engagement
        from tests.helpers import rev
        before=self.facts();current=rev(f['c'])
        same=factory_engagement.start(f['a'],f['c'].pk,'impact805',f['capture'].pk,'Synthetic direct intake',current)
        self.assertEqual(same.pk,f['work'].pk);self.assertEqual(adapter.query(f['a'],f['policy']).count(),1)
        # Existing exact-idempotent native start intentionally precedes expected-revision validation.
        replay=factory_engagement.start(f['a'],f['c'].pk,'impact805',f['capture'].pk,'Synthetic direct intake',max(0,current-1))
        self.assertEqual(replay.pk,same.pk)
        with self.assertRaisesMessage(ValidationError,'IDEMPOTENCY_CONFLICT'):
            factory_engagement.start(f['a'],f['c'].pk,'other805',f['capture'].pk,'Different request',current)
        self.assertEqual(before,self.facts())

    def test_persisted_native_other_component_and_unbound_successor(self):
        import json
        from pathlib import Path
        from django.utils import timezone
        from apps.policy.operator_drafts import draft_operator_policy
        from apps.policy.services import transition
        f=self.f
        values=json.loads((Path(__file__).resolve().parents[1]/'fixtures/factory-planning.json').read_text());values.pop('classification')
        other=draft_operator_policy(f['a'],f['c'].pk,'OPS.factory_planning_execution',values,f['e'].pk,timezone.now())
        transition(f['a'],other.pk,'validated');transition(f['a'],other.pk,'active')
        self.assertNotEqual(other.component,f['policy'].component)
        self.assertFalse(adapter.query(f['a'],other).exists())
        newer=policy(f)
        self.assertFalse(adapter.query(f['a'],newer).exists())
        self.assertEqual(list(adapter.query(f['a'],f['policy'])),[f['work']])

    def capture(self,new=None,previous=None):
        from apps.policy import impact
        f=self.f;new=new or policy(f)
        return impact.capture(f['a'],f['c'].pk,(previous or f['policy']).pk,new.pk,[adapter.KEY],f['e'].pk,'Synthetic engagement profile observation')

    def assert_engineering_delta(self,before,after,model,row,actor,action,data):
        # Preserve ALL original rows including policy/identity, permit only the exact returned engineering row and one Audit append.
        label=model._meta.label;expected=model.objects.values().get(pk=row.pk)
        self.assertEqual(after[label],before[label]+[expected])
        audit_ids={x['id'] for x in before['core.Audit']};added=[x for x in after['core.Audit'] if x['id'] not in audit_ids]
        self.assertEqual(len(added),1)
        self.assertEqual((added[0]['actor_id'],added[0]['case_id'],added[0]['action'],added[0]['data']),(actor.pk,self.f['c'].pk,action,data))
        after=dict(after);after[label]=before[label];after['core.Audit']=[x for x in after['core.Audit'] if x['id'] in audit_ids]
        self.assertEqual(before,after)

    def test_integrated_capture_review_agent_history_and_saved_revocation(self):
        from apps.policy import impact
        from apps.policy.models import ImpactAssessment,ImpactReview
        from apps.agents.policy_impact import investigate
        f=self.f;new=policy(f)
        reviewer=get_user_model().objects.create_user(username='impact805-reviewer')
        Grant.objects.bulk_create([Grant(case=f['c'],user=reviewer,action=g.action) for g in Grant.objects.filter(case=f['c'],user=f['a'])])
        before=self.facts();row=self.capture(new)
        self.assert_engineering_delta(before,self.facts(),ImpactAssessment,row,f['a'],'policy.impact.captured',{'assessment':row.pk,'previous':f['policy'].pk,'successor':new.pk})
        old=dict(ImpactAssessment.objects.values().get(pk=row.pk));before=self.facts()
        review=impact.review(reviewer,f['c'].pk,row.pk,'accept',f['e'].pk,'Independent intake metadata review')
        report=investigate(reviewer,f['c'].pk,row.pk)
        self.assertFalse(report['business_approval']);self.assertEqual(report['effect_tools'],[])
        self.assertIn('Engagement intake profile metadata only',str(report))
        self.assert_engineering_delta(before,self.facts(),ImpactReview,review,reviewer,'policy.impact.reviewed',{'assessment':row.pk,'review':review.pk,'verdict':'accept'})
        factory.adopt_profile(f['a'],f['work'].pk,f['work'].revision,new.pk,'Explicit synthetic successor')
        self.assertEqual(ImpactAssessment.objects.values().get(pk=row.pk),old)
        for action in ('case.read','engagement.read','factory.read','policy.read'):
            Grant.objects.filter(user=reviewer,case=f['c'],action=action).update(active=False)
            for fn in (impact.inspect,investigate):
                with self.assertRaises(PermissionDenied):fn(reviewer,f['c'].pk,row.pk)
            Grant.objects.filter(user=reviewer,case=f['c'],action=action).update(active=True)

    def test_integrated_inherited_source_permission_saved_and_agent(self):
        from tests.helpers import setup_case,roles
        from apps.core.services import add_evidence
        from apps.policy.operator_drafts import draft_operator_policy
        from apps.policy import scopes,impact
        from apps.policy.services import transition
        from apps.agents.policy_impact import investigate
        from django.utils import timezone
        f=self.f;owner,source=setup_case(username='impact805-origin')
        Grant.objects.bulk_create([Grant(case=source,user=f['a'],action=g.action) for g in Grant.objects.filter(case=source,user=owner)])
        e=add_evidence(f['a'],source.pk,'policy_decision','Synthetic inherited intake profile','synthetic:805');roles(f['a'],source,e)
        # This profile deliberately appoints NO executor/resolver/review role.
        self.assertTrue(all(f['values'][key] is None for key in ('executor_id','information_resolver_id','review_role')))
        draft=draft_operator_policy(f['a'],source.pk,adapter.COMPONENT,f['values'],e.pk,timezone.now());transition(f['a'],draft.pk,'validated')
        src=scopes.create(f['a'],draft.pk,'organization',source.tenant,[]);scopes.transition(f['a'],src.pk,'validated');scopes.transition(f['a'],src.pk,'active')
        applied=scopes.apply(f['a'],src.pk,f['c'].pk,f['e'].pk,[]);transition(f['a'],applied.pk,'validated');transition(f['a'],applied.pk,'active')
        work=factory.adopt_profile(f['a'],f['work'].pk,f['work'].revision,applied.pk,'Explicit inherited synthetic profile')
        new=policy(f);row=self.capture(new,applied);self.assertEqual(list(adapter.query(f['a'],applied)),[work])
        Grant.objects.filter(user=f['a'],case=source,action='policy.read').update(active=False)
        with patch('adapters.factory_engagement_policy_impact.FactoryWork.objects.filter',side_effect=AssertionError('No work lookup')):
            with self.assertRaises(PermissionDenied):adapter.query(f['a'],applied)
        for fn in (impact.inspect,investigate):
            with self.assertRaises(PermissionDenied):fn(f['a'],f['c'].pk,row.pk)

    def test_integrated_singleton_cursor_namespaces_and_artificial_zero_budget(self):
        from apps.policy import impact
        from django.core import signing
        f=self.f;new=policy(f);other=fixture(username='impact805-cursor-other')
        Grant.objects.bulk_create([Grant(case=other['c'],user=f['a'],action=g.action) for g in Grant.objects.filter(case=other['c'],user=other['a'])])
        reader=get_user_model().objects.create_user(username='impact805-cursor-reader')
        for action in ('case.read','engagement.read','factory.read','planning.read','policy.read'):Grant.objects.create(user=reader,case=f['c'],action=action)
        before=self.facts();page=impact.page(f['a'],f['c'].pk,f['policy'].pk,adapter.KEY,limit=1)
        self.assertEqual([r['id'] for r in page['records']],[f['work'].pk]);self.assertIsNone(page['next_cursor'])
        # Explicit test-only signed token exercises namespace validation; native singleton emits no continuation.
        token=signing.dumps([f['a'].pk,str(f['c'].pk),f['policy'].pk,adapter.KEY,0],salt=impact.FORMAT)
        for actor,case,config,key,cursor in [(reader,f['c'],f['policy'],adapter.KEY,token),(f['a'],other['c'],other['policy'],adapter.KEY,token),(f['a'],f['c'],new,adapter.KEY,token),(f['a'],f['c'],f['policy'],'workflows.factory_planning_profiles',token),(f['a'],f['c'],f['policy'],adapter.KEY,token+'tampered')]:
            with self.assertRaisesMessage(ValidationError,'page link'):impact.page(actor,case.pk,config.pk,key,cursor=cursor,limit=1)
        with patch.object(impact,'SNAPSHOT_LIMIT',0),self.assertRaisesMessage(ValidationError,'snapshot exceeds'):self.capture(new)
        self.assertEqual(before,self.facts())

    def test_integrated_sql_closed_registry(self):
        from django.db import transaction,DatabaseError
        from apps.policy import impact
        from apps.policy.models import ImpactAssessment
        row=self.capture();before=self.facts()
        base={k:v for k,v in ImpactAssessment.objects.values().get(pk=row.pk).items() if k not in ('id','created_at')}
        for i,keys in enumerate([[],[adapter.KEY,adapter.KEY],[adapter.KEY+'.unknown'],[adapter.KEY]*29]):
            with self.assertRaises(DatabaseError),transaction.atomic():ImpactAssessment.objects.create(**dict(base,adapters=keys,operation_key=impact.digest(['bad805',i])))
        self.assertEqual(before,self.facts())

from django.test import TransactionTestCase
class EngagementProfileLockTests(TransactionTestCase):
    def test_committed_two_connection_lock_and_first_query_nowait(self):
        from threading import Event,Thread
        from django.db import connection,connections,transaction,close_old_connections
        from apps.workflows.models import FactoryWork
        from apps.policy import impact
        f=fixture(username='impact805-lock');new=policy(f);selects=[]
        def capture(successor):return impact.capture(f['a'],f['c'].pk,f['policy'].pk,successor.pk,[adapter.KEY],f['e'].pk,'Bounded engagement lock observation')
        def wrapper(execute,sql,params,many,context):
            if 'FROM "workflows_factorywork"' in sql:selects.append(sql)
            return execute(sql,params,many,context)
        with connection.execute_wrapper(wrapper):capture(new)
        self.assertTrue(selects);self.assertIn('FOR UPDATE',selects[0]);self.assertIn('NOWAIT',selects[0])
        newer=policy(f);before={m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label in ('finance','core','pmo','documents','workflows','agents','policy','identity')}
        with connection.cursor() as c:c.execute('SELECT pg_backend_pid()');main_pid=c.fetchone()[0]
        ready=Event();release=Event();closed=Event();errors=[];pids=[]
        def holder():
            close_old_connections()
            try:
                with transaction.atomic():
                    with connections['default'].cursor() as c:
                        c.execute("SET LOCAL lock_timeout='2s'");c.execute("SET LOCAL statement_timeout='5s'");c.execute('SELECT pg_backend_pid()');pids.append(c.fetchone()[0])
                    FactoryWork.objects.select_for_update().get(pk=f['work'].pk);ready.set()
                    if not release.wait(10):raise RuntimeError('Bounded synthetic lock timeout')
            except BaseException as exc:errors.append(exc);ready.set()
            finally:
                connections.close_all()
                if connections['default'].connection is None:closed.set()
        thread=Thread(target=holder);thread.start()
        try:
            self.assertTrue(ready.wait(5));self.assertFalse(errors);self.assertEqual(len(pids),1);self.assertNotEqual(pids[0],main_pid)
            with self.assertRaisesMessage(ValidationError,'being reconciled'):capture(newer)
            after={m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label in ('finance','core','pmo','documents','workflows','agents','policy','identity')}
            self.assertEqual(before,after)
        finally:release.set();thread.join(12)
        self.assertFalse(thread.is_alive());self.assertTrue(closed.is_set());self.assertFalse(errors)
