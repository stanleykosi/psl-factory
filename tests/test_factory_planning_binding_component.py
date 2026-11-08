import ast,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sql(prefix):
    tree=ast.parse(next((ROOT/'apps/policy/migrations').glob(prefix+'*.py')).read_text())
    return ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and n.targets[0].id=='SQL'))
class PlanningBindingComponentTests(unittest.TestCase):
    def test_exact_additive_guard(self):
        self.assertEqual(sql('0032'),sql('0031').replace('BETWEEN 1 AND 27','BETWEEN 1 AND 28').replace("'workflows.factory_planning_profiles',","'workflows.factory_planning_profiles','workflows.factory_planning_execution_bindings',"))
    def test_immutable_closed_projection_and_no_commands(self):
        tree=ast.parse((ROOT/'adapters/factory_planning_binding_impact.py').read_text())
        calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(tree) if isinstance(n,ast.Call)}
        self.assertFalse(calls & {'bind','execution_actor','qualified_rule','transport','claim','run_once','adopt_profile'})
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='project')
        self.assertEqual({n.attr for n in ast.walk(fn) if isinstance(n,ast.Attribute)},{'pk','sequence','configuration_id'})
    def test_native_synthetic_fixture_without_worker(self):
        s=(ROOT/'tests/factory_planning_binding804_helpers.py').read_text();tree=ast.parse(s)
        calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(tree) if isinstance(n,ast.Call)}
        self.assertIn('bind',calls);self.assertFalse(calls & {'run_once','run_until_wait','claim','transport','sign_baseline','adopt_signed'})
        self.assertIn("review_role='PM'",s);self.assertIn("if not f['c'].synthetic",s)
        self.assertIn('Starter, source and budget preserved',s)
    def test_reader_and_origin_before_hydration(self):
        s=(ROOT/'adapters/factory_planning_binding_impact.py').read_text()
        self.assertLess(s.index('configuration(actor,config.case_id,config.pk)'),s.index('FactoryExecutionBinding.objects.filter'))
        self.assertIn('configuration(actor,case.pk,row.configuration_id)',s)
        self.assertIn("work__definition=DEFINITION",s)

    def test_failure_and_cursor_coverage_is_explicit(self):
        s=(ROOT/'tests/test_factory_planning_binding_impact.py').read_text()
        self.assertIn('self.assertEqual(business_before,self.facts())',s)
        self.assertIn('self.assertEqual(policy_before',s)
        self.assertIn("token+'tampered'",s)
        self.assertIn("(f['a'],other['c'],other['policy'],KEY,token)",s)
        self.assertIn("self.assertFalse(adapter.query(new,KEY,actor=f['a']).exists())",s)
