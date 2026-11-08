from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import PermissionDenied
from django.apps import apps
from apps.finance import payments
from apps.identity.models import Grant
from apps.policy import impact
from apps.policy.services import active_component
from apps.policy.payment_validators import DENOMINATOR,FUNDS
from adapters import policy_impact as adapter
from adapters.payment_policy_impact import KEY,project
from tests.payment_helpers import configure
from tests.payment_impact795_helpers import fixture
from tests.helpers import rev

class PaymentPolicyImpactTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f=fixture()
        configure(cls.f.actor,cls.f.case,cls.f.cov,cls.f.actor,components=[DENOMINATOR,FUNDS])
        cls.row=payments.assess(cls.f.actor,cls.f.case.pk,cls.f.d.pk,cls.f.cov.pk,rev(cls.f.case))
        cls.config=active_component(FUNDS,cls.f.case)
        from tests.payment_impact795_helpers import assert_predeployment_fixture
        assert_predeployment_fixture(cls.f)
        if cls.row.manifest['context']['deployment_request'] is not None or cls.row.manifest['context']['external_ref'] is not None:
            raise AssertionError('Predeployment assessment must not claim deployment request')
    def successor(self):
        return configure(self.f.actor,self.f.case,self.f.cov,self.f.actor,components=[FUNDS])[0]
    def capture(self):
        new=self.successor()
        return impact.capture(self.f.actor,self.f.case.pk,self.config.pk,new.pk,[KEY],self.f.e['policy_decision'].pk,'Metadata only payment impact')
    def snapshot(self):
        # Baseline is taken only after synthetic native fixture + assessment setup.
        return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models()
            if m._meta.app_label in ('finance','pmo','core','workflows')}
    def test_exact_direct_pins_and_closed_metadata_without_effects(self):
        f=self.f;before=self.snapshot()
        for component in (DENOMINATOR,FUNDS):
            config=active_component(component,f.case)
            self.assertEqual(list(adapter.query(config,KEY,actor=f.actor)),[self.row])
        self.assertFalse(adapter.query(active_component('D05.role_principal_assignments',f.case),KEY,actor=f.actor).exists())
        adapter.authorize_row(f.actor,f.case,KEY,self.row);value=adapter.project(self.row,KEY)
        self.assertTrue(value['native_current']);self.assertEqual(self.row.result['status'],'BELOW_EXPECTATION')
        self.assertEqual(set(value),{'id','kind','metadata_only','domain_route','sha256','dossier','coverage','native_current','state','assessment_renewed','debt_waived','deployment_authorized','deployment_dispatched','cash_moved'})
        self.assertEqual(before,self.snapshot())
    def test_successor_stales_original_without_renewal(self):
        new=self.successor();before=self.snapshot()
        self.assertFalse(project(self.row)['native_current'])
        self.assertEqual(list(adapter.query(self.config,KEY,actor=self.f.actor)),[self.row])
        self.assertFalse(adapter.query(new,KEY,actor=self.f.actor).exists())
        self.assertEqual(before,self.snapshot())
        fresh=payments.assess(self.f.actor,self.f.case.pk,self.f.d.pk,self.f.cov.pk,rev(self.f.case))
        self.assertEqual(list(adapter.query(new,KEY,actor=self.f.actor)),[fresh])
    def test_all_observer_grants_precede_lookup(self):
        for action in ('case.read','payment.read','finance.read','delivery.read'):
            grant=Grant.objects.get(user=self.f.actor,case=self.f.case,action=action)
            grant.active=False;grant.save()
            with patch('adapters.payment_policy_impact.PaymentAssessment.objects.filter',side_effect=AssertionError('lookup before authorization')):
                with self.assertRaises(PermissionDenied):adapter.query(self.config,KEY,actor=self.f.actor)
            grant.active=True;grant.save()
        with self.assertRaises(PermissionDenied):adapter.query(self.config,KEY)
    def test_cash_fact_change_uses_native_currentness(self):
        from tests.settlement_helpers import allocate
        f=self.f;allocate(f.actor,f.case,f.lot,f.iss,'1',f.cash_e,'impact795-change')
        before=self.snapshot();self.assertFalse(project(self.row)['native_current']);self.assertEqual(before,self.snapshot())
    def test_saved_impact_and_agent_revoke_current_reader(self):
        from apps.agents.policy_impact import investigate
        row=self.capture()
        Grant.objects.filter(user=self.f.actor,case=self.f.case,action='payment.read').update(active=False)
        for call in (impact.inspect,investigate):
            with self.assertRaises(PermissionDenied):call(self.f.actor,self.f.case.pk,row.pk)
    def test_choices_route_and_inactive_observer(self):
        from apps.policy.impact_views import choices
        from django.urls import reverse
        f=self.f;self.assertIn(KEY,dict(choices(f.actor,f.case)))
        self.assertTrue(reverse(adapter.ROUTES[KEY],args=[f.case.pk]))
        f.actor.is_active=False;f.actor.save()
        with self.assertRaises(PermissionDenied):adapter.query(self.config,KEY,actor=f.actor)
    def test_cross_case_config_and_row_rejected(self):
        from tests.helpers import setup_case,prepared
        a,c=setup_case(username='impact795-other');prepared(a,c)
        other=active_component('D05.role_principal_assignments',c)
        self.assertFalse(adapter.query(other,KEY,actor=a).exists())
        with self.assertRaises(PermissionDenied):adapter.authorize_row(a,c,KEY,self.row)
    def test_native_errors_are_not_exposed_or_effect_commands_called(self):
        from django.core.exceptions import ValidationError
        with patch.object(payments,'assessment_current',side_effect=ValidationError('PRIVATE financial details')),patch.object(payments,'assess',side_effect=AssertionError('write')),patch.object(payments,'reserve',side_effect=AssertionError('release')):
            value=project(self.row)
        self.assertFalse(value['native_current']);self.assertNotIn('PRIVATE',str(value))
    def test_json_numeric_pin_not_string_boolean_null_or_wrong_component(self):
        from copy import deepcopy
        from apps.finance.payment_models import PaymentAssessment
        from apps.finance.billing import digest
        # Payment assessments have append-only UPDATE/DELETE guards, not an INSERT
        # shape guard. Adversarial test rows are inserted without disabling either.
        for bad in (str(self.config.pk),None,True):
            manifest=deepcopy(self.row.manifest);manifest['policies'][FUNDS]['id']=bad
            PaymentAssessment.objects.create(case=self.f.case,dossier=self.f.d,coverage=self.f.cov,
                actor=self.f.actor,manifest=manifest,result=self.row.result,
                sha256=digest({'manifest':manifest,'result':self.row.result}))
        manifest=deepcopy(self.row.manifest)
        manifest['policies'][FUNDS]['id']=None;manifest['policies']['D05.role_principal_assignments']={'id':self.config.pk}
        PaymentAssessment.objects.create(case=self.f.case,dossier=self.f.d,coverage=self.f.cov,actor=self.f.actor,
            manifest=manifest,result=self.row.result,sha256=digest({'manifest':manifest,'result':self.row.result}))
        self.assertEqual(list(adapter.query(self.config,KEY,actor=self.f.actor)),[self.row])
    def test_same_component_other_case_with_dual_grants(self):
        from tests.helpers import setup_case,prepared
        from tests.billing_helpers import coverage
        a,c=setup_case(username='impact795-dual');prepared(a,c)
        c.tenant='impact795-other-tenant';c.save(update_fields=['tenant'])
        cov=coverage(a,c,completeness='complete')
        other=configure(a,c,cov,a,components=[FUNDS])[0]
        Grant.objects.bulk_create([Grant(case=c,user=self.f.actor,action=g.action) for g in Grant.objects.filter(case=c,user=a)])
        self.assertEqual(other.component,self.config.component)
        self.assertFalse(adapter.query(other,KEY,actor=self.f.actor).exists())
        self.assertEqual(list(adapter.query(self.config,KEY,actor=self.f.actor)),[self.row])
        with self.assertRaises(PermissionDenied):adapter.authorize_row(self.f.actor,c,KEY,self.row)
    def test_sql_closed_list_rejects_unknown_duplicate_empty_and_excess(self):
        from django.db import transaction,DatabaseError
        from apps.policy.models import ImpactAssessment
        from apps.policy.impact import digest
        row=self.capture()
        base={k:v for k,v in ImpactAssessment.objects.values().get(pk=row.pk).items() if k not in ('id','created_at')}
        for i,keys in enumerate([['finance.payment_assessments.unknown'],[KEY,KEY],[],[KEY]*21]):
            with self.assertRaises(DatabaseError),transaction.atomic():
                ImpactAssessment.objects.create(**dict(base,adapters=keys,operation_key=digest(['invalid795',i])))
    def test_independent_review_agent_saved_body_and_revoked_domain_grants(self):
        import json
        from django.contrib.auth import get_user_model
        from apps.agents.policy_impact import investigate
        from apps.policy.impact_views import choices
        row=self.capture();f=self.f
        reviewer=get_user_model().objects.create_user(username='impact795-reviewer')
        Grant.objects.bulk_create([Grant(case=f.case,user=reviewer,action=g.action) for g in Grant.objects.filter(case=f.case,user=f.actor)])
        before=self.snapshot()
        impact.review(reviewer,f.case.pk,row.pk,'accept',f.e['policy_decision'].pk,'Independent engineering metadata review only')
        result=investigate(reviewer,f.case.pk,row.pk)
        self.assertFalse(result['business_approval']);self.assertEqual(result['effect_tools'],[])
        row.refresh_from_db();saved=json.dumps(row.observation)
        for body in (saved,json.dumps(result)):
            self.assertNotIn(json.dumps(self.row.manifest),body)
            self.assertNotIn('"qualifying_funds":',body);self.assertNotIn('"denominator":',body)
            self.assertNotIn('external_ref',body);self.assertNotIn('customer',body)
        after=self.snapshot()
        # Engineering review audit is the sole intended difference in these apps.
        before.pop('core.Audit',None);after.pop('core.Audit',None)
        self.assertEqual(before,after)
        for action in ('payment.read','finance.read','delivery.read'):
            grant=Grant.objects.get(case=f.case,user=reviewer,action=action)
            grant.active=False;grant.save()
            self.assertNotIn(KEY,dict(choices(reviewer,f.case)))
            for call in (impact.inspect,investigate):
                with self.assertRaises(PermissionDenied):call(reviewer,f.case.pk,row.pk)
            grant.active=True;grant.save()
