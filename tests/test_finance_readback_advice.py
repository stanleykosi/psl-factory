from django.test import SimpleTestCase
from apps.agents.finance_readback import recommendations

class FinanceReadbackAdviceTests(SimpleTestCase):
    def test_stale_current_capture_is_described_as_history(self):
        # The real domain report can retain a recorded current verdict after source revocation.
        report={'recorded':{'outcome':'acknowledged','disposition':'current','hold_code':None},'observation_current':False,'holds':['Current source review required']}
        text=' '.join(recommendations(report))
        self.assertIn('historical',text)
        self.assertNotIn('Current source authority verified',text)
        self.assertIn('neither prove a financial receipt nor authorise execution',text)
    def test_unknown_is_not_a_failed_effect_and_current_is_not_execution(self):
        report={'recorded':{'outcome':'unknown','disposition':'absent','hold_code':'request_not_observed'},'observation_current':True,'holds':[]}
        self.assertIn('absence is not proof of a failed financial effect',' '.join(recommendations(report)))
        report['recorded']={'outcome':'acknowledged','disposition':'current','hold_code':None}
        self.assertIn('normal independent controls',' '.join(recommendations(report)))
