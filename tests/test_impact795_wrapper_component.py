from pathlib import Path
from unittest import TestCase
ROOT=Path(__file__).resolve().parents[1]
class PaymentImpactWrapperTests(TestCase):
    def test_exact_predecessor(self):
        from scripts.impact795_upgrade import TARGET,PREVIOUS,FUNCTION_PREVIOUS
        self.assertEqual(TARGET,('policy','0024_payment_assessment_policy_impact'))
        self.assertEqual(PREVIOUS,('policy','0023_planning_comparison_policy_impact'))
        self.assertEqual(FUNCTION_PREVIOUS,'0023_planning_comparison_policy_impact')
    def test_caps_and_populated_before_primary(self):
        s=(ROOT/'scripts/impact795_run.sh').read_text()
        self.assertLess(s.index('step upgrade-test'),s.index('step upgrade-primary'))
        self.assertIn('seq 1 8',s);self.assertIn('sz<=183500800 && wf>=234881024 && tf>=440401920',s)
        self.assertIn('step test-restart-equality equal test-final test-restart',s)
    def test_old_comparison_assessment_and_review_preserved(self):
        s=(ROOT/'scripts/impact795_upgrade_lifecycle.py').read_text()
        self.assertLess(s.index("['pmo.planning_comparisons']"),s.index('upgrade(connection,root)'))
        self.assertLess(s.index('review_before='),s.index('upgrade(connection,root)'))
        self.assertLess(s.index('upgrade(connection,root)'),s.index("f=fixture()"))
        self.assertIn('review_before)',s)

        # Pure comparison: permit only one exact engineering audit append.
        from scripts.impact795_upgrade_lifecycle import unchanged_except_capture_audit
        from copy import deepcopy
        before={'core.Audit':[{'id':1,'data':{'keep':'original'}}], 'finance.PaymentAssessment':[{'id':2}]}
        event={'id':3,'actor_id':4,'case_id':5,'action':'policy.impact.captured',
            'data':{'assessment':6,'previous':7,'successor':8},'created_at':'recorded'}
        after=deepcopy(before);after['core.Audit'].append(event)
        args=dict(actor=4,case=5,assessment=6,previous=7,successor=8)
        self.assertEqual(unchanged_except_capture_audit(before,after,**args),3)
        for field,bad in [('actor_id',99),('case_id',99),('action','wrong'),('data',{})]:
            changed=deepcopy(after);changed['core.Audit'][-1][field]=bad
            with self.assertRaises(AssertionError):unchanged_except_capture_audit(before,changed,**args)
        for changed in (deepcopy(before),deepcopy(after)):
            if changed==before:pass
            elif 'mutated' not in changed['core.Audit'][0]:
                changed['core.Audit'][0]['mutated']=True
            with self.assertRaises(AssertionError):unchanged_except_capture_audit(before,changed,**args)
        changed=deepcopy(after);changed['core.Audit'].append(dict(event,id=9))
        with self.assertRaises(AssertionError):unchanged_except_capture_audit(before,changed,**args)
        changed=deepcopy(after);changed['finance.PaymentAssessment'].append({'id':99})
        with self.assertRaises(AssertionError):unchanged_except_capture_audit(before,changed,**args)
