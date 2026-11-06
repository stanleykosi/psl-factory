"""Typed outcome-selection configuration never appoints a relationship owner."""
import json
from pathlib import Path
from types import SimpleNamespace
from django.core.exceptions import ValidationError,PermissionDenied
from django.test import SimpleTestCase,TestCase
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo import rfp
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.rfp_outcome_validators import COMPONENT,SCHEMA,METHOD,validate_reference
from apps.policy.services import reference_values,resolve,transition
from tests.helpers import setup_case


class RFPOutcomePolicyShapeTests(SimpleTestCase):
    def test_nullable_fixture_and_explicit_method_validate_without_implicit_selection(self):
        fixture=json.loads(Path('fixtures/rfp-outcome-reconciliation.json').read_text())
        self.assertIn('synthetic_test_only',fixture.pop('classification'))
        self.assertEqual(fixture,{'method':None})
        for method in [None,METHOD]:
            content={'method':method}
            target=SimpleNamespace(schema_ref=SCHEMA,content=content)
            self.assertEqual(validate_reference(COMPONENT,target,None),content)
            self.assertEqual(validate_reference(COMPONENT,target,None,runtime=True),content)

    def test_closed_schema_rejects_unknown_fields_unrecognised_methods_and_malformed_values(self):
        invalid=[{},None,[],METHOD,{'method':True},{'method':False},{'method':0},{'method':1},
            {'method':''},{'method':'latest_submission_wins'},{'method':[]},{'method':{}},
            {'method':METHOD,'owner_id':1},{'method':None,'precedence':'latest'}]
        for content in invalid:
            with self.subTest(content=content),self.assertRaises(ValidationError):
                validate_reference(COMPONENT,SimpleNamespace(schema_ref=SCHEMA,content=content),None)
        with self.assertRaises(ValidationError):
            validate_reference(COMPONENT,SimpleNamespace(schema_ref=SCHEMA.rsplit('/',1)[0]+'/v2',content={'method':METHOD}),None)


class RFPOutcomePolicyLifecycleTests(TestCase):
    def test_native_draft_validation_keeps_owner_grants_and_authority_unchanged(self):
        actor,case=setup_case(username='rfp-outcome-policy-author')
        evidence=add_evidence(actor,case.pk,'policy_decision','Synthetic interface decision; no relationship owner appointed',
            'synthetic:rfp-outcome-method')
        Grant.objects.filter(case=case,user=actor,action='rfp.outcome').update(active=False)
        grants=list(Grant.objects.filter(case=case).order_by('pk').values_list('pk','user_id','action','active'))
        for method in [None,METHOD]:
            config=draft_operator_policy(actor,case.pk,COMPONENT,{'method':method},evidence.pk,timezone.now())
            self.assertEqual(config.states.latest('pk').state,'draft')
            transition(actor,config.pk,'validated')
            self.assertEqual(config.states.latest('pk').state,'validated')
            self.assertEqual(reference_values(config),[{'method':method}])
            self.assertEqual(resolve(COMPONENT,case).status,'MISSING')
        self.assertEqual(list(Grant.objects.filter(case=case).order_by('pk').values_list('pk','user_id','action','active')),grants)
        self.assertFalse(Grant.objects.filter(case=case,user=actor,action='rfp.outcome',active=True).exists())
        with self.assertRaises((ValidationError,PermissionDenied)):
            rfp.authority(actor,case,'outcome','Client')
