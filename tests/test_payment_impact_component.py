"""DB-free contract/source checks; native definitions are separately UNRUN."""
import ast
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
def sql(number):
    tree=ast.parse(next((ROOT/'apps/policy/migrations').glob(number+'*.py')).read_text())
    return ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and n.targets[0].id=='SQL'))
class PaymentImpactComponentTests(unittest.TestCase):
    def test_exact_additive_guard(self):
        expected=sql('0023').replace('BETWEEN 1 AND 19','BETWEEN 1 AND 20').replace("'pmo.planning_comparisons',","'pmo.planning_comparisons','finance.payment_assessments',")
        self.assertEqual(sql('0024'),expected)
    def test_closed_read_only_native_path(self):
        tree=ast.parse((ROOT/'adapters/payment_policy_impact.py').read_text())
        calls={ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n,ast.Call)}
        self.assertIn('assessment_current',calls)
        self.assertFalse(calls & {'assess','reserve','decide','revalidate','combined','usable'})
        source=ast.unparse(tree)
        self.assertIn('config.component not in COMPONENTS',source)
        self.assertIn("'manifest__policies__' + config.component + '__id'",source)
    def test_fixture_explicitly_local(self):
        import json
        self.assertEqual(json.loads((ROOT/'fixtures/finance-settlement.json').read_text())['adapter']['implementation'],'internal_invoice_register_v1')
        self.assertIn('adapter=adapter or _LOCAL_ADAPTER()', (ROOT/'apps/finance/invoice_delivery.py').read_text())

        dedicated=(ROOT/'tests/payment_impact795_helpers.py').read_text()
        self.assertIn('from .obligation_helpers import issue_identified as issue',dedicated)
        legacy=(ROOT/'tests/payment_helpers.py').read_text()
        self.assertNotIn('obligation_helpers',legacy)
        self.assertIn('from .settlement_helpers import configured,draft,issue,receipt,assign,allocate',legacy)
        helper=(ROOT/'tests/obligation_helpers.py').read_text().split('def issue_identified(',1)[1].split('def factory_',1)[0]
        self.assertLess(helper.index('identified(actor, case, invoice)'),helper.index('return issue(actor, case, invoice, proofs)'))
        for relative in ('tests/test_payment_policy_impact.py','scripts/impact795c_compatibility.py'):
            self.assertIn('from tests.payment_impact795_helpers import fixture',(ROOT/relative).read_text())

        self.assertNotIn('human(',dedicated)
        self.assertNotIn('f.ready()',dedicated)
        self.assertIn('assert_predeployment_fixture(f)',dedicated)
        self.assertIn('component__in=[ROLE,PEOPLE,DELEGATION,VALIDITY]',dedicated)
        self.assertIn('DeliveryRecord.objects.filter(dossier=f.d).exists()',dedicated)
        self.assertNotIn('.approver',(ROOT/'tests/test_payment_policy_impact.py').read_text())
