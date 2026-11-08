import ast
from pathlib import Path
from unittest import TestCase
ROOT=Path(__file__).resolve().parents[1]
class RecognitionImpactComponentTests(TestCase):
    def test_additive_sql_preserves_previous_guard(self):
        oldtree=ast.parse((ROOT/'apps/policy/migrations/0010_private_impact_contracts.py').read_text())
        old=next(ast.literal_eval(n.args[0]) for n in ast.walk(oldtree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='RunSQL')
        tree=ast.parse((ROOT/'apps/policy/migrations/0021_recognition_policy_impact.py').read_text())
        new=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign))
        self.assertEqual(new.replace(",'finance.recognition_records'",'',1).replace('NOT BETWEEN 1 AND 17','NOT BETWEEN 1 AND 16'),old)
    def test_projection_has_no_intent_or_body_access(self):
        s=(ROOT/'adapters/recognition_policy_impact.py').read_text()
        for forbidden in ['.payload','.operation_key','.body','.create(','event(','bump(']:self.assertNotIn(forbidden,s)
        self.assertIn('record_current(row)',s)
    def test_exact_component_scopes_review_pin(self):
        s=(ROOT/'adapters/policy_impact.py').read_text()
        self.assertIn("config.component=='F33.recognition_review_rules'",s)
        self.assertIn("result=result.filter(kind__in=['attest','review'])",s)
