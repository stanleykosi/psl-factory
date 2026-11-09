import ast
from pathlib import Path
import unittest
from unittest.mock import Mock
ROOT=Path(__file__).resolve().parents[1]

class PlanningPreviewComponentTests(unittest.TestCase):
    def test_native_mutation_remains_locked_and_guard_is_write_free(self):
        tree=ast.parse((ROOT/'apps/pmo/planning.py').read_text())
        guard=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='guard_prepare')
        calls=[ast.unparse(n.func) for n in ast.walk(guard) if isinstance(n,ast.Call)]
        self.assertNotIn('write',calls);self.assertNotIn('event',calls)
        native=ast.unparse(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='prepare'))
        self.assertLess(native.index('locked('),native.index('guard_prepare('));self.assertIn("return old or write(a, c, 'ready', value)",native)

    def test_observer_access_precedes_lookup_and_checks_all_source_grants(self):
        tree=ast.parse((ROOT/'adapters/planning_readiness_guard.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='readable')
        body=ast.unparse(fn)
        self.assertLess(body.index('planning.readable'),body.index('Evidence.objects.filter'))
        self.assertLess(body.index('approvals.readable'),body.index('Evidence.objects.filter'))
        self.assertIn("'approval.source.read:' + receipt.system",body)
        self.assertNotIn('current_request(',body)

    def test_binding_is_ids_only(self):
        source=(ROOT/'apps/policy/pilot_binding_validators.py').read_text()
        self.assertIn("'planning.readiness':dict(args,planning_packet_id=ID)",source)
        self.assertNotIn('recognition.attest',source)

    def test_replay_branch_keeps_original_current_readiness_check(self):
        s=(ROOT/'apps/pmo/planning.py').read_text();tree=ast.parse(s)
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='guard_prepare')
        text=ast.unparse(fn)
        self.assertIn("current_readiness(c, old.pk)['packet_id'] == e.pk",text)
        self.assertIn('return (e, None, old)',text)
        self.assertLess(text.index('requests(c, e, a)'),text.index('current_readiness('))

    def test_sql_addition_preserves_predecessor_body(self):
        def sql(name):
            tree=ast.parse((ROOT/'apps/policy/migrations'/name).read_text())
            return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SQL' for t in n.targets))
        old=sql('0018_approval_route_preview.py');new=sql('0019_planning_readiness_preview.py')
        start=new.index("  WHEN 'planning.readiness' THEN");end=new.index("  WHEN 'approval.route' THEN",start)
        self.assertEqual(new[:start]+new[end:],old.replace("NOT IN ('approval.route'","NOT IN ('planning.readiness','approval.route'",1))
