from copy import deepcopy
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import PermissionDenied,ValidationError
from apps.pmo import approval_routing as routing
from apps.pmo.models import ApprovalRouteJob,ApprovalRouteReceipt
from apps.policy import impact
from apps.policy.services import active_component
from apps.policy.approval_validators import ROUTES,CONTRACTS
from apps.identity.models import Grant
from adapters import policy_impact as adapter
from adapters.approval_routing_policy_impact import KEY,project
from tests.approval_helpers import fixture,policy

class ApprovalRoutingPolicyImpactTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f=fixture(prefix='impact796')
        cls.job=routing.reserve(cls.f['actor'],cls.f['case'].pk,cls.f['request'].pk)
        cls.config=active_component(ROUTES,cls.f['case'])
    def rows(self):
        from django.apps import apps
        return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models()
            if m._meta.app_label in ('pmo','core','workflows')}
    def capture(self):
        f=self.f;new=policy(f,ROUTES,deepcopy(f['v']['routes']))
        return impact.capture(f['actor'],f['case'].pk,self.config.pk,new.pk,[KEY],f['e']['policy_decision'].pk,'Observe routing metadata only')
    def receipt(self):
        # Isolated synthetic fixture receipt, not source approval or live delivery.
        return ApprovalRouteReceipt.objects.create(job=self.job,recipient_id=self.job.intent['recipient'],
            operation_key=self.job.operation_key,payload=self.job.intent['public'])
    def test_direct_route_contract_authority_and_no_effect_metadata(self):
        f=self.f;before=self.rows()
        for key in (ROUTES,CONTRACTS,'D05.role_principal_assignments'):
            self.assertEqual(list(adapter.query(active_component(key,f['case']),KEY,actor=f['actor'])),[self.job])
        value=project(self.job)
        self.assertTrue(value['native_intent_current']);self.assertEqual(value['state'],'pending_effect')
        self.assertFalse(value['dispatch_readiness_evaluated']);self.assertFalse(value['approval_granted'])
        self.assertEqual(set(value),{'id','kind','metadata_only','domain_route','request','generation','purpose','status','intent_sha256','receipt','receipt_conflict','native_intent_current','state','dispatch_readiness_evaluated','dispatch_authorized','approval_granted','effects_performed'})
        self.assertEqual(before,self.rows())
    def test_observer_read_does_not_require_route_or_source_body_rights(self):
        from django.contrib.auth import get_user_model
        f=self.f;reader=get_user_model().objects.create_user(username='impact796-reader')
        for action in ('case.read','approval.read'):Grant.objects.create(case=f['case'],user=reader,action=action)
        adapter.authorize_row(reader,f['case'],KEY,self.job)
        self.assertEqual(list(adapter.query(self.config,KEY,actor=reader)),[self.job])
        Grant.objects.filter(case=f['case'],action='approval.source.read:synthetic-qa').update(active=False)
        value=project(self.job);self.assertNotIn('source_decision',value);self.assertNotIn('subject',value)
        self.assertTrue(value['native_intent_current'])
    def test_observer_revocation_precedes_lookup(self):
        Grant.objects.filter(case=self.f['case'],user=self.f['actor'],action='approval.read').update(active=False)
        with patch('adapters.approval_routing_policy_impact.ApprovalRouteJob.objects.filter',side_effect=AssertionError('Unauthorized lookup')):
            with self.assertRaises(PermissionDenied):adapter.query(self.config,KEY,actor=self.f['actor'])
    def test_policy_change_preserves_confirmed_receipt(self):
        receipt=self.receipt();self.job.status='confirmed';self.job.save(update_fields=['status'])
        policy(self.f,ROUTES,deepcopy(self.f['v']['routes']))
        before=self.rows();value=project(self.job)
        self.assertFalse(value['native_intent_current']);self.assertEqual(value['receipt'],receipt.pk)
        self.assertEqual(value['state'],'committed_effect');self.assertEqual(before,self.rows())
    def test_uncertain_receipt_and_terminal_states_stay_distinct(self):
        self.job.status='unknown';self.job.save(update_fields=['status'])
        self.assertEqual(project(self.job)['state'],'uncertain_effect')
        receipt=self.receipt();before=self.rows()
        self.assertEqual(project(self.job)['state'],'committed_receipt_requires_reconciliation')
        self.assertEqual(project(self.job)['receipt'],receipt.pk);self.assertEqual(before,self.rows())
    def test_terminal_and_inconsistent_confirmed_without_receipt(self):
        for status,state in [('cancelled','historical_terminal_routing'),('replaced','historical_terminal_routing'),('confirmed','inconsistent_or_unknown_effect_state'),('leased','uncertain_effect'),('held','pending_effect')]:
            self.job.status=status;self.assertEqual(project(self.job)['state'],state)
    def test_receipt_conflict_and_native_error_are_generic(self):
        from adapters.approvals import InternalApprovalRoutingAdapter
        with patch.object(InternalApprovalRoutingAdapter,'lookup',side_effect=ValidationError('PRIVATE')),patch.object(routing,'intent',side_effect=PermissionDenied('SECRET')):
            value=project(self.job)
        self.assertEqual(value['state'],'receipt_conflict_requires_reconciliation')
        self.assertNotIn('PRIVATE',str(value));self.assertNotIn('SECRET',str(value))
    def test_original_principal_and_factory_context_preserved(self):
        self.job.intent=deepcopy(self.job.intent);self.job.intent['factory_execution']={'work':123}
        with patch.object(routing,'intent',return_value=self.job.intent) as recompute:
            self.assertTrue(project(self.job)['native_intent_current'])
        recompute.assert_called_once_with(self.job.actor,self.job.request,self.job.purpose,123)
        Grant.objects.filter(case=self.f['case'],user=self.f['actor'],action='approval.route').update(active=False)
        self.assertFalse(project(self.job)['native_intent_current'])
    def test_saved_impact_and_agent_revoke_reader(self):
        from apps.agents.policy_impact import investigate
        row=self.capture();f=self.f
        Grant.objects.filter(case=f['case'],user=f['actor'],action='approval.read').update(active=False)
        for call in (impact.inspect,investigate):
            with self.assertRaises(PermissionDenied):call(f['actor'],f['case'].pk,row.pk)
    def test_sql_closed_registry_negative(self):
        from django.db import transaction,DatabaseError
        from apps.policy.models import ImpactAssessment
        from apps.policy.impact import digest
        row=self.capture();base={k:v for k,v in ImpactAssessment.objects.values().get(pk=row.pk).items() if k not in ('id','created_at')}
        for i,keys in enumerate([[],[KEY,KEY],['pmo.approval_routing_jobs.unknown'],[KEY]*22]):
            with self.assertRaises(DatabaseError),transaction.atomic():
                ImpactAssessment.objects.create(**dict(base,adapters=keys,operation_key=digest(['bad796',i])))
    def clone(self,changes=None):
        intent=deepcopy(self.job.intent);intent.update(changes or {})
        n=ApprovalRouteJob.objects.filter(request=self.job.request).count()+1
        from apps.documents.contracts import digest
        return ApprovalRouteJob.objects.create(request=self.job.request,actor=self.job.actor,generation=n,
            purpose='request',operation_key=digest(['impact796-adversarial',n]),intent=intent)
    def test_numeric_pins_reject_strings_null_boolean_wrong_position_component(self):
        # Native job INSERT has no typed intent trigger; UPDATE/DELETE guards stay on.
        contract=active_component(CONTRACTS,self.f['case'])
        for bad in (str(self.config.pk),None,True):self.clone({'policies':[bad,contract.pk]})
        self.clone({'policies':[contract.pk,self.config.pk]})
        self.clone({'policies':[None,None],'authority':{'unrelated.component':self.config.pk}})
        self.assertEqual(list(adapter.query(self.config,KEY,actor=self.f['actor'])),[self.job])
        authority=active_component('D05.role_principal_assignments',self.f['case'])
        for bad in (str(authority.pk),None,True):
            row=self.clone({'policies':[None,None],'authority':{authority.component:bad}})
            self.assertNotIn(row.pk,adapter.query(authority,KEY,actor=self.f['actor']).values_list('pk',flat=True))
    def test_same_component_cross_case_dual_grants(self):
        other=fixture(prefix='impact796-other');other['case'].tenant='impact796-other-tenant';other['case'].save(update_fields=['tenant'])
        job=routing.reserve(other['actor'],other['case'].pk,other['request'].pk)
        Grant.objects.bulk_create([Grant(case=other['case'],user=self.f['actor'],action=g.action) for g in Grant.objects.filter(case=other['case'],user=other['actor'])])
        config=active_component(ROUTES,other['case'])
        self.assertEqual(list(adapter.query(config,KEY,actor=self.f['actor'])),[job])
        self.assertEqual(list(adapter.query(self.config,KEY,actor=self.f['actor'])),[self.job])
        with self.assertRaises(PermissionDenied):adapter.authorize_row(self.f['actor'],other['case'],KEY,self.job)
    def test_inactive_and_missing_case_reader_before_lookup(self):
        f=self.f
        for mode in ('inactive','case.read'):
            if mode=='inactive':f['actor'].is_active=False;f['actor'].save()
            else:Grant.objects.filter(case=f['case'],user=f['actor'],action='case.read').update(active=False)
            with patch('adapters.approval_routing_policy_impact.ApprovalRouteJob.objects.filter',side_effect=AssertionError('lookup')):
                with self.assertRaises(PermissionDenied):adapter.query(self.config,KEY,actor=f['actor'])
            f['actor'].is_active=True;f['actor'].save()
    def test_request_successor_stales_original_without_effects(self):
        from apps.pmo import approvals
        f=self.f;r=f['request']
        approvals.create_request(f['actor'],f['case'].pk,r.reference,f['candidate'].pk,r.kind,'BUILD-2','RELEASE-2',f['e']['approval_request'].pk,predecessor=r.pk)
        before=self.rows();self.assertFalse(project(self.job)['native_intent_current']);self.assertEqual(before,self.rows())
    def test_independent_review_agent_closed_saved_metadata(self):
        from django.contrib.auth import get_user_model
        from apps.agents.policy_impact import investigate
        from apps.policy.impact_views import choices
        f=self.f;row=self.capture();reader=get_user_model().objects.create_user(username='impact796-reviewer')
        Grant.objects.bulk_create([Grant(case=f['case'],user=reader,action=g.action) for g in Grant.objects.filter(case=f['case'],user=f['actor'])])
        before=self.rows();impact.review(reader,f['case'].pk,row.pk,'accept',f['e']['policy_decision'].pk,'Engineering receipt metadata only')
        result=investigate(reader,f['case'].pk,row.pk);self.assertFalse(result['business_approval']);self.assertEqual(result['effect_tools'],[])
        row.refresh_from_db()
        for body in (str(row.observation),str(result)):
            for key in ("'public':","'subject':","'recipient':","'source_owner':","'authority':","'source_decision':","'error':"):
                self.assertNotIn(key,body)
        after=self.rows();before.pop('core.Audit');after.pop('core.Audit');self.assertEqual(before,after)
        self.assertIn(KEY,dict(choices(reader,f['case'])))
    def test_snapshot_budget_exact_boundary_no_partial_assessment(self):
        from apps.policy.models import ImpactAssessment
        f=self.f;new=policy(f,ROUTES,deepcopy(f['v']['routes']))
        args=(f['actor'],f['case'].pk,self.config.pk,new.pk,[KEY],f['e']['policy_decision'].pk,'Exact bounded routing')
        with patch.object(impact,'SNAPSHOT_LIMIT',1):
            self.assertEqual(len(impact.capture(*args).observation['domains'][KEY]),1)
        self.clone();before=ImpactAssessment.objects.count()
        with patch.object(impact,'SNAPSHOT_LIMIT',1),self.assertRaisesMessage(ValidationError,'snapshot exceeds'):
            impact.capture(*args)
        self.assertEqual(before,ImpactAssessment.objects.count())

from django.test import TransactionTestCase
class ApprovalRoutingImpactLockTests(TransactionTestCase):
    def setUp(self):
        self.f=fixture(prefix='impact796-lock')
        self.job=routing.reserve(self.f['actor'],self.f['case'].pk,self.f['request'].pk)
        self.old=active_component(ROUTES,self.f['case']);self.new=policy(self.f,ROUTES,deepcopy(self.f['v']['routes']))
    def capture(self):
        f=self.f
        return impact.capture(f['actor'],f['case'].pk,self.old.pk,self.new.pk,[KEY],f['e']['policy_decision'].pk,'Locked routing observation')
    def test_actual_query_locks_before_hydration(self):
        from django.db import connection
        ApprovalRouteJob.objects.filter(pk=self.job.pk).update(status='unknown')
        selects=[]
        def wrapper(execute,sql,params,many,context):
            if 'FROM "pmo_approvalroutejob"' in sql:selects.append(sql)
            return execute(sql,params,many,context)
        with connection.execute_wrapper(wrapper):row=self.capture()
        self.assertTrue(selects, 'Expected a routing-job SELECT')
        self.assertIn('FOR UPDATE',selects[0])
        self.assertIn('NOWAIT',selects[0])
        self.assertEqual(row.observation['domains'][KEY][0]['status'],'unknown')
    def test_other_connection_lock_holds_without_partial_assessment(self):
        from threading import Event,Thread
        from django.db import transaction,connections,close_old_connections
        from apps.policy.models import ImpactAssessment
        ready=Event();release=Event();errors=[]
        def holder():
            close_old_connections()
            try:
                with transaction.atomic():
                    ApprovalRouteJob.objects.select_for_update().get(pk=self.job.pk)
                    ready.set()
                    if not release.wait(10):raise RuntimeError('Bounded lock fixture timeout')
            except BaseException as exc:errors.append(exc);ready.set()
            finally:connections.close_all()
        thread=Thread(target=holder);thread.start()
        try:
            self.assertTrue(ready.wait(5));self.assertFalse(errors)
            before=ImpactAssessment.objects.count()
            with self.assertRaisesMessage(ValidationError,'being reconciled'):self.capture()
            self.assertEqual(before,ImpactAssessment.objects.count())
        finally:release.set();thread.join(12)
        self.assertFalse(thread.is_alive());self.assertFalse(errors)
