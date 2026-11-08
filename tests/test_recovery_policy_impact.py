from copy import deepcopy
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import PermissionDenied,ValidationError
from apps.identity.models import Grant
from apps.pmo import recoveries
from apps.pmo.models import AuthorityRecoveryRequest
from apps.policy.services import active_component,resolve
from apps.policy import impact
from adapters import policy_impact as adapter
from adapters.recovery_policy_impact import KEY,POLICY,AUTHORITY,project
from tests.recovery_impact798_helpers import fixture,policy
from tests.helpers import rev

class RecoveryPolicyImpactTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.f=fixture();cls.row=cls.f['request']
    def rows(self):
        from django.apps import apps
        return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label in ('pmo','finance','core','documents','workflows')}
    def capture(self):
        f=self.f;new=policy(f)
        return impact.capture(f['a'],f['c'].pk,f['policy'].pk,new.pk,[KEY],f['e']['policy_decision'].pk,'Recovery request metadata only')
    def test_exact_pins_closed_metadata_current_not_recovered(self):
        f=self.f;before=self.rows()
        for component in (POLICY,*AUTHORITY):
            config=resolve(component,f['c']).configuration
            if config is not None:self.assertEqual(list(adapter.query(config,KEY,actor=f['a'])),[self.row])
            else:self.assertIsNone(self.row.snapshot['authority_policies'][component][1])
        value=project(self.row);self.assertTrue(value['request_snapshot_current']);self.assertFalse(value['authority_recovered'])
        self.assertEqual(set(value),{'id','kind','metadata_only','domain_route','adoption','snapshot_sha256','request_snapshot_current','state','authority_recovered','approval_granted','effects_performed'})
        self.assertEqual(before,self.rows())
    def test_policy_and_original_authority_change_stale_without_effects(self):
        policy(self.f);before=self.rows();self.assertFalse(project(self.row)['request_snapshot_current']);self.assertEqual(before,self.rows())
        fresh=recoveries.request_recovery(self.f['a'],self.f['c'].pk,'signed_adoption',self.f['adoption'].pk,self.f['e']['policy_decision'].pk,'Fresh snapshot only',rev(self.f['c']))
        self.assertTrue(project(fresh)['request_snapshot_current'])
        Grant.objects.filter(user=self.f['a'],case=self.f['c'],action='commercial.decide').update(active=False)
        before=self.rows();self.assertFalse(project(fresh)['request_snapshot_current']);self.assertEqual(before,self.rows())
    def test_minimal_reader_no_recovery_or_body_authority(self):
        from django.contrib.auth import get_user_model
        reader=get_user_model().objects.create_user(username='impact798-reader')
        for action in ('case.read','authority.read'):Grant.objects.create(user=reader,case=self.f['c'],action=action)
        adapter.authorize_row(reader,self.f['c'],KEY,self.row)
        self.assertEqual(list(adapter.query(self.f['policy'],KEY,actor=reader)),[self.row])
        self.assertTrue(project(self.row)['request_snapshot_current'])
    def test_missing_or_inactive_reader_before_lookup(self):
        f=self.f
        for action in ('case.read','authority.read'):
            g=Grant.objects.get(user=f['a'],case=f['c'],action=action);g.active=False;g.save()
            with patch('adapters.recovery_policy_impact.AuthorityRecoveryRequest.objects.filter',side_effect=AssertionError('lookup')):
                with self.assertRaises(PermissionDenied):adapter.query(f['policy'],KEY,actor=f['a'])
            g.active=True;g.save()
        f['a'].is_active=False;f['a'].save()
        with self.assertRaises(PermissionDenied):adapter.query(f['policy'],KEY,actor=f['a'])
    def test_typed_numeric_pin_and_wrong_component(self):
        f=self.f
        for bad in (str(f['policy'].pk),None,True):
            snap=deepcopy(self.row.snapshot);snap['recovery_policy_id']=bad
            AuthorityRecoveryRequest.objects.create(case=f['c'],adoption=f['adoption'],snapshot=snap,evidence=f['e']['policy_decision'],note='Adversarial typed pin',actor=f['a'])
        self.assertEqual(list(adapter.query(f['policy'],KEY,actor=f['a'])),[self.row])
        cfg=active_component(AUTHORITY[0],f['c'])
        for bad in (str(cfg.pk),None,True):
            snap=deepcopy(self.row.snapshot);snap['authority_policies'][cfg.component][1]=bad
            r=AuthorityRecoveryRequest.objects.create(case=f['c'],adoption=f['adoption'],snapshot=snap,evidence=f['e']['policy_decision'],note='Adversarial authority pin',actor=f['a'])
            self.assertNotIn(r.pk,adapter.query(cfg,KEY,actor=f['a']).values_list('pk',flat=True))
        unrelated=active_component('D11.template_storage_retention_rules',f['c'])
        self.assertFalse(adapter.query(unrelated,KEY,actor=f['a']).exists())
    def test_real_same_component_crosscase_with_dualgrants(self):
        other=fixture(username='impact798-other');other['c'].tenant='impact798-other-tenant';other['c'].save(update_fields=['tenant'])
        Grant.objects.bulk_create([Grant(user=self.f['a'],case=other['c'],action=g.action) for g in Grant.objects.filter(user=other['a'],case=other['c'])])
        self.assertEqual(list(adapter.query(other['policy'],KEY,actor=self.f['a'])),[other['request']])
        self.assertEqual(list(adapter.query(self.f['policy'],KEY,actor=self.f['a'])),[self.row])
        with self.assertRaises(PermissionDenied):adapter.authorize_row(self.f['a'],other['c'],KEY,self.row)
    def test_current_request_does_not_mean_active_or_latest_recovery(self):
        f=self.f;new=recoveries.request_recovery(f['a'],f['c'].pk,'signed_adoption',f['adoption'].pk,f['e']['policy_decision'].pk,'Later request remains unresolved',rev(f['c']))
        before=self.rows()
        with patch.object(recoveries,'active_recovery',side_effect=AssertionError('No active authority lookup')),patch.object(recoveries,'finalize_recovery',side_effect=AssertionError('No finalization')):
            for row in (self.row,new):self.assertTrue(project(row)['request_snapshot_current']);self.assertFalse(project(row)['authority_recovered'])
        self.assertEqual(before,self.rows())
    def test_review_agent_saved_no_body_and_current_observer(self):
        from django.contrib.auth import get_user_model
        from apps.agents.policy_impact import investigate
        from apps.policy.impact_views import choices
        from django.urls import reverse
        f=self.f;row=self.capture();reader=get_user_model().objects.create_user(username='impact798-reviewer')
        Grant.objects.bulk_create([Grant(user=reader,case=f['c'],action=g.action) for g in Grant.objects.filter(user=f['a'],case=f['c'])])
        impact.review(reader,f['c'].pk,row.pk,'accept',f['e']['policy_decision'].pk,'Independent engineering observation')
        before=self.rows();result=investigate(reader,f['c'].pk,row.pk);self.assertEqual(before,self.rows())
        self.assertFalse(result['business_approval']);self.assertEqual(result['effect_tools'],[])
        for key in ("'authority_state':","'source':","'user_id':","'signatures':","'note':","'finding':"):
            self.assertNotIn(key,str(result));self.assertNotIn(key,str(row.observation))
        self.assertIn(KEY,dict(choices(reader,f['c'])));self.assertTrue(reverse(adapter.ROUTES[KEY],args=[f['c'].pk]))
        Grant.objects.filter(user=reader,case=f['c'],action='authority.read').update(active=False)
        for call in (impact.inspect,investigate):
            with self.assertRaises(PermissionDenied):call(reader,f['c'].pk,row.pk)
    def test_generic_error_not_private_exception(self):
        with patch.object(recoveries,'current_request',side_effect=ValidationError('PRIVATE original principal')):
            value=project(self.row)
        self.assertFalse(value['request_snapshot_current']);self.assertNotIn('PRIVATE',str(value))
    def test_sql_closed_registry_and_budget(self):
        from apps.policy.models import ImpactAssessment
        from django.db import DatabaseError,transaction
        from apps.policy.impact import digest
        with patch.object(impact,'SNAPSHOT_LIMIT',1):row=self.capture()
        base={k:v for k,v in ImpactAssessment.objects.values().get(pk=row.pk).items() if k not in ('id','created_at')}
        for i,keys in enumerate([[],[KEY,KEY],['pmo.signed_adoption_recovery_requests.unknown'],[KEY]*24]):
            with self.assertRaises(DatabaseError),transaction.atomic():ImpactAssessment.objects.create(**dict(base,adapters=keys,operation_key=digest(['invalid798',i])))
    def test_configured_optional_authority_positive_and_typed_negatives(self):
        from datetime import timedelta
        from django.utils import timezone
        from django.contrib.auth import get_user_model
        from apps.policy.services import register_reference
        from tests.helpers import activate
        from tests.document_helpers import artifact
        f=self.f;a,c,e=f['a'],f['c'],f['e']
        delegate=get_user_model().objects.create_user(username='impact798-delegate')
        Grant.objects.create(user=delegate,case=c,action='commercial.decide')
        ref=register_reference(a,c.pk,'impact798-pm-delegate','schema:psl/decision-delegation/v1',
            {'role':'PM','principal_id':a.pk,'delegate_id':delegate.pk,'valid_from':(timezone.now()-timedelta(hours=1)).isoformat(),'valid_until':(timezone.now()+timedelta(hours=1)).isoformat()},e['policy_decision'].pk)
        delegation=activate(a,c,'D05.delegation_rules',[ref.ref],e['policy_decision'])
        matrix=artifact(a,c,'D05.decision_action_matrix','schema:psl/decision-actions/v1',{'rules':[{'role':'PMO Lead','actions':['return','reject']}]},e['policy_decision'])
        fresh=recoveries.request_recovery(a,c.pk,'signed_adoption',f['adoption'].pk,e['policy_decision'].pk,'Explicit configured authority snapshots',rev(c))
        for config in (delegation,matrix):
            self.assertEqual(fresh.snapshot['authority_policies'][config.component],['ACTIVE',config.pk])
            self.assertEqual(list(adapter.query(config,KEY,actor=a)),[fresh])
        for config in (delegation,matrix):
            for bad in (str(config.pk),None,True):
                snap=deepcopy(fresh.snapshot);snap['authority_policies'][config.component][1]=bad
                malformed=AuthorityRecoveryRequest.objects.create(case=c,adoption=f['adoption'],snapshot=snap,evidence=e['policy_decision'],note='Typed negative',actor=a)
                self.assertNotIn(malformed.pk,adapter.query(config,KEY,actor=a).values_list('pk',flat=True))
    def test_over_budget_cursor_and_no_partial_assessment(self):
        from apps.policy.models import ImpactAssessment
        f=self.f
        recoveries.request_recovery(f['a'],f['c'].pk,'signed_adoption',f['adoption'].pk,f['e']['policy_decision'].pk,'Second immutable request',rev(f['c']))
        page=impact.page(f['a'],f['c'].pk,f['policy'].pk,KEY,limit=1)
        self.assertEqual(len(page['records']),1);self.assertIsNotNone(page['next_cursor'])
        tail=impact.page(f['a'],f['c'].pk,f['policy'].pk,KEY,cursor=page['next_cursor'],limit=1)
        self.assertNotEqual(page['records'][0]['id'],tail['records'][0]['id']);self.assertIsNone(tail['next_cursor'])
        with self.assertRaises(ValidationError):impact.page(f['a'],f['c'].pk,f['policy'].pk,KEY,limit=0)
        with self.assertRaises(ValidationError):impact.page(f['a'],f['c'].pk,f['policy'].pk,KEY,cursor='not-a-cursor',limit=1)
        new=policy(f);before=ImpactAssessment.objects.count()
        with patch.object(impact,'SNAPSHOT_LIMIT',1),self.assertRaisesMessage(ValidationError,'snapshot exceeds'):
            impact.capture(f['a'],f['c'].pk,f['policy'].pk,new.pk,[KEY],f['e']['policy_decision'].pk,'Over budget')
        self.assertEqual(before,ImpactAssessment.objects.count())
    def test_exact_capture_review_audit_and_original_signed_history(self):
        from django.contrib.auth import get_user_model
        from apps.pmo.models import BaselineAdoption,CommercialSignaturePacket,CommercialSignatureUse,CommercialSignatureReaffirmation
        f=self.f;new=policy(f)
        reader=get_user_model().objects.create_user(username='impact798-audit-reviewer')
        Grant.objects.bulk_create([Grant(user=reader,case=f['c'],action=g.action) for g in Grant.objects.filter(user=f['a'],case=f['c'])])
        def history():
            return {'adoption':list(BaselineAdoption.objects.filter(pk=f['adoption'].pk).values()),
                'packets':list(CommercialSignaturePacket.objects.filter(case=f['c']).order_by('pk').values()),
                'uses':list(CommercialSignatureUse.objects.filter(packet__case=f['c']).order_by('pk').values()),
                'reaffirmations':list(CommercialSignatureReaffirmation.objects.filter(packet__case=f['c']).values())}
        original=history();self.assertEqual(original['reaffirmations'],[])
        def check(before,after,actor,action,data):
            old=before['core.Audit'];now=after['core.Audit'];ids={r['id'] for r in old}
            self.assertEqual([r for r in now if r['id'] in ids],old)
            added=[r for r in now if r['id'] not in ids];self.assertEqual(len(added),1)
            self.assertEqual((added[0]['actor_id'],added[0]['case_id'],added[0]['action'],added[0]['data']),(actor,f['c'].pk,action,data))
            expected=dict(before);expected['core.Audit']=now;self.assertEqual(expected,after)
        before=self.rows()
        row=impact.capture(f['a'],f['c'].pk,f['policy'].pk,new.pk,[KEY],f['e']['policy_decision'].pk,'Exact metadata audit')
        check(before,self.rows(),f['a'].pk,'policy.impact.captured',{'assessment':row.pk,'previous':f['policy'].pk,'successor':new.pk})
        before=self.rows();review=impact.review(reader,f['c'].pk,row.pk,'accept',f['e']['policy_decision'].pk,'Exact independent review')
        check(before,self.rows(),reader.pk,'policy.impact.reviewed',{'assessment':row.pk,'review':review.pk,'verdict':'accept'})
        self.assertEqual(original,history())
