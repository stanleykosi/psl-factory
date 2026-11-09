"""Exact production entrypoint executed with synthetic dependencies, no ORM/DB/transport."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from django.core.exceptions import ValidationError


class DraftTransactionBoundaryComponentTests(unittest.TestCase):
    def function(self, *, atomic=False, autocommit=True):
        tree = ast.parse((Path(__file__).resolve().parents[1]/'apps/finance/draft_generation.py').read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_once')
        connection = SimpleNamespace(in_atomic_block=atomic, get_autocommit=Mock(return_value=autocommit))
        dependencies = {name:Mock(name=name) for name in ['DraftGeneration','d','require','configured_adapter','claim','observe']}
        env = dict(dependencies, connection=connection, ValidationError=ValidationError)
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<exact draft run_once>', 'exec'), env)
        return env['run_once'], dependencies, env

    def test_outer_transaction_rejected_before_orm_authority_claim_or_adapter(self):
        run, deps, env = self.function(atomic=True)
        with self.assertRaisesMessage(ValidationError, 'outer autocommit boundary'):
            run(object(), 'synthetic-case', 7)
        for dependency in deps.values():self.assertEqual(dependency.mock_calls, [])
        env['connection'].get_autocommit.assert_not_called()

    def test_autocommit_off_rejected_before_orm_authority_claim_or_adapter(self):
        run, deps, env = self.function(autocommit=False)
        with self.assertRaisesMessage(ValidationError, 'outer autocommit boundary'):
            run(object(), 'synthetic-case', 7)
        for dependency in deps.values():self.assertEqual(dependency.mock_calls, [])

    def test_autocommit_path_keeps_claim_before_generate_and_observe(self):
        run, deps, env = self.function()
        events=[]
        class Adapter:
            def generate(self, payload):events.append(('generate',payload));return {'synthetic':'response'}
        adapter=Adapter();env['MockDraftGenerationAdapter']=Adapter
        row=SimpleNamespace(case=SimpleNamespace(synthetic=True))
        deps['DraftGeneration'].objects.select_related.return_value.get.return_value=row
        attempt=SimpleNamespace(action='generate',generation=SimpleNamespace(payload={'synthetic':'intent'}),pk=1,fence='f')
        deps['claim'].side_effect=lambda *args:(events.append(('claim',None)) or attempt)
        deps['observe'].side_effect=lambda *args:(events.append(('observe',args[-1])) or 'observed')
        self.assertEqual(run(object(),'synthetic-case',7,adapter),'observed')
        self.assertEqual([e[0] for e in events],['claim','generate','observe'])

    # unittest.TestCase does not supply Django's assertRaisesMessage.
    def assertRaisesMessage(self, exception, message):
        return self.assertRaisesRegex(exception, message)
