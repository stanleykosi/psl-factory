"""Exact source extraction: no Django setup, database or provider."""
import ast
from pathlib import Path
from types import SimpleNamespace as N
from unittest import TestCase
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]

class ApprovalGuardComponentTests(TestCase):
    def load(self, original=None, last=None):
        tree=ast.parse((ROOT/'apps/pmo/approval_routing.py').read_text())
        node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='guard_reserve')
        d=Mock();r=N(pk=1);d.exact.return_value=r
        jobs=Mock();jobs.order_by.return_value=jobs;jobs.first.return_value=last
        jobs.filter.return_value.exclude.return_value.order_by.return_value.first.return_value=original
        env={'d':d,'require':Mock(),'intent':Mock(return_value={'safe':True}),
             'ApprovalRouteJob':N(objects=N(filter=Mock(return_value=jobs))),
             'ValidationError':ValueError,'ApprovalRouteReceipt':Mock(),'timezone':Mock()}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<exact-production-guard>','exec'),env)
        return env

    def test_new_request_readonly_generation(self):
        env=self.load();r,v,old,g=env['guard_reserve'](1,N(kind='project'),2)
        self.assertIsNone(old);self.assertEqual(g,1);env['require'].assert_called_once()

    def test_existing_exact_intent_reused(self):
        old=N(intent={'safe':True},status='confirmed');env=self.load(old,N(generation=4))
        result=env['guard_reserve'](1,N(kind='project'),2)
        self.assertIs(result[2],old);self.assertEqual(result[3],5)

    def test_changed_intent_fails_closed(self):
        env=self.load(N(intent={'different':True},status='confirmed'),N(generation=4))
        with self.assertRaises(ValueError):env['guard_reserve'](1,N(kind='project'),2)

    def test_outstanding_job_holds_reminder(self):
        for status in ['pending','unknown','leased','held']:
            env=self.load(last=N(status=status,generation=1))
            with self.assertRaises(ValueError):env['guard_reserve'](1,N(kind='project'),2,'reminder')

    def test_reserve_uses_guard_before_create_and_retains_lock(self):
        tree=ast.parse((ROOT/'apps/pmo/approval_routing.py').read_text())
        node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='reserve')
        text=ast.unparse(node)
        self.assertLess(text.index('d.locked('),text.index('guard_reserve('))
        self.assertLess(text.index('guard_reserve('),text.index('ApprovalRouteJob.objects.create('))
        self.assertIn('if existing:',text);self.assertIn('@transaction.atomic',text)

    def test_migration_preserves_all_prior_sql_bytes(self):
        def sql(n):
            tree=ast.parse((ROOT/'apps/policy/migrations'/n).read_text())
            return ast.literal_eval(next(x.value for x in tree.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SQL' for t in x.targets)))
        old=sql('0017_ledger_review_preview.py');new=sql('0018_approval_route_preview.py')
        start=new.index("  WHEN 'approval.route' THEN");end=new.index("  WHEN 'ledger.review' THEN",start)
        restored=(new[:start]+new[end:]).replace("NOT IN ('approval.route','ledger.review'","NOT IN ('ledger.review'",1)
        self.assertEqual(restored,old)
        block=new[start:end]
        self.assertIn("ARRAY['approval_purpose','approval_request_id','expected_revision']",block)
        self.assertIn('FROM pmo_approvalrequest',block);self.assertIn('IS DISTINCT FROM c.case_id',block)

    def test_registry_schema_and_agent_are_explicit(self):
        registry=ast.parse((ROOT/'adapters/pilot_guards.py').read_text())
        node=next(x for x in registry.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REGISTRY' for t in x.targets))
        keys=[ast.literal_eval(k) for k in node.value.keys]
        self.assertEqual(len(keys),20);self.assertIn('ledger.review',keys);self.assertIn('approval.route',keys)
        self.assertIn("'approval.route':dict(args,approval_request_id=ID,approval_purpose=",(ROOT/'apps/policy/pilot_binding_validators.py').read_text())
        self.assertIn('no job, reminder, delivery or department approval is created',(ROOT/'apps/agents/pilot.py').read_text())

    def test_native_clock_fixture_preserves_receipt_history(self):
        tree=ast.parse((ROOT/'tests/test_approval_route_preview.py').read_text())
        cls=next(x for x in tree.body if isinstance(x,ast.ClassDef))
        method=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='test_receipt_interval_and_budget_are_not_skipped')
        source=ast.unparse(method)
        self.assertNotIn('.update(',source)
        self.assertIn('timedelta(microseconds=1)',source)
        self.assertIn("'Configured reminder budget exhausted'",source)
        self.assertIn('self.assertEqual(receipt.created_at, original_created_at)',source)
        self.assertIn('self.assertEqual(reminder_receipt.created_at, boundary)',source)
