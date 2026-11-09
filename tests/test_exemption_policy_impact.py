from copy import copy
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import PermissionDenied,ValidationError
from django.apps import apps
from apps.identity.models import Grant
from apps.policy.services import active_component
from apps.policy.signature_validators import COMPONENT
from apps.policy import impact
from apps.pmo import signature_exemptions as native
from adapters import policy_impact as adapter
from adapters.exemption_policy_impact import KEY,AUTHORITY,project
from tests.exemption_impact801_helpers import fixture,policy,capture

class ExemptionPolicyImpactTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.f=fixture()
    def facts(self):
        return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models()
            if m._meta.app_label in ('pmo','core','documents','finance','workflows')}
    def assessment(self):
        f=self.f;new=policy(f)
        return impact.capture(f['a'],f['c'].pk,f['policy'].pk,new.pk,[KEY],f['e']['policy_decision'].pk,'Selected unsigned exemption metadata')
    def test_exact_nonnull_fk_and_closed_noeffect_metadata(self):
        f=self.f;before=self.facts()
        for component in (COMPONENT,AUTHORITY):
            self.assertEqual(list(adapter.query(active_component(component,f['c']),KEY,actor=f['a'])),[f['row']])
        value=project(f['row']);self.assertTrue(value['selected_exemption_valid_now'])
        self.assertEqual(set(value),{'id','kind','metadata_only','domain_route','policy','authority','exemption_sha256','selected_exemption_valid_now','state','signature_created','signing_authorized','baseline_assurance_granted','effects_performed'})
        for flag in ('signature_created','signing_authorized','baseline_assurance_granted','effects_performed'):self.assertFalse(value[flag])
        wrong=copy(f['policy']);wrong.component='D11.hypercare_criteria_ref'
        self.assertFalse(adapter.query(wrong,KEY,actor=f['a']).exists());self.assertEqual(before,self.facts())
    def test_same_component_crosscase_dual_grants_and_row_isolation(self):
        f=self.f;other=fixture(username='impact801-other')
        Grant.objects.bulk_create([Grant(case=other['c'],user=f['a'],action=g.action) for g in Grant.objects.filter(case=other['c'],user=other['a'])])
        self.assertEqual(list(adapter.query(other['policy'],KEY,actor=f['a'])),[other['row']])
        self.assertEqual(list(adapter.query(f['policy'],KEY,actor=f['a'])),[f['row']])
        with self.assertRaises(PermissionDenied):adapter.authorize_row(f['a'],other['c'],KEY,f['row'])
    def test_minimal_commercial_reader_is_not_exemption_recorder(self):
        from django.contrib.auth import get_user_model
        f=self.f;reader=get_user_model().objects.create_user(username='impact801-reader')
        for action in ('case.read','commercial.read'):Grant.objects.create(user=reader,case=f['c'],action=action)
        before=self.facts();adapter.authorize_row(reader,f['c'],KEY,f['row'])
        self.assertEqual(list(adapter.query(f['policy'],KEY,actor=reader)),[f['row']])
        self.assertTrue(project(f['row'])['selected_exemption_valid_now']);self.assertEqual(before,self.facts())
    def test_observer_grants_inactive_denied_before_lookup(self):
        f=self.f
        for action in ('case.read','commercial.read'):
            g=Grant.objects.get(user=f['a'],case=f['c'],action=action);g.active=False;g.save()
            with patch('adapters.exemption_policy_impact.BaselineSignatureExemption.objects.filter',side_effect=AssertionError('lookup')):
                with self.assertRaises(PermissionDenied):adapter.query(f['policy'],KEY,actor=f['a'])
            g.active=True;g.save()
        f['a'].is_active=False;f['a'].save()
        with patch('adapters.exemption_policy_impact.BaselineSignatureExemption.objects.filter',side_effect=AssertionError('lookup')):
            with self.assertRaises(PermissionDenied):adapter.query(f['policy'],KEY,actor=f['a'])
            with self.assertRaises(PermissionDenied):adapter.query(f['policy'],KEY)
    def test_original_recorder_revocation_and_authority_successor_preserve_history(self):
        from tests.helpers import activate
        f=self.f;g=Grant.objects.get(user=f['a'],case=f['c'],action='baseline.sign');g.active=False;g.save()
        before=self.facts();self.assertFalse(project(f['row'])['selected_exemption_valid_now']);self.assertEqual(before,self.facts())
        g.active=True;g.save();old=active_component(AUTHORITY,f['c'])
        activate(f['a'],f['c'],AUTHORITY,old.envelope['value'],f['e']['policy_decision'])
        before=self.facts();self.assertFalse(project(f['row'])['selected_exemption_valid_now'])
        self.assertEqual(list(adapter.query(old,KEY,actor=f['a'])),[f['row']]);self.assertEqual(before,self.facts())
    def test_policy_scope_and_unresolved_successors_never_renew_exemption(self):
        from apps.core.services import add_evidence
        f=self.f;scope=add_evidence(f['a'],f['c'].pk,'internal_project_scope','New synthetic owner scope','synthetic:impact801')
        new=policy(f,scope=scope);before=self.facts()
        self.assertFalse(project(f['row'])['selected_exemption_valid_now']);self.assertFalse(adapter.query(new,KEY,actor=f['a']).exists())
        self.assertEqual(list(adapter.query(f['policy'],KEY,actor=f['a'])),[f['row']]);self.assertEqual(before,self.facts())
        policy(f,requirement='unresolved');before=self.facts()
        self.assertFalse(project(f['row'])['selected_exemption_valid_now']);self.assertEqual(before,self.facts())
    def test_older_same_source_exemption_remains_selected_valid_not_latest_assurance(self):
        f=self.f;new=capture(f);self.assertEqual(new.predecessor_id,f['row'].pk)
        self.assertEqual(native.latest(f['c']).pk,new.pk)
        before=self.facts()
        self.assertTrue(project(f['row'])['selected_exemption_valid_now']);self.assertTrue(project(new)['selected_exemption_valid_now'])
        self.assertEqual(list(adapter.query(f['policy'],KEY,actor=f['a'])),[f['row'],new]);self.assertEqual(before,self.facts())
    def test_new_unsigned_prd_draft_does_not_destroy_adopted_source_proof(self):
        from apps.core.services import add_evidence
        f=self.f;add_evidence(f['a'],f['c'].pk,'prd','Later unsigned draft','synthetic:impact801')
        before=self.facts();self.assertTrue(project(f['row'])['selected_exemption_valid_now']);self.assertEqual(before,self.facts())
    def test_native_unsigned_plan_and_costing_replacement_stales_history(self):
        from apps.core.services import add_evidence
        from apps.pmo.services import prepare_baseline
        from apps.pmo.models import Baseline
        from tests.helpers import rev
        f=self.f;a,c=f['a'],f['c'];old=Baseline.objects.get(case=c)
        plan=add_evidence(a,c.pk,'plan','New unsigned plan','synthetic:impact801');cost=add_evidence(a,c.pk,'costing','New supplied costing','synthetic:impact801')
        prepare_baseline(a,c.pk,plan.pk,cost.pk,f['e']['sow'].pk,rev(c))
        current=Baseline.objects.get(case=c);self.assertNotEqual(old.plan_id,current.plan_id);self.assertNotEqual(old.costing_id,current.costing_id);self.assertIsNone(current.signed_id)
        before=self.facts();self.assertFalse(project(f['row'])['selected_exemption_valid_now'])
        self.assertEqual(list(adapter.query(f['policy'],KEY,actor=a)),[f['row']]);self.assertEqual(before,self.facts())
    def test_generic_native_error_and_no_latest_or_effect_commands(self):
        with patch.object(native,'validate_exemption',side_effect=ValidationError('PRIVATE scope details')),patch.object(native,'assert_current_baseline_assurance',side_effect=AssertionError('latest assurance')),patch.object(native,'record_exemption',side_effect=AssertionError('write')):
            value=project(self.f['row'])
        self.assertFalse(value['selected_exemption_valid_now']);self.assertNotIn('PRIVATE',str(value))
    def test_saved_capture_review_agent_exact_audit_and_revoked_reader(self):
        from django.contrib.auth import get_user_model
        from apps.agents.policy_impact import investigate
        from scripts.impact795_upgrade_lifecycle import unchanged_except_capture_audit
        f=self.f;new=policy(f);before=self.facts()
        row=impact.capture(f['a'],f['c'].pk,f['policy'].pk,new.pk,[KEY],f['e']['policy_decision'].pk,'Selected exemption metadata')
        unchanged_except_capture_audit(before,self.facts(),actor=f['a'].pk,case=f['c'].pk,assessment=row.pk,previous=f['policy'].pk,successor=new.pk)
        reader=get_user_model().objects.create_user(username='impact801-reviewer')
        Grant.objects.bulk_create([Grant(case=f['c'],user=reader,action=g.action) for g in Grant.objects.filter(case=f['c'],user=f['a'])])
        before=self.facts();review=impact.review(reader,f['c'].pk,row.pk,'accept',f['e']['policy_decision'].pk,'Independent metadata review')
        result=investigate(reader,f['c'].pk,row.pk);self.assertFalse(result['business_approval']);self.assertEqual(result['effect_tools'],[])
        after=self.facts();old_ids={r['id'] for r in before['core.Audit']}
        self.assertEqual([r for r in after['core.Audit'] if r['id'] in old_ids],before['core.Audit'])
        added=[r for r in after['core.Audit'] if r['id'] not in old_ids];self.assertEqual(len(added),1)
        self.assertEqual((added[0]['actor_id'],added[0]['case_id'],added[0]['action'],added[0]['data']),(reader.pk,f['c'].pk,'policy.impact.reviewed',{'assessment':row.pk,'review':review.pk,'verdict':'accept'}))
        expected=dict(before);expected['core.Audit']=after['core.Audit'];self.assertEqual(expected,after)
        for body in (str(row.observation),str(result)):
            for key in ("'sources':","'approval_refs':","'scope_evidence':","'actor':","'note':","'operation_key':"):
                self.assertNotIn(key,body)
        Grant.objects.filter(case=f['c'],user=reader,action='commercial.read').update(active=False)
        for call in (impact.inspect,investigate):
            with self.assertRaises(PermissionDenied):call(reader,f['c'].pk,row.pk)
    def test_sql_closed_registry_and_exact_budget_no_partial_assessment(self):
        from apps.policy.models import ImpactAssessment
        from apps.policy.impact import digest
        from django.db import transaction,DatabaseError
        f=self.f
        with patch.object(impact,'SNAPSHOT_LIMIT',1):row=self.assessment()
        self.assertEqual(len(row.observation['domains'][KEY]),1)
        base={k:v for k,v in ImpactAssessment.objects.values().get(pk=row.pk).items() if k not in ('id','created_at')}
        for i,keys in enumerate([[],[KEY,KEY],['pmo.baseline_signature_exemptions.unknown'],[KEY]*27]):
            with self.assertRaises(DatabaseError),transaction.atomic():ImpactAssessment.objects.create(**dict(base,adapters=keys,operation_key=digest(['bad801',i])))
        # Fresh current-policy exemption shares same original authority, native guards remain enabled.
        capture(f)
        from tests.helpers import activate
        old=active_component(AUTHORITY,f['c']);new=activate(f['a'],f['c'],AUTHORITY,old.envelope['value'],f['e']['policy_decision'])
        before=ImpactAssessment.objects.count()
        with patch.object(impact,'SNAPSHOT_LIMIT',1),self.assertRaisesMessage(ValidationError,'snapshot exceeds'):
            impact.capture(f['a'],f['c'].pk,old.pk,new.pk,[KEY],f['e']['policy_decision'].pk,'Exact exemption budget')
        self.assertEqual(before,ImpactAssessment.objects.count())
