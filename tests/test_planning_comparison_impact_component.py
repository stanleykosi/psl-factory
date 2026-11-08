import ast
from pathlib import Path
from unittest import TestCase
ROOT=Path(__file__).resolve().parents[1]
class ComparisonImpactComponentTests(TestCase):
    def test_sql_preserves_exact_previous_variants(self):
        def sql(name):return next(ast.literal_eval(n.value) for n in ast.parse((ROOT/'apps/policy/migrations'/name).read_text()).body if isinstance(n,ast.Assign))
        old=sql('0022_planning_readiness_policy_impact.py');new=sql('0023_planning_comparison_policy_impact.py')
        self.assertEqual(new.replace(",'pmo.planning_comparisons'",'',1).replace('NOT BETWEEN 1 AND 19','NOT BETWEEN 1 AND 18'),old)
    def test_currentness_uses_native_identity_not_only_success(self):
        s=(ROOT/'adapters/planning_comparison_impact.py').read_text();self.assertIn('planning.comparison_context(row.case,packet,config,rules)==row.pk',s)
        self.assertIn("config.component not in [COMPONENT,AUTHORITY]",s)
        for grant in ['commercial.read','document.read']:self.assertIn(grant,s)
    def test_projection_has_no_private_body_or_effect(self):
        t=ast.parse((ROOT/'adapters/planning_comparison_impact.py').read_text());s=ast.unparse(next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='project'))
        for forbidden in ['.body','.create(','.save(','event(','bump(']:self.assertNotIn(forbidden,s)
        for field in ['business_approval','contract_renewed','effects_performed']:self.assertIn(field,s)
