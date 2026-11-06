"""Selected F12/F13 native factory, with explicitly synthetic financial rules."""
import copy,json
from datetime import timedelta
from django.test import TestCase,Client
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.utils import timezone
from apps.identity.models import Grant
from apps.finance import schedules,analysis
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory,factory_schedules as flow
from apps.workflows.models import FactoryWork
from .schedule_helpers import fixture,policy,evidence,row,review,accepted_equity
from .helpers import rev

class FactorySchedulesTests(TestCase):
    def setUp(self):
        self.f=fixture();f=self.f
        value={'definition':flow.DEFINITION,'max_steps':40,'max_tokens':50000,'tokens_per_call':100,'max_children':100,'max_depth':3,'lease_seconds':30,'max_age_seconds':86400,'required_evidence_kinds':[flow.KIND],'information_resolver_id':None,'executor_id':None,'review_role':None,'provider':'synthetic_factory_v1','enabled':True}
        p=draft_operator_policy(f['actor'],f['case'].pk,'OPS.factory_schedules_execution',value,f['e']['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active')
        self.payload=copy.deepcopy(f['values']['detail']);self.payload['rows']=[row(f,'a','-600'),row(f,'b','-400')]
    def start(self,inventory=False,accepted=False):
        f=self.f
        if inventory:
            body=accepted_equity(f) if accepted else f['values']['inventory'];e=evidence(f,'schedule_inventory',json.dumps(body))
            self.args=['inventory',None,e.pk,None]
        else:self.args=['income',f['parent'].pk,f['e']['income_detail'].pk,self.payload]
        self.work=flow.start(f['actor'],f['case'].pk,'SCHEDULES-1',*self.args,'factory-schedules',rev(f['case']));return self.work
    def advance(self):factory.run_until_wait(self.work.pk);self.work.refresh_from_db();return self.work
    def rows(self):
        with connection.cursor() as c:
            c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename");names=[r[0] for r in c.fetchall()];result={}
            for n in names:c.execute('SELECT to_jsonb(t)::text FROM '+connection.ops.quote_name(n)+' t ORDER BY to_jsonb(t)::text');result[n]=c.fetchall()
            return result
    def test_income_native_chain_and_read_only_metadata(self):
        f=self.f;self.start();self.advance();s=flow.schedule(self.work);self.assertIsNotNone(s,self.work.finding);self.assertEqual(s.result['adjusted_total'],'-1000');self.assertNotEqual(self.work.status,'verified')
        review(f,s);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding);self.assertFalse(flow.verify(self.work,f['actor'])['ledger_posted'])
        self.client.force_login(f['reviewer']);Grant.objects.filter(case=f['case'],user=f['reviewer'],action='schedules.report').update(active=False)
        before=self.rows();response=self.client.get('/work/'+str(self.work.pk)+'/');self.assertContains(response,'Private report values require separate report permission');self.assertEqual(before,self.rows());self.assertNotContains(response,'-600');self.assertNotContains(response,'-400');self.assertFalse(flow.projection(f['reviewer'],self.work)['readiness_changed'])
        self.assertEqual(self.client.get('/cases/'+str(f['case'].pk)+'/finance/schedules/'+str(s.pk)+'/report/').status_code,403)
        self.assertEqual(flow.start(f['actor'],f['case'].pk,'SCHEDULES-1',*self.args,'factory-schedules',rev(f['case'])).pk,self.work.pk)
        review(f,s,'revoke')
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_partial_inventory_is_only_selected_dependency_output(self):
        f=self.f;self.start(inventory=True);self.advance();s=flow.schedule(self.work);self.assertIsNotNone(s,self.work.finding);self.assertFalse(s.result['complete_inventory']);review(f,s);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        proof=flow.verify(self.work,f['actor']);self.assertEqual(proof['verification_scope'],'selected_supplied_schedule_dependency_inventory');self.assertFalse(proof['native_workbook_verified']);self.assertFalse(proof['complete_inventory'])
    def test_af13_accepted_inventory_and_source_supersession(self):
        from apps.documents import validation as v
        f=self.f;self.start(inventory=True,accepted=True);self.advance();s=flow.schedule(self.work);self.assertIsNotNone(s,self.work.finding);review(f,s);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        old=f['discovery_source'];v.capture_source(f['actor'],f['case'].pk,old.reference,old.evidence_id,old.metadata,rev(f['case']))
        with self.assertRaises((ValidationError,PermissionDenied)):flow.verify(self.work,f['actor'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_current_review_wait_is_not_rebuild_and_is_in_decision_queue(self):
        f=self.f;self.start();self.advance();s=flow.schedule(self.work)
        with self.assertRaises(ValidationError):flow.correct(f['actor'],self.work.pk,self.work.revision,rev(f['case']),*self.args,'Do not bypass the exact pending review')
        self.client.force_login(f['reviewer'])
        for q in ['needs_me','decisions']:self.assertContains(self.client.get('/?queue='+q),'factory-schedules')
        from apps.policy.schedule_validators import INCOME
        policy(f,INCOME,f['values']['income_rule']);self.assertFalse(flow.projection(f['reviewer'],self.work)['pending_reviews'])
        flow.correct(f['actor'],self.work.pk,self.work.revision,rev(f['case']),*self.args,'Rebuild with the newly configured rule');self.advance();self.assertNotEqual(flow.schedule(self.work).pk,s.pk)
    def test_exact_export_reconciles_and_requires_separate_native_adjustment_review(self):
        f=self.f;self.payload['rows']=[row(f,'supplement','20','additive',lines=[{'account':'sales','amount':'20'}])];self.start();self.advance();s=flow.schedule(self.work);review(f,s);self.advance()
        args=[f['actor'],self.work.pk,self.work.revision,rev(f['case']),s.pk,'additive',f['e']['finance_adjustment'].pk];a=flow.export(*args);args[3]=rev(f['case']);self.assertEqual(flow.export(*args).pk,a.pk)
        with self.assertRaises(ValidationError):analysis.map_source(f['actor'],f['case'].pk,f['source'].pk,[a.adjustment_id],rev(f['case']))
        analysis.review(f['reviewer'],f['case'].pk,'adjustment',a.adjustment_id,'Finance','approve',f['e']['finance_review'].pk,'Separate reporting adjustment approval',rev(f['case']));mapped=analysis.map_source(f['actor'],f['case'].pk,f['source'].pk,[a.adjustment_id],rev(f['case']));self.assertFalse(mapped.result['ledger_posted'])
    def test_cancel_restart_forgery_and_source_scope(self):
        f=self.f;self.start();self.client.force_login(f['actor']);url='/work/'+str(self.work.pk)+'/'
        self.client.post(url,{'action':'advance','revision':self.work.revision,'approved_by':'Finance'});self.assertIsNone(flow.schedule(self.work))
        factory.manage(f['actor'],self.work.pk,self.work.revision,'cancel');self.advance();self.assertEqual(self.work.status,'cancelled');flow.restart(f['actor'],self.work.pk,self.work.revision,rev(f['case']),'Fresh human restart instruction');self.advance();self.assertIsNotNone(flow.schedule(self.work),self.work.finding)
        Grant.objects.filter(case=f['case'],user=f['actor'],action='finance.read').update(active=False);self.assertEqual(self.client.get(url).status_code,404)
    def test_http_intake_review_and_csrf_preserve_native_authority(self):
        from django.urls import reverse
        f=self.f;self.client.force_login(f['actor']);url=reverse('factory_create')+'?definition='+flow.DEFINITION+'&case='+str(f['case'].pk)
        before=self.rows();self.assertEqual(self.client.get(url).status_code,200);self.assertEqual(before,self.rows())
        response=self.client.post(reverse('factory_create'),{'definition':flow.DEFINITION,'key':'SCHEDULES-HTTP','case':f['case'].pk,'reference':'http-schedules','revision':rev(f['case']),'kind':'income','parent_id':f['parent'].pk,'evidence_id':f['e']['income_detail'].pk,'payload':json.dumps(self.payload)})
        self.assertEqual(response.status_code,302);self.work=FactoryWork.objects.get(key='SCHEDULES-HTTP');self.advance();s=flow.schedule(self.work);self.assertIsNotNone(s,self.work.finding)
        url=reverse('factory_detail',args=[self.work.pk]);secure=Client(enforce_csrf_checks=True);secure.force_login(f['reviewer']);self.assertEqual(secure.post(url,{'action':'review'}).status_code,403)
        self.client.force_login(f['reviewer']);response=self.client.post(url,{'action':'review','revision':self.work.revision,'case_revision':rev(f['case']),'target':s.pk,'verdict':'approve','evidence':f['e']['finance_review'].pk,'note':'Exact synthetic human review through primary console'})
        self.assertEqual(response.status_code,302);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
    def test_af13_grant_withdrawal_invalidates_native_and_sql_without_private_report_grant(self):
        f=self.f;self.start(inventory=True,accepted=True);self.advance();s=flow.schedule(self.work);review(f,s);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        Grant.objects.filter(case=f['case'],user=f['reviewer'],action='validation.accept').update(active=False)
        with self.assertRaises((ValidationError,PermissionDenied)):flow.verify(self.work,f['actor'])
        self.assertFalse(flow.projection(f['reviewer'],self.work)['pending_reviews'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_scoped_sql_currentness_tracks_native_grants_context_and_wall_time(self):
        import time
        from tests.test_policy_scopes import fixture as scope_fixture,source_version
        from apps.policy import scopes
        from apps.policy.services import resolve
        from .helpers import envelope
        a,source,target,se,te=scope_fixture()
        src=source_version(a,source,se);cfg=scopes.apply(a,src.pk,target.pk,te.pk,[]);transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        def current():
            with connection.cursor() as c:c.execute('SELECT psl_schedules_policy_current(%s,%s)',[str(target.pk),cfg.pk]);return c.fetchone()[0]
        self.assertTrue(current());self.assertEqual(resolve(cfg.component,target).status,'ACTIVE')
        Grant.objects.filter(case=source,user=a,action='policy.activate').update(active=False);self.assertFalse(current());self.assertNotEqual(resolve(cfg.component,target).status,'ACTIVE')
        Grant.objects.filter(case=source,user=a,action='policy.activate').update(active=True);self.assertTrue(current())
        target.tenant='changed-scope';target.save(update_fields=['tenant']);self.assertFalse(current());self.assertNotEqual(resolve(cfg.component,target).status,'ACTIVE')
        target.tenant=source.tenant;target.save(update_fields=['tenant']);self.assertTrue(current())
        scopes.transition(a,src.pk,'revoked');self.assertFalse(current());self.assertEqual(resolve(cfg.component,target).status,'REVOKED')
        env=envelope(source,'D04.iana_timezone','UTC',se);env['effective_until']=(timezone.now()+timedelta(seconds=4)).isoformat();src=source_version(a,source,se,env=env);cfg=scopes.apply(a,src.pk,target.pk,te.pk,[]);transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        self.assertTrue(current());time.sleep(max(0,(timezone.datetime.fromisoformat(env['effective_until'])-timezone.now()).total_seconds())+0.1)
        self.assertEqual(resolve(cfg.component,target).status,'EXPIRED');self.assertFalse(current())
    def test_inactive_unused_authority_assignee_holds_native_and_sql(self):
        from django.contrib.auth import get_user_model
        from apps.policy.schedule_validators import AUTH
        f=self.f;extra=get_user_model().objects.create_user(username='unused-schedule-authority');rules=copy.deepcopy(f['values']['authority']);rules['assignments'].append({'user_id':extra.pk,'role':'Finance','purposes':['income']});policy(f,AUTH,rules)
        self.start();self.advance();s=flow.schedule(self.work);review(f,s);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        extra.is_active=False;extra.save(update_fields=['is_active'])
        with self.assertRaises((ValidationError,PermissionDenied)):flow.verify(self.work,f['actor'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_selected_inventory_retains_unconfigured_af13_domain_gap(self):
        from apps.documents import validation as v
        from apps.policy.services import resolve
        f=self.f;body=accepted_equity(f);p=f['package'];payload=copy.deepcopy(p.payload)
        component='D09.support_sop_ref';self.assertEqual(resolve(component,f['case']).status,'MISSING');payload['policy_components']=[component]
        package=v.prepare_package(f['actor'],f['case'].pk,p.reference,payload,f['e']['policy_decision'].pk,rev(f['case']));body['schedules'][0]['validation_package_id']=package.pk
        e=evidence(f,'schedule_inventory',json.dumps(body));self.args=['inventory',None,e.pk,None]
        self.work=flow.start(f['actor'],f['case'].pk,'SCHEDULES-1',*self.args,'factory-schedules',rev(f['case']));self.advance();s=flow.schedule(self.work);self.assertIsNotNone(s,self.work.finding);self.assertFalse(s.result['complete_inventory']);review(f,s);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
    def test_nonactive_domain_pins_follow_native_scope_context_and_grants(self):
        import time
        from tests.test_policy_scopes import fixture as scope_fixture,source_version
        from apps.policy import scopes
        from apps.policy.services import resolve,save_draft
        from .helpers import envelope
        a,source,target,se,te=scope_fixture();key='D04.iana_timezone'
        def pin(status):
            with connection.cursor() as cursor:
                cursor.execute('SELECT psl_schedules_policy_pin_current(%s,%s,%s::jsonb)',[str(target.pk),key,json.dumps({'status':status,'id':None})]);return cursor.fetchone()[0]
        self.assertEqual(resolve(key,target).status,'MISSING');self.assertTrue(pin('MISSING'))
        env=envelope(target,key,'UTC',te);env['effective_from']=(timezone.now()+timedelta(hours=1)).isoformat()
        cfg=save_draft(a,target.pk,env);transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        self.assertEqual(resolve(key,target).status,'MISSING');self.assertTrue(pin('MISSING'))
        target.synthetic=False;target.save(update_fields=['synthetic'])
        self.assertEqual(resolve(key,target).status,'INVALID');self.assertFalse(pin('MISSING'))
        target.synthetic=True;target.save(update_fields=['synthetic'])
        env=envelope(source,key,'UTC',se);env['effective_until']=(timezone.now()+timedelta(seconds=3)).isoformat()
        src=source_version(a,source,se,env=env);cfg=scopes.apply(a,src.pk,target.pk,te.pk,[]);transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        time.sleep(max(0,(timezone.datetime.fromisoformat(env['effective_until'])-timezone.now()).total_seconds())+0.1)
        self.assertEqual(resolve(key,target).status,'EXPIRED');self.assertTrue(pin('EXPIRED'))
        Grant.objects.filter(case=source,user=a,action='policy.activate').update(active=False)
        self.assertEqual(resolve(key,target).status,'INVALID');self.assertFalse(pin('EXPIRED'))
        Grant.objects.filter(case=source,user=a,action='policy.activate').update(active=True)
        scopes.transition(a,src.pk,'revoked');self.assertEqual(resolve(key,target).status,'REVOKED');self.assertTrue(pin('REVOKED'))
        Grant.objects.filter(case=target,user=a,action='policy.configure').update(active=False)
        self.assertEqual(resolve(key,target).status,'INVALID');self.assertFalse(pin('REVOKED'))
        Grant.objects.filter(case=target,user=a,action='policy.configure').update(active=True)
        self.assertTrue(pin('REVOKED'))
    def test_bound_scope_value_and_synthetic_context_remain_exact(self):
        from tests.test_policy_scopes import fixture as scope_fixture,source_version
        from apps.policy import scopes
        from apps.policy.services import resolve
        a,source,target,se,te=scope_fixture();key='D04.iana_timezone'
        src=source_version(a,source,se,paths=['/0']);cfg=scopes.apply(a,src.pk,target.pk,te.pk,[{'path':'/0','value':'Africa/Lagos'}]);transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_schedules_binding_current(%s),psl_schedules_policy_current(%s,%s)',[cfg.pk,str(target.pk),cfg.pk]);self.assertEqual(cursor.fetchone(),(True,True))
        target.synthetic=False;target.save(update_fields=['synthetic']);self.assertEqual(resolve(key,target).status,'INVALID')
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_schedules_policy_current(%s,%s)',[str(target.pk),cfg.pk]);self.assertFalse(cursor.fetchone()[0])
        target.synthetic=True;target.save(update_fields=['synthetic'])
        source.kind='support';source.save(update_fields=['kind']);self.assertEqual(resolve(key,target).status,'INVALID')
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_schedules_policy_current(%s,%s)',[str(target.pk),cfg.pk]);self.assertFalse(cursor.fetchone()[0])
        source.kind='project';source.save(update_fields=['kind'])
        newer=source_version(a,source,se);self.assertEqual(resolve(key,target).status,'INVALID')
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_schedules_policy_current(%s,%s)',[str(target.pk),cfg.pk]);self.assertFalse(cursor.fetchone()[0])
    def test_mapping_source_successor_holds_native_and_sql(self):
        f=self.f;self.start();self.advance();s=flow.schedule(self.work);review(f,s);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        old=f['source'];analysis.capture_source(f['actor'],f['case'].pk,old.batch_id,old.entity,old.accounting_basis,old.extracted_at,'complete',old.control_total,old.evidence_id,rev(f['case']))
        with self.assertRaises((ValidationError,PermissionDenied)):flow.verify(self.work,f['actor'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
