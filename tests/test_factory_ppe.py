"""F07 native connection. All fixture financial policies are explicit synthetic inputs."""
import copy,json
from datetime import timedelta
from django.test import TestCase,Client
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.utils import timezone
from apps.identity.models import Grant
from apps.finance import ppe,analysis
from apps.finance.models import ScheduleWork
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory,factory_ppe as flow
from apps.workflows.models import FactoryWork,FactoryAttempt
from .ppe_helpers import fixture,capture,review,policy
from .helpers import rev

class FactoryPPETests(TestCase):
    def setUp(self):
        self.f=fixture();f=self.f
        value={'definition':flow.DEFINITION,'max_steps':40,'max_tokens':50000,'tokens_per_call':100,'max_children':100,'max_depth':3,'lease_seconds':30,'max_age_seconds':86400,'required_evidence_kinds':['ppe_register'],'information_resolver_id':None,'executor_id':None,'review_role':None,'provider':'synthetic_factory_v1','enabled':True}
        p=draft_operator_policy(f['actor'],f['case'].pk,'OPS.factory_ppe_execution',value,f['e']['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active')
    def rows(self):
        # Snapshot every table, including audit/coordination, not a selected subset.
        with connection.cursor() as cursor:
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            names=[r[0] for r in cursor.fetchall()];result={}
            for name in names:
                cursor.execute('SELECT to_jsonb(t)::text FROM '+connection.ops.quote_name(name)+' t ORDER BY to_jsonb(t)::text')
                result[name]=cursor.fetchall()
            return result
    def start(self):
        f=self.f;self.work=flow.start(f['actor'],f['case'].pk,'PPE-1',f['register'].pk,None,f['parent'].pk,'factory-assets',rev(f['case']));return self.work
    def advance(self):factory.run_until_wait(self.work.pk);self.work.refresh_from_db();return self.work
    def test_native_chain_exact_reviews_note_and_read_only_console(self):
        f=self.f;self.start();self.advance();s=flow.schedule(self.work);self.assertIsNotNone(s,self.work.finding);self.assertEqual(s.result['status'],'ready');self.assertNotEqual(self.work.status,'verified')
        review(f,s);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        proof=flow.verify(self.work,f['actor']);self.assertEqual(proof['ledger'],f['parent'].pk);self.assertFalse(proof['ledger_posted']);self.assertEqual(proof['full_owner_oracle_acceptance'],'unresolved')
        self.client.force_login(f['actor']);before=self.rows()
        response=self.client.get('/work/'+str(self.work.pk)+'/');self.assertContains(response,'Full owner-oracle acceptance remains unresolved');self.assertIn('no-store',response['Cache-Control'])
        self.assertEqual(before,self.rows())
        count=FactoryWork.objects.count();self.assertEqual(self.start().pk,self.work.pk);self.assertEqual(FactoryWork.objects.count(),count)
        review(f,s,verdict='revoke');self.assertTrue(flow.projection(f['actor'],self.work)['readiness_changed'])
        with self.assertRaises((ValidationError,PermissionDenied)):flow.verify(self.work,f['actor'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_unknown_rows_and_source_review_remain_human_with_safe_correction(self):
        f=self.f;review(f,f['register'],'register','revoke');self.start();self.advance();self.assertIsNone(flow.schedule(self.work))
        review(f,f['register'],'register');self.advance();old=flow.schedule(self.work);self.assertIsNotNone(old,self.work.finding);spent=self.work.budget_used
        body=copy.deepcopy(f['ppe']['body']);other=copy.deepcopy(body['assets'][0]);other.update(asset_id='unknown',life=None);body['assets'].append(other);r=capture(f,body);review(f,r,'register')
        self.work.refresh_from_db();flow.correct(f['actor'],self.work.pk,self.work.revision,rev(f['case']),r.pk,None,f['parent'].pk,'Select corrected supplied register')
        self.advance();new=flow.schedule(self.work);self.assertNotEqual(new.pk,old.pk);self.assertEqual(new.result['rows'][0]['charge'],'100.00');self.assertIsNone(new.result['rows'][1]['charge']);self.assertGreaterEqual(self.work.budget_used,spent)
        with self.assertRaises(ValidationError):review(f,new)
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
        self.assertTrue(ScheduleWork.objects.filter(pk=old.pk).exists())
    def test_access_csrf_forgery_cancellation_and_no_automatic_restart(self):
        f=self.f;self.start();self.client.force_login(f['actor']);url='/work/'+str(self.work.pk)+'/'
        response=self.client.post(url,{'action':'advance','revision':self.work.revision,'approved_by':'Finance'});self.assertContains(response,'exact typed PPE command');self.assertIsNone(flow.schedule(self.work))
        client=Client(enforce_csrf_checks=True);client.force_login(f['actor']);self.assertEqual(client.post(url,{'action':'advance','revision':self.work.revision}).status_code,403)
        factory.manage(f['actor'],self.work.pk,self.work.revision,'cancel');self.advance();self.assertEqual(self.work.status,'cancelled');self.assertIsNone(flow.schedule(self.work))
        with self.assertRaises(ValidationError):factory.manage(f['actor'],self.work.pk,self.work.revision,'resume')
        flow.restart(f['actor'],self.work.pk,self.work.revision,rev(f['case']),'Fresh human instruction after settled cancellation');self.work.refresh_from_db();self.assertFalse(self.work.cancel_requested)
        Grant.objects.filter(user=f['actor'],case=f['case'],action='ppe.read').update(active=False)
        self.assertEqual(self.client.get(url).status_code,404)
    def test_note_source_review_withdrawal_invalidates_exact_mapping_and_verified_schedule(self):
        f=self.f;self.start();self.advance();s=flow.schedule(self.work);review(f,s);self.advance();self.assertEqual(self.work.status,'verified')
        before=s.pk;analysis.review(f['actor'],f['case'].pk,'source',f['source'].pk,'Finance','return',f['e']['finance_review'].pk,'Source completeness needs corrected evidence',rev(f['case']))
        with self.assertRaises((ValidationError,PermissionDenied)):flow.verify(self.work,f['actor'])
        self.assertTrue(flow.projection(f['actor'],self.work)['readiness_changed']);self.assertEqual(flow.schedule(self.work).pk,before)
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_policy_change_and_reviewer_grant_withdrawal_hold_without_new_approval(self):
        from apps.policy.ppe_validators import CALC
        f=self.f;self.start();self.advance();s=flow.schedule(self.work);review(f,s);self.advance();self.assertEqual(self.work.status,'verified')
        policy(f,CALC,f['ppe']['calculation'])
        with self.assertRaises(ValidationError):flow.verify(self.work,f['actor'])
        self.work.refresh_from_db();spent=self.work.budget_used
        flow.correct(f['actor'],self.work.pk,self.work.revision,rev(f['case']),f['register'].pk,None,f['parent'].pk,'Rebuild under newly activated native calculation policy')
        self.advance();new=flow.schedule(self.work);self.assertNotEqual(new.pk,s.pk);self.assertEqual(self.work.budget_used>=spent,True);self.assertFalse(new.reviews.exists())
        review(f,new);self.advance();self.assertEqual(self.work.status,'verified')
        Grant.objects.filter(user=f['reviewer'],case=f['case'],action='ppe.review').update(active=False)
        with self.assertRaises((ValidationError,PermissionDenied)):flow.verify(self.work,f['actor'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_private_finance_boundary_and_exact_target_review(self):
        f=self.f;self.start();self.advance();s=flow.schedule(self.work)
        with self.assertRaises(ValidationError):flow.review(f['reviewer'],self.work.pk,self.work.revision,rev(f['case']),f['register'].pk,'schedule','approve',f['e']['finance_review'].pk,'Wrong typed native target')
        self.client.force_login(f['reviewer']);url='/work/'+str(self.work.pk)+'/'
        before=self.rows();self.assertEqual(self.client.get(url).status_code,200);self.assertEqual(before,self.rows())
        Grant.objects.filter(user=f['reviewer'],case=f['case'],action='finance.read').update(active=False)
        self.assertEqual(self.client.get(url).status_code,404)
        response=self.client.get('/');self.assertNotContains(response,'factory-assets')
        self.assertFalse(s.reviews.exists())
    def test_typed_http_intake_and_human_decisions_keep_exact_source(self):
        from django.urls import reverse
        f=self.f;review(f,f['register'],'register','revoke');self.client.force_login(f['actor'])
        payload={'definition':flow.DEFINITION,'key':'PPE-HTTP','case':f['case'].pk,'reference':'http-assets','revision':rev(f['case']),'register_id':f['register'].pk,'prior_id':'','ledger_id':f['parent'].pk}
        response=self.client.post(reverse('factory_create'),payload);self.assertEqual(response.status_code,302)
        self.work=FactoryWork.objects.get(key='PPE-HTTP');self.advance();self.assertIsNone(flow.schedule(self.work))
        self.client.force_login(f['reviewer']);url=reverse('factory_detail',args=[self.work.pk]);response=self.client.post(url,{'action':'review','revision':self.work.revision,'case_revision':rev(f['case']),'target':f['register'].pk,'purpose':'register','verdict':'approve','evidence':f['e']['finance_review'].pk,'note':'Human reviewed exact selected register'})
        self.assertEqual(response.status_code,302);self.advance();s=flow.schedule(self.work);self.assertIsNotNone(s,self.work.finding)
        response=self.client.post(url,{'action':'review','revision':self.work.revision,'case_revision':rev(f['case']),'target':s.pk,'purpose':'schedule','verdict':'approve','evidence':f['e']['finance_review'].pk,'note':'Human reviewed exact calculated output'})
        self.assertEqual(response.status_code,302);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
    def test_reader_without_report_permission_sees_current_verified_metadata(self):
        f=self.f;self.start();self.advance();review(f,flow.schedule(self.work));self.advance();self.assertEqual(self.work.status,'verified')
        Grant.objects.filter(user=f['reviewer'],case=f['case'],action='ppe.report').update(active=False)
        self.client.force_login(f['reviewer']);before=self.rows();response=self.client.get('/?queue=verified')
        self.assertContains(response,'factory-assets');self.assertEqual(before,self.rows());self.assertFalse(flow.projection(f['reviewer'],self.work)['readiness_changed'])
        self.assertEqual(self.client.get('/cases/'+str(f['case'].pk)+'/finance/assets/'+str(flow.schedule(self.work).pk)+'/report/').status_code,403)
    def test_native_human_waits_reach_decision_and_attention_queues(self):
        f=self.f;review(f,f['register'],'register','revoke');self.start();self.advance();self.client.force_login(f['reviewer'])
        for queue in ['needs_me','decisions']:self.assertContains(self.client.get('/?queue='+queue),'factory-assets')
        review(f,f['register'],'register');self.advance()
        for queue in ['needs_me','decisions']:self.assertContains(self.client.get('/?queue='+queue),'factory-assets')
    def test_stopped_superseded_register_recovers_only_with_fresh_instruction_and_selection(self):
        f=self.f;self.start();factory.manage(f['actor'],self.work.pk,self.work.revision,'cancel');self.advance();spent=self.work.budget_used
        r=capture(f);review(f,r,'register')
        flow.restart(f['actor'],self.work.pk,self.work.revision,rev(f['case']),'Fresh instruction to inspect successor source');self.work.refresh_from_db()
        self.advance();self.assertNotEqual(self.work.status,'verified');self.work.refresh_from_db()
        flow.correct(f['actor'],self.work.pk,self.work.revision,rev(f['case']),r.pk,None,f['parent'].pk,'Select exact current supplied register')
        self.advance();self.assertEqual(flow.schedule(self.work).payload['register_id'],r.pk);self.assertGreaterEqual(self.work.budget_used,spent)
    def test_current_native_output_can_be_reaffirmed_after_intake_authority_withdrawal(self):
        f=self.f;self.start();self.advance();review(f,flow.schedule(self.work));self.advance();old=flow.schedule(self.work);head=self.work.source_head_id;spent=self.work.budget_used
        Grant.objects.filter(user=f['actor'],case=f['case'],action='factory.start').update(active=False)
        with self.assertRaises(PermissionDenied):flow.source(self.work,f['reviewer'])
        flow.correct(f['reviewer'],self.work.pk,self.work.revision,rev(f['case']),f['register'].pk,None,f['parent'].pk,'Authorized manager reaffirms unchanged native facts after original intake grant withdrawal')
        self.advance();self.assertNotEqual(self.work.source_head_id,head);self.assertEqual(flow.schedule(self.work).pk,old.pk);self.assertGreaterEqual(self.work.budget_used,spent);self.assertEqual(self.work.status,'verified',self.work.finding)
    def test_basis_revocation_and_mapping_rule_return_reject_sql_verification(self):
        f=self.f;body=copy.deepcopy(f['ppe']['body']);body['label_as_of']='2026-03-31';r=capture(f,body);review(f,r,'register');review(f,r,'basis');f['register']=r
        self.start();self.advance();review(f,flow.schedule(self.work));self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        review(f,r,'basis','revoke')
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
        review(f,r,'basis');self.work.refresh_from_db();flow.correct(f['actor'],self.work.pk,self.work.revision,rev(f['case']),r.pk,None,f['parent'].pk,'Rebuild after explicit corrected basis decision');self.advance();review(f,flow.schedule(self.work));self.advance()
        key=next(k for k,purpose in analysis.PURPOSE.items() if purpose=='mapping')
        analysis.review(f['actor'],f['case'].pk,'mapping',f['configs'][key].pk,'Finance','return',f['e']['finance_review'].pk,'Return exact selected mapping rule for correction',rev(f['case']))
        with self.assertRaises((ValidationError,PermissionDenied)):flow.verify(self.work,f['actor'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
