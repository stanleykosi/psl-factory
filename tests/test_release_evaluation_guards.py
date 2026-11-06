"""Native financial/delivery calculations without human decisions or release effects."""
import json
from copy import deepcopy
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,DatabaseError
from django.test import TestCase,Client
from django.urls import reverse
from apps.core.models import Audit
from apps.identity.models import Grant
from apps.finance import payments
from apps.finance.models import PaymentAssessment,PaymentDecision,PaymentReleaseReservation
from apps.pmo.delivery_closure import evaluate_hypercare
from apps.pmo.models import DeliveryRecord
from apps.policy import pilot,pilot_bindings,pilot_binding_validators
from apps.policy.models import PilotBinding
from apps.policy.services import transition
from apps.policy.payment_validators import DENOMINATOR,FUNDS
from adapters import pilot_guards
from tests.helpers import rev,setup_case
from tests.test_pilot_preflight import selection
from tests.test_document_guard import payload as document_payload
from tests.payment_helpers import fixture,configure
from tests.test_delivery import DeliveryFixture


def selected(a,c,op,**args):
    return {'operation':op,'user_id':a.pk,'arguments':dict(expected_revision=rev(c),**args)}


def contract_payload(a,c,g):
    p=selection(a,c);p['operations']=[g['operation']];contract=pilot.configure(a,c.pk,p)
    v=document_payload(a,c,type('Subject',(),{'pk':1})());v['guards']=[g]
    return contract,v


class PaymentGuardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        f=fixture()
        for k,v in f.__dict__.items():setattr(cls,k,v)

    def g(self):return selected(self.actor,self.case,'payment.assess',dossier_id=self.d.pk,coverage_id=self.cov.pk)

    def test_unknown_basis_is_recordable_unknown_and_does_not_approve_exception_or_release(self):
        before=(Audit.objects.count(),PaymentAssessment.objects.count(),PaymentDecision.objects.count(),PaymentReleaseReservation.objects.count(),rev(self.case))
        result=pilot_guards.check(self.actor,self.case,self.g())
        self.assertEqual(result['state'],'READY_AT_OBSERVATION')
        self.assertEqual(result['evaluation']['status'],'UNKNOWN')
        self.assertFalse(result['evaluation']['business_approval']);self.assertFalse(result['evaluation']['deployment_authorized'])
        self.assertEqual(before,(Audit.objects.count(),PaymentAssessment.objects.count(),PaymentDecision.objects.count(),PaymentReleaseReservation.objects.count(),rev(self.case)))
        actual=payments.assess(self.actor,self.case.pk,self.d.pk,self.cov.pk,rev(self.case))
        self.assertEqual(actual.result['status'],result['evaluation']['status'])
        self.assertIsNone(actual.result['denominator'])

    def test_actual_configured_assessment_matches_preview_but_amounts_stay_private(self):
        configure(self.actor,self.case,self.cov,self.approver,components=[DENOMINATOR,FUNDS])
        result=pilot_guards.check(self.actor,self.case,self.g())
        self.assertEqual(result['state'],'READY_AT_OBSERVATION')
        self.assertEqual(result['evaluation']['status'],'BELOW_EXPECTATION')
        for key in ['denominator','qualifying_funds','open_debt','percentage']:self.assertNotIn(key,json.dumps(result))
        actual=payments.assess(self.actor,self.case.pk,self.d.pk,self.cov.pk,rev(self.case))
        self.assertEqual(actual.result['status'],result['evaluation']['status']);self.assertEqual(Decimal(actual.result['denominator']),Decimal('32.25'))
        self.assertFalse(PaymentDecision.objects.exists());self.assertFalse(PaymentReleaseReservation.objects.exists())
        Grant.objects.filter(user=self.actor,case=self.case,action='payment.assess').update(active=False)
        self.assertEqual(pilot_guards.check(self.actor,self.case,self.g())['findings'],[{'code':'native_authority_denied'}])
        with self.assertRaises(PermissionDenied):payments.assess(self.actor,self.case.pk,self.d.pk,self.cov.pk,rev(self.case))

    def test_ui_review_agent_and_policy_successor_invalidate_without_business_effect(self):
        from apps.agents.pilot import investigate
        configure(self.actor,self.case,self.cov,self.approver,components=[DENOMINATOR,FUNDS])
        contract,value=contract_payload(self.actor,self.case,self.g());d=value['deployment']
        client=Client(enforce_csrf_checks=True);client.force_login(self.actor)
        url=reverse('pilot_bindings',args=[self.case.pk,contract.pk]);self.assertContains(client.get(url),'Exact billing coverage')
        self.assertEqual(client.post(url,{}).status_code,403)
        response=client.post(url,dict(operation='payment.assess',participant=self.actor.pk,expected_revision=rev(self.case),dossier_id=self.d.pk,coverage_id=self.cov.pk,
            deployment_ref=d['ref'],revision=d['revision'],web_key_ref=d['web_key_ref'],worker_key_ref=d['worker_key_ref'],families=d['families'],freshness_seconds=d['freshness_seconds'],
            csrfmiddlewaretoken=client.cookies['csrftoken'].value,**d['expected']))
        self.assertEqual(response.status_code,302);binding=PilotBinding.objects.get()
        reviewer=get_user_model().objects.create_user(username='assessment-reviewer')
        Grant.objects.bulk_create([Grant(user=reviewer,case=self.case,action=k) for k in Grant.objects.filter(user=self.actor,case=self.case).values_list('action',flat=True)])
        pilot_bindings.review(reviewer,self.case.pk,binding.pk,'accept','Native assessment evidence only')
        pack=pilot.capture(self.actor,self.case.pk,contract.pk);self.assertTrue(pilot.inspect(self.actor,self.case.pk,pack.pk)['current'])
        report=investigate(self.actor,self.case.pk,pack.pk)
        self.assertTrue(any('Payment assessment preview only: BELOW_EXPECTATION' in x for x in report['findings']))
        self.assertEqual(report['effect_tools'],[]);self.assertFalse(PaymentAssessment.objects.exists())
        configure(self.actor,self.case,self.cov,self.approver,components=[DENOMINATOR])
        self.assertFalse(pilot.inspect(self.actor,self.case.pk,pack.pk)['current'])

    def test_current_observer_access_precedes_lookup_and_closed_sql_has_valid_control(self):
        from tests.billing_helpers import coverage
        other,foreign=setup_case(username='other-payment-coverage');foreign_cov=coverage(other,foreign)
        contract,value=contract_payload(self.actor,self.case,self.g());binding=pilot_bindings.configure(self.actor,self.case.pk,contract.pk,value)
        for wrong in [foreign_cov.pk,True,float(self.cov.pk)]:
            bad=deepcopy(value);bad['guards'][0]['arguments']['coverage_id']=wrong
            with self.assertRaises(ValidationError):pilot_binding_validators.validate(contract,bad)
            successor=pilot.configure(self.actor,self.case.pk,dict(contract.payload),contract.pk)
            fields={f.name:getattr(binding,f.name) for f in binding._meta.fields if f.name not in ['id','created_at','contract','payload']}
            with self.assertRaisesMessage(DatabaseError,'PSL'),transaction.atomic():PilotBinding.objects.create(contract=successor,payload=bad,**fields)
            PilotBinding.objects.create(contract=successor,payload=value,**fields);contract=successor
        Grant.objects.filter(user=self.actor,case=self.case,action='payment.read').update(active=False)
        for pk in [self.d.pk,999999999]:
            g=self.g();g['arguments']['dossier_id']=pk
            with self.assertRaises(PermissionDenied):pilot_guards.check(self.actor,self.case,g)


class HypercareGuardTests(DeliveryFixture,TestCase):
    @classmethod
    def setUpTestData(cls):
        f=DeliveryFixture();f.setup_delivery();f.accepted();f.criteria();f.observations()
        for k,v in f.__dict__.items():setattr(cls,k,v)

    def g(self):return selected(self.actor,self.case,'hypercare.evaluate',dossier_id=self.d.pk)

    def test_actual_evaluation_matches_native_preview_without_closure_or_deployment(self):
        before=(Audit.objects.count(),DeliveryRecord.objects.count(),rev(self.case))
        result=pilot_guards.check(self.actor,self.case,self.g());self.assertEqual(result['state'],'READY_AT_OBSERVATION')
        self.assertIs(result['evaluation']['qualified'],True)
        self.assertFalse(result['evaluation']['closure_authorized']);self.assertFalse(result['evaluation']['deployment_authorized'])
        self.assertEqual(before,(Audit.objects.count(),DeliveryRecord.objects.count(),rev(self.case)))
        actual=evaluate_hypercare(self.actor,self.case.pk,self.d.pk,self.e['requirements'].pk,'Human records evaluation',rev(self.case))
        self.assertEqual(actual.snapshot['qualified'],result['evaluation']['qualified'])
        self.assertFalse(self.d.records.filter(kind='closure').exists())

    def test_unknown_failed_qualified_and_revoked_criteria_are_distinct(self):
        self.observations(errors=None)
        self.assertIsNone(pilot_guards.check(self.actor,self.case,self.g())['evaluation']['qualified'])
        self.observations(errors=2)
        self.assertIs(pilot_guards.check(self.actor,self.case,self.g())['evaluation']['qualified'],False)
        config=self.criteria();self.observations()
        self.assertIs(pilot_guards.check(self.actor,self.case,self.g())['evaluation']['qualified'],True)
        transition(self.actor,config.pk,'revoked')
        self.assertEqual(pilot_guards.check(self.actor,self.case,self.g())['state'],'HELD')
        self.assertFalse(self.d.records.filter(kind='hypercare').exists())

    def test_review_access_cannot_replace_native_manage_grant_and_stale_revisions_hold(self):
        g=self.g();g['arguments']['expected_revision']-=1
        self.assertEqual(pilot_guards.check(self.actor,self.case,g)['state'],'HELD')
        Grant.objects.filter(user=self.actor,case=self.case,action='delivery.manage').update(active=False)
        self.assertEqual(pilot_guards.check(self.actor,self.case,self.g())['findings'],[{'code':'native_authority_denied'}])
        Grant.objects.filter(user=self.actor,case=self.case,action='delivery.read').update(active=False)
        for pk in [self.d.pk,999999999]:
            g=self.g();g['arguments']['dossier_id']=pk
            with self.assertRaises(PermissionDenied):pilot_guards.check(self.actor,self.case,g)

    def test_reviewed_hypercare_pack_and_agent_never_close_and_source_revision_stales(self):
        from apps.agents.pilot import investigate
        contract,value=contract_payload(self.actor,self.case,self.g())
        binding=pilot_bindings.configure(self.actor,self.case.pk,contract.pk,value)
        reviewer=get_user_model().objects.create_user(username='hypercare-evidence-reviewer')
        Grant.objects.bulk_create([Grant(user=reviewer,case=self.case,action=k) for k in Grant.objects.filter(user=self.actor,case=self.case).values_list('action',flat=True)])
        pilot_bindings.review(reviewer,self.case.pk,binding.pk,'accept','Criteria evidence only; independent closure remains required')
        pack=pilot.capture(self.actor,self.case.pk,contract.pk);self.assertTrue(pilot.inspect(self.actor,self.case.pk,pack.pk)['current'])
        report=investigate(self.actor,self.case.pk,pack.pk)
        self.assertTrue(any('Hypercare evaluation preview only' in x for x in report['findings']))
        self.assertEqual(report['effect_tools'],[])
        self.assertFalse(self.d.records.filter(kind__in=['hypercare','closure']).exists())
        self.observations(errors=2)
        self.assertFalse(pilot.inspect(self.actor,self.case.pk,pack.pk)['current'])

    def test_foreign_dossier_binding_rejected_by_validator_and_sql_with_valid_control(self):
        from tests.helpers import prepared
        from apps.pmo.gates import register_candidate
        from apps.pmo.delivery import open_dossier
        other,foreign=setup_case(username='foreign-hypercare-dossier');ev=prepared(other,foreign)
        candidate=register_candidate(other,foreign.pk,'foreign-release',ev['requirements'].pk,rev(foreign))
        dossier=open_dossier(other,foreign.pk,candidate.pk,ev['plan'].pk,'Foreign dossier source',rev(foreign))
        contract,value=contract_payload(self.actor,self.case,self.g());binding=pilot_bindings.configure(self.actor,self.case.pk,contract.pk,value)
        bad=deepcopy(value);bad['guards'][0]['arguments']['dossier_id']=dossier.pk
        with self.assertRaises(ValidationError):pilot_binding_validators.validate(contract,bad)
        successor=pilot.configure(self.actor,self.case.pk,dict(contract.payload),contract.pk)
        fields={f.name:getattr(binding,f.name) for f in binding._meta.fields if f.name not in ['id','created_at','contract','payload']}
        with self.assertRaisesMessage(DatabaseError,'PSL'),transaction.atomic():PilotBinding.objects.create(contract=successor,payload=bad,**fields)
        PilotBinding.objects.create(contract=successor,payload=value,**fields)
