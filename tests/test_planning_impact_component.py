"""Read-only source checks, no PostgreSQL execution."""
import ast
from pathlib import Path
from unittest import TestCase
ROOT=Path(__file__).resolve().parents[1]
class PlanningImpactComponentTests(TestCase):
    def test_additive_sql_preserves_prior_impact_guard(self):
        def sql(name):
            return next(ast.literal_eval(n.value) for n in ast.parse((ROOT/'apps/policy/migrations'/name).read_text()).body if isinstance(n,ast.Assign))
        old=sql('0021_recognition_policy_impact.py');new=sql('0022_planning_readiness_policy_impact.py')
        self.assertEqual(new.replace(",'pmo.planning_readiness'",'',1).replace('NOT BETWEEN 1 AND 18','NOT BETWEEN 1 AND 17'),old)
    def test_bounded_selection_precedes_body_parsing_and_projection(self):
        tree=ast.parse((ROOT/'adapters/planning_policy_impact.py').read_text())
        query=ast.unparse(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='query'))
        self.assertLess(query.index('readable('),query.index('Evidence.objects'))
        self.assertLess(query.index('len(sizes)'),query.index('authorize_row('))
        self.assertIn('MAX_TOTAL_CHARACTERS',query);self.assertIn('MAX_CANDIDATES + 1',query)
        self.assertNotIn('Cast(',query);self.assertNotIn('RawSQL',query)
    def test_projection_is_closed_metadata_and_native_currentness(self):
        tree=ast.parse((ROOT/'adapters/planning_policy_impact.py').read_text())
        text=ast.unparse(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='project'))
        self.assertIn('planning.current_readiness',text)
        for forbidden in ['planning.prepare(','.body','.create(','event(','bump(']:self.assertNotIn(forbidden,text)
    def test_observer_required_in_both_shared_selection_paths(self):
        s=(ROOT/'apps/policy/impact.py').read_text()
        self.assertIn('adapter.query(config,key,actor=actor)',s)
        self.assertIn('adapter.query(previous,key,actor=actor)',s)
