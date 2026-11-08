"""Pure exact shared-guard and closed schema tests. No database required."""
import ast,importlib.util,json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from django.core.exceptions import ValidationError
ROOT=Path(__file__).resolve().parents[1]
class LedgerReviewPreviewComponentTests(unittest.TestCase):
    def guard(self,verdict):
        node=next(x for x in ast.parse((ROOT/'apps/finance/ledger.py').read_text()).body if isinstance(x,ast.FunctionDef) and x.name=='guard_review')
        x=object();manager=Mock();manager.filter.return_value.first.return_value=x
        scope={'readable':Mock(),'require':Mock(),'LedgerCheck':SimpleNamespace(objects=manager),'authority':Mock(return_value={'a':1}),'current':Mock(),'subject':Mock(return_value='proof'),'ValidationError':ValidationError}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'shared-native-guard','exec'),scope)
        result=scope['guard_review']('actor','case',1,2,verdict);return result,scope
    def test_approve_uses_exact_native_currentness(self):
        value,s=self.guard('approve');s['current'].assert_called_once_with(value[0]);self.assertEqual(value[1:],({'a':1},'proof'))
    def test_reject_does_not_invent_freshness_requirement(self):
        value,s=self.guard('reject');s['current'].assert_not_called();s['authority'].assert_called_once()
    def test_native_review_reuses_guard_after_existing_locks(self):
        tree=ast.parse((ROOT/'apps/finance/ledger.py').read_text());n=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='review');s=ast.unparse(n)
        self.assertLess(s.index('identity_lock('),s.index('guard_review('));self.assertLess(s.index('target_lock('),s.index('guard_review('));self.assertLess(s.index('guard_review('),s.index('LedgerDecision.objects.create'))
    def test_observer_access_precedes_evidence_lookup(self):
        s=(ROOT/'adapters/ledger_review_guard.py').read_text();tree=ast.parse(s);n=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='readable');calls=[ast.unparse(x) for x in n.body];self.assertIn('ledger.readable',calls[0]);self.assertIn('public_evidence',calls[1])
    def test_migration_preserves_old_function_except_additive_variant(self):
        def sql(name):
            t=ast.parse((ROOT/'apps/policy/migrations'/name).read_text())
            if name.startswith('0017'):return next(ast.literal_eval(n.value) for n in t.body if isinstance(n,ast.Assign) and n.targets[0].id=='SQL')
            return next(n.args[0].value for n in ast.walk(t) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='RunSQL')
        old=sql('0016_cash_operation_identity.py');new=sql('0017_ledger_review_preview.py');start=new.index("  WHEN 'ledger.review' THEN");end=new.index("  WHEN 'receipt.verify' THEN",start);self.assertEqual(new[:start]+new[end:],old.replace("NOT IN ('receipt.verify'","NOT IN ('ledger.review','receipt.verify'",1))
