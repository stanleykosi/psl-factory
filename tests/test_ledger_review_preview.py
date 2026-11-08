"""Synthetic native F01 preview boundaries. Native runtime NOT RUN until cleared."""
import json
from copy import deepcopy
from unittest.mock import patch
from django.test import TestCase,Client
from django.urls import reverse
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,DatabaseError
from apps.core.models import Audit,Evidence
from apps.identity.models import Grant
from apps.finance import ledger
from apps.finance.models import LedgerDecision,InvoiceJob
from apps.policy import pilot,pilot_bindings,pilot_binding_validators
from apps.policy.models import PilotBinding
from apps.policy.pilot_binding_views import BindingForm
from adapters import pilot_guards
from tests.ledger_helpers import fixture,capture,verify,policy
from tests.helpers import rev,setup_case
from tests.test_pilot_preflight import selection
from tests.test_document_guard import payload as document_payload

class LedgerReviewPreviewTests(TestCase):
    def setUp(self):
        self.f=fixture();self.a=self.f['actor'];self.b=self.f['reviewer'];self.c=self.f['case']
        self.w=capture(self.f);self.x=verify(self.f,self.w);self.e=self.f['e']
    def g(self,verdict='approve',**changes):
        value={'operation':'ledger.review','user_id':self.b.pk,'arguments':{'expected_revision':rev(self.c),'ledger_check_id':self.x.pk,'ledger_review_evidence_id':self.e.pk,'ledger_verdict':verdict}}
        value['arguments'].update(changes);return value
    def check(self,g=None,observer=None):return pilot_guards.check(observer or self.a,self.c,g or self.g())
    def state(self):return LedgerDecision.objects.count(),Audit.objects.count(),InvoiceJob.objects.count(),rev(self.c)
    def contract(self,g=None):
        g=g or self.g();p=selection(self.a,self.c);p['operations']=['ledger.review'];p['participants']=[{'user_id':self.b.pk,'actions':['ledger.review']}]
        contract=pilot.configure(self.a,self.c.pk,p)
        value=document_payload(self.a,self.c,type('Subject',(),{'pk':1})());value['guards']=[g]
        return contract,value
    def test_shared_ready_preview_is_read_only_and_native_review_creates_only_decision(self):
        before=self.state();result=self.check();self.assertEqual(result['state'],'READY_AT_OBSERVATION');self.assertEqual(before,self.state())
        self.assertFalse(result['business_approval']);self.assertFalse(result['effects_scheduled'])
        for secret in [self.w.payload['source_reference'],self.w.payload['realm'],self.e.body]:self.assertNotIn(secret,json.dumps(result))
        r=ledger.review(self.b,self.c.pk,self.x.pk,self.e.pk,'approve',rev(self.c));self.assertEqual(r.verification_id,self.x.pk);self.assertEqual(LedgerDecision.objects.count(),1)
    def test_observer_revocation_denies_before_subject_lookup(self):
        Grant.objects.filter(case=self.c,user=self.a,action='ledger.read').update(active=False)
        with patch.object(ledger.LedgerCheck.objects,'filter',side_effect=AssertionError('subject lookup forbidden')):
            with self.assertRaises(PermissionDenied):self.check()
    def test_independent_reviewer_and_actor_revocation_match_native(self):
        g=self.g();g['user_id']=self.a.pk
        self.assertEqual(self.check(g)['findings'],[{'code':'native_authority_denied'}])
        with self.assertRaises(PermissionDenied):ledger.review(self.a,self.c.pk,self.x.pk,self.e.pk,'approve',rev(self.c))
        Grant.objects.filter(case=self.c,user=self.b,action='ledger.review').update(active=False)
        self.assertEqual(self.check()['findings'],[{'code':'native_authority_denied'}])
    def test_expired_approval_holds_but_rejection_preserves_native_semantics(self):
        from datetime import timedelta
        from django.utils import timezone
        with patch('apps.finance.ledger.timezone.now',return_value=timezone.now()+timedelta(days=2)):
            self.assertEqual(self.check()['state'],'HELD')
            self.assertEqual(self.check(self.g('reject'))['state'],'READY_AT_OBSERVATION')
            with self.assertRaises(ValidationError):ledger.review(self.b,self.c.pk,self.x.pk,self.e.pk,'approve',rev(self.c))
            r=ledger.review(self.b,self.c.pk,self.x.pk,self.e.pk,'reject',rev(self.c));self.assertEqual(r.verdict,'reject')
    def test_new_check_and_policy_change_invalidate_observed_approval(self):
        first=self.check();verify(self.f,self.w)
        self.assertEqual(self.check()['state'],'HELD');self.assertNotEqual(first['head'],self.check()['head'])
        from apps.policy.ledger_validators import AUTH
        policy(self.f,AUTH,dict(self.f['v']['authority'],user_ids=[self.a.pk]))
        self.assertEqual(self.check()['findings'],[{'code':'native_authority_denied'}])
    def test_duplicate_source_holds_approval_but_allows_reject(self):
        capture(self.f)
        self.assertEqual(self.check()['state'],'HELD')
        self.assertEqual(self.check(self.g('reject'))['state'],'READY_AT_OBSERVATION')
    def test_foreign_case_and_private_review_evidence_never_leak(self):
        foreign=fixture(username='other-ledger',reviewer_username='other-reviewer');w=capture(foreign);x=verify(foreign,w)
        self.assertEqual(self.check(self.g(ledger_check_id=x.pk))['state'],'HELD')
        self.assertIsNone(self.check(self.g(ledger_check_id=x.pk))['head']['ledger_review'])
        with self.assertRaises(PermissionDenied):self.check(self.g(ledger_review_evidence_id=foreign['e'].pk))
        with self.assertRaises(PermissionDenied):self.check(self.g(ledger_review_evidence_id=self.w.evidence_id))
    def test_binding_form_agent_projection_and_sql_types(self):
        contract,value=self.contract();pilot_binding_validators.validate(contract,value)
        binding=pilot_bindings.configure(self.a,self.c.pk,contract.pk,value)
        self.assertEqual(binding.payload['guards'][0]['operation'],'ledger.review')
        form=BindingForm(self.a,contract);self.assertEqual(form.fields['ledger_check_id'].label_from_instance(self.x),'#'+str(self.x.pk))
        self.assertNotIn(self.w.evidence_id,list(form.fields['ledger_review_evidence_id'].queryset.values_list('pk',flat=True)))
        from apps.agents.pilot import investigate
        observation=pilot.capture(self.a,self.c.pk,contract.pk)
        result=investigate(self.a,self.c.pk,observation.pk)
        self.assertNotIn(self.w.payload['source_reference'],json.dumps(result,default=str))
        for key,bad in [('ledger_check_id',True),('ledger_review_evidence_id',1.5),('ledger_verdict','release')]:
            raw=deepcopy(value);raw['guards'][0]['arguments'][key]=bad
            with self.assertRaises(ValidationError):pilot_binding_validators.validate(contract,raw)
            with self.assertRaises(DatabaseError),transaction.atomic():PilotBinding.objects.create(contract=contract,actor=self.a,payload=raw,sha256='a'*64)
    def test_http_csrf_and_observer_revoked_choices(self):
        contract,value=self.contract();client=Client(enforce_csrf_checks=True);client.force_login(self.a)
        url=reverse('pilot_bindings',args=[self.c.pk,contract.pk])
        self.assertEqual(client.post(url,{}).status_code,403)
        Grant.objects.filter(case=self.c,user=self.a,action='ledger.read').update(active=False)
        form=BindingForm(self.a,contract)
        self.assertFalse(form.fields['ledger_check_id'].queryset.exists());self.assertFalse(form.fields['ledger_review_evidence_id'].queryset.exists())
        with self.assertRaises(PermissionDenied):pilot_bindings.configure(self.a,self.c.pk,contract.pk,value)

    def test_cross_tenant_subject_is_held_even_with_grants_on_both_cases(self):
        from apps.core.models import Case
        from apps.core.services import add_evidence
        from apps.core.management.commands.seed_demo import ACTIONS
        other=Case.objects.create(tenant='separate-synthetic-tenant',title='Other tenant',kind='project',synthetic=True)
        for actor in [self.a,self.b]:
            for action in ACTIONS:Grant.objects.create(case=other,user=actor,action=action)
        evidence=add_evidence(self.a,other.pk,'policy_decision','Synthetic separate tenant review','synthetic:other')
        g=self.g(ledger_review_evidence_id=evidence.pk,expected_revision=rev(other))
        result=pilot_guards.check(self.a,other,g)
        self.assertEqual(result['state'],'HELD');self.assertIsNone(result['head']['ledger_review'])
        self.assertFalse(LedgerDecision.objects.exists())

    def test_sql_missing_null_and_foreign_subjects_fail_closed(self):
        contract,value=self.contract()
        foreign=fixture(username='sql-foreign-ledger',reviewer_username='sql-foreign-reviewer')
        other=verify(foreign,capture(foreign))
        variants=[]
        for key in ['ledger_check_id','ledger_review_evidence_id','ledger_verdict','expected_revision']:
            missing=deepcopy(value);missing['guards'][0]['arguments'].pop(key);variants.append(missing)
            null=deepcopy(value);null['guards'][0]['arguments'][key]=None;variants.append(null)
        for key,value_id in [('ledger_check_id',other.pk),('ledger_review_evidence_id',foreign['e'].pk)]:
            wrong=deepcopy(value);wrong['guards'][0]['arguments'][key]=value_id;variants.append(wrong)
        for raw in variants:
            with self.assertRaises(DatabaseError),transaction.atomic():
                PilotBinding.objects.create(contract=contract,actor=self.a,payload=raw,sha256='a'*64)
        self.assertFalse(PilotBinding.objects.filter(contract=contract).exists())
