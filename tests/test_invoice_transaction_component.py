"""Exact production entrypoint without ORM or transport; no database connection."""
import ast
from pathlib import Path
from types import SimpleNamespace,ModuleType
import unittest
from unittest.mock import Mock,patch
from django.core.exceptions import ValidationError

class InvoiceTransactionComponentTests(unittest.TestCase):
    def invoke(self, *, atomic=False, autocommit=True, adapter_kind='custom'):
        root=Path(__file__).resolve().parents[1]
        node=next(n for n in ast.parse((root/'apps/finance/invoice_delivery.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='run_once')
        class Internal:
            def lookup(self,*args):pass
            def deliver(self,*args):pass
        class Subclass(Internal):pass
        adapter={'custom':SimpleNamespace(lookup=Mock(),deliver=Mock()),'subclass':Subclass(),'internal':Internal(),'default':None}[adapter_kind]
        connection=SimpleNamespace(in_atomic_block=atomic,get_autocommit=Mock(return_value=autocommit))
        claim=Mock(return_value=None)
        scope={'connection':connection,'claim':claim,'ValidationError':ValidationError}
        scope.update(_LOCAL_ADAPTER=Internal,_LOCAL_LOOKUP=Internal.lookup,_LOCAL_DELIVER=Internal.deliver)
        module=ModuleType('adapters.invoices');module.InternalInvoiceAdapter=Internal
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(root/'apps/finance/invoice_delivery.py'),'exec'),scope)
        with patch.dict('sys.modules',{'adapters.invoices':module}):
            if adapter_kind in ['custom','subclass'] and (atomic or not autocommit):
                with self.assertRaisesRegex(ValidationError,'outer autocommit boundary'):scope['run_once'](adapter)
                claim.assert_not_called()
                if atomic:connection.get_autocommit.assert_not_called()
            else:
                self.assertFalse(scope['run_once'](adapter));claim.assert_called_once()

    def test_outer_atomic_rejects_custom_and_subclass_before_claim(self):
        for kind in ['custom','subclass']:self.invoke(atomic=True,adapter_kind=kind)
    def test_autocommit_off_rejects_custom_and_subclass_before_claim(self):
        for kind in ['custom','subclass']:self.invoke(autocommit=False,adapter_kind=kind)
    def test_exact_internal_adapter_preserves_local_atomic_composition(self):
        for kind in ['internal','default']:self.invoke(atomic=True,autocommit=False,adapter_kind=kind)
    def test_external_autocommit_caller_reaches_ordinary_claim(self):
        for kind in ['custom','subclass']:self.invoke(adapter_kind=kind)

    def test_exact_instance_overrides_reject_before_claim(self):
        node=next(n for n in ast.parse((Path(__file__).resolve().parents[1]/'apps/finance/invoice_delivery.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='run_once')
        class Internal:
            def lookup(self,*args):pass
            def deliver(self,*args):pass
        for name in ['lookup','deliver']:
            adapter=Internal();override=Mock();setattr(adapter,name,override)
            claim=Mock()
            scope={'connection':SimpleNamespace(in_atomic_block=True),'claim':claim,'ValidationError':ValidationError}
            scope.update(_LOCAL_ADAPTER=Internal,_LOCAL_LOOKUP=Internal.lookup,_LOCAL_DELIVER=Internal.deliver)
            module=ModuleType('adapters.invoices');module.InternalInvoiceAdapter=Internal
            exec(compile(ast.Module(body=[node],type_ignores=[]),'production-run-once','exec'),scope)
            with patch.dict('sys.modules',{'adapters.invoices':module}),self.assertRaisesRegex(ValidationError,'outer autocommit boundary'):
                scope['run_once'](adapter)
            claim.assert_not_called();override.assert_not_called()

    def test_local_lookup_cannot_replace_pinned_delivery(self):
        node=next(n for n in ast.parse((Path(__file__).resolve().parents[1]/'apps/finance/invoice_delivery.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='run_once')
        hostile=Mock();canonical=Mock()
        class Internal:
            def lookup(self,job):self.deliver=hostile;return None
            def deliver(self,*args):canonical(*args)
        adapter=Internal();job=SimpleNamespace(attempts=1,intent={'identity':{'max_attempts':3}},invoice=SimpleNamespace(case=SimpleNamespace(synthetic=True)))
        manager=Mock();manager.select_related.return_value.get.return_value=job
        scope={'connection':SimpleNamespace(in_atomic_block=True),'claim':Mock(return_value=(1,2)),
            'InvoiceJob':SimpleNamespace(objects=manager),'dispatch_context':Mock(),'finish':Mock(),
            'ValidationError':ValidationError,'PermissionDenied':RuntimeError}
        scope.update(_LOCAL_ADAPTER=Internal,_LOCAL_LOOKUP=Internal.lookup,_LOCAL_DELIVER=Internal.deliver)
        module=ModuleType('adapters.invoices');module.InternalInvoiceAdapter=Internal
        exec(compile(ast.Module(body=[node],type_ignores=[]),'production-run-once','exec'),scope)
        with patch.dict('sys.modules',{'adapters.invoices':module}):self.assertTrue(scope['run_once'](adapter))
        canonical.assert_called_once_with(1,2);hostile.assert_not_called()

    def test_class_overrides_require_autocommit_before_claim(self):
        node=next(n for n in ast.parse((Path(__file__).resolve().parents[1]/'apps/finance/invoice_delivery.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='run_once')
        for name in ['lookup','deliver']:
            class Internal:
                def lookup(self,*args):pass
                def deliver(self,*args):pass
            scope={'_LOCAL_ADAPTER':Internal,'_LOCAL_LOOKUP':Internal.lookup,'_LOCAL_DELIVER':Internal.deliver,
                'connection':SimpleNamespace(in_atomic_block=True),'claim':Mock(),'ValidationError':ValidationError}
            module=ModuleType('adapters.invoices');module.InternalInvoiceAdapter=Internal
            override=Mock();setattr(Internal,name,override)
            exec(compile(ast.Module(body=[node],type_ignores=[]),'production-run-once','exec'),scope)
            with patch.dict('sys.modules',{'adapters.invoices':module}),self.assertRaisesRegex(ValidationError,'outer autocommit boundary'):scope['run_once']()
            scope['claim'].assert_not_called();override.assert_not_called()

    def test_rebound_adapter_class_does_not_gain_local_allowance(self):
        node=next(n for n in ast.parse((Path(__file__).resolve().parents[1]/'apps/finance/invoice_delivery.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='run_once')
        class Internal:
            def lookup(self,*args):pass
            def deliver(self,*args):pass
        class Replacement(Internal):pass
        scope={'_LOCAL_ADAPTER':Internal,'_LOCAL_LOOKUP':Internal.lookup,'_LOCAL_DELIVER':Internal.deliver,
            'connection':SimpleNamespace(in_atomic_block=True),'claim':Mock(),'ValidationError':ValidationError}
        module=ModuleType('adapters.invoices');module.InternalInvoiceAdapter=Replacement
        exec(compile(ast.Module(body=[node],type_ignores=[]),'production-run-once','exec'),scope)
        with patch.dict('sys.modules',{'adapters.invoices':module}),self.assertRaisesRegex(ValidationError,'outer autocommit boundary'):scope['run_once']()
        scope['claim'].assert_not_called()

    def test_autocommit_class_mock_and_lookup_mutation_use_pinned_callable(self):
        node=next(n for n in ast.parse((Path(__file__).resolve().parents[1]/'apps/finance/invoice_delivery.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='run_once')
        class Internal:
            def lookup(self,*args):pass
            def deliver(self,*args):pass
        adapter=Internal();hostile=Mock();delivery=Mock()
        scope={'_LOCAL_ADAPTER':Internal,'_LOCAL_LOOKUP':Internal.lookup,'_LOCAL_DELIVER':Internal.deliver,
            'connection':SimpleNamespace(in_atomic_block=False,get_autocommit=lambda:True),'claim':Mock(return_value=(1,2)),
            'ValidationError':ValidationError,'PermissionDenied':RuntimeError,'dispatch_context':Mock(),'finish':Mock()}
        def mutate(job):adapter.deliver=hostile;return None
        Internal.lookup=Mock(side_effect=mutate);Internal.deliver=delivery
        job=SimpleNamespace(attempts=1,intent={'identity':{'max_attempts':3}},invoice=SimpleNamespace(case=SimpleNamespace(synthetic=True)))
        manager=Mock();manager.select_related.return_value.get.return_value=job;scope['InvoiceJob']=SimpleNamespace(objects=manager)
        module=ModuleType('adapters.invoices');module.InternalInvoiceAdapter=Internal
        exec(compile(ast.Module(body=[node],type_ignores=[]),'production-run-once','exec'),scope)
        with patch.dict('sys.modules',{'adapters.invoices':module}):self.assertTrue(scope['run_once'](adapter))
        delivery.assert_called_once_with(1,2);hostile.assert_not_called()

if __name__=='__main__':unittest.main()
