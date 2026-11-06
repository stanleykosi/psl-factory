"""Recovery policy interfaces distinguish explicit unknowns from invalid authority."""
import copy,json
from pathlib import Path
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition,reference_values
from apps.policy.factory_recovery_validators import COMPONENT
from apps.core.services import add_evidence
from tests.helpers import setup_case

class FactoryRecoveryPolicyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor,cls.case=setup_case(username='recovery-policy-owner')
        cls.proof=add_evidence(cls.actor,cls.case.pk,'policy_decision','Synthetic recovery interface decision only','synthetic:recovery-policy')
        cls.value={'rules':json.loads(Path('fixtures/factory-recovery-authority.json').read_text())['rules']}

    def draft(self,value):return draft_operator_policy(self.actor,self.case.pk,COMPONENT,value,self.proof.pk,timezone.now())

    def test_unknown_settings_have_native_lifecycle_without_appointing_anyone(self):
        policy=self.draft(self.value);transition(self.actor,policy.pk,'validated');transition(self.actor,policy.pk,'active')
        value=reference_values(policy)[0]
        for key in ['method','principal_id','reviewer_id','review_role','independent_of_worker','valid_from','valid_until']:
            self.assertIsNone(value['rules'][0][key])

    def test_ambiguous_rules_timezone_and_unqualified_nominees_are_rejected(self):
        variants=[]
        v=copy.deepcopy(self.value);v['rules'].append(copy.deepcopy(v['rules'][0]));variants.append(v)
        for changes in [dict(valid_from='2026-11-04T00:00:00'),dict(valid_from='2026-11-05T00:00:00Z',valid_until='2026-11-04T00:00:00Z'),
                dict(principal_id=999999),dict(principal_id=True),dict(principal_id=self.actor.pk,reviewer_id=self.actor.pk,independent_of_worker=True)]:
            v=copy.deepcopy(self.value);v['rules'][0].update(changes);variants.append(v)
        for value in variants:
            with self.subTest(value=value):
                policy=self.draft(value)
                with self.assertRaises(ValidationError):transition(self.actor,policy.pk,'validated')
