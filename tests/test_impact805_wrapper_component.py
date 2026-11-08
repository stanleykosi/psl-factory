"""Source/pure805 wrapper proof only. No database lifecycle is invoked."""
import ast,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Engagement805WrapperTests(unittest.TestCase):
    def test_exact_selection_predecessor_and_isolated_lock(self):
        v=json.loads((ROOT/'docs/design/impact805-selection.json').read_text())
        self.assertEqual(v['accepted_predecessor'],'9069d2d99e29ac31127a80d734a3d889432bc7f9')
        self.assertEqual((v['count'],v['total_native_count'],len(v['batches'])),(14,15,8))
        ids=[i for b in v['batches'] for i in b['ids']];self.assertEqual(len(set(ids)),14)
        lock=[b for b in v['batches'] if any('EngagementProfileLockTests' in i for i in b['ids'])]
        self.assertEqual(len(lock),1);self.assertEqual(len(lock[0]['ids']),1)
        self.assertTrue(all(b['outer_timeout_seconds']==300 and len(b['ids'])<=2 for b in v['batches']))
    def test_additive_predecessor_and_exact_upgrade_identity(self):
        from scripts.impact805_upgrade import TARGET,PREVIOUS,FUNCTION_PREVIOUS
        self.assertEqual(TARGET,('policy','0033_factory_engagement_policy_impact'))
        self.assertEqual(PREVIOUS,('policy','0032_factory_planning_binding_impact'));self.assertEqual(FUNCTION_PREVIOUS,PREVIOUS[1])
        text=(ROOT/'scripts/impact805_upgrade.py').read_text()
        self.assertIn('Repeated migration changed raw state',text)
        self.assertIn('Undeclared function property changed',text)
        self.assertIn('Other sequence changed',text)
    def test_populated_prior_binding_review_and_setup_before_effects(self):
        text=(ROOT/'scripts/impact805_upgrade_lifecycle.py').read_text()
        self.assertLess(text.index("['workflows.factory_planning_execution_bindings']"),text.index('upgrade(connection,root)'))
        self.assertLess(text.index('review=impact.review'),text.index('upgrade(connection,root)'))
        self.assertLess(text.index("f=fixture(username='impact805-new')"),text.index('baseline=effects()'))
        self.assertIn('unchanged_except_capture_audit(baseline,effects()',text)
        for name in ('finance','pmo','core','documents','workflows','agents','identity'):self.assertIn(repr(name),text)
        self.assertEqual(text.count('self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)'),2)
    def test_resource_and_supervisor_guards_and_no_reset(self):
        text=(ROOT/'scripts/impact805_run.sh').read_text()
        for token in ('sz<=183500800 && wf>=234881024 && tf>=440401920','sz>173015040 || wf<268435456 || tf<471859200','limit=152043520','seq 1 8','scripts/native_stage_supervisor782.py','scripts.impact804_index','groups-final-verification.log'):
            self.assertIn(token,text)
        for forbidden in ('createdb','dropdb','initdb','migrate policy zero'):self.assertNotIn(forbidden,text)
        self.assertLess(text.index('step baseline-compare'),text.index('step upgrade-test'))
        self.assertLess(text.index('step test-baseline-compare'),text.index('step upgrade-test'))
        self.assertLess(text.index('step upgrade-test'),text.index('step upgrade-primary'))
    def test_complete_raw_preservation_dual_restart_and_source_checks(self):
        text=(ROOT/'scripts/impact805_run.sh').read_text();h=(ROOT/'scripts/impact805_harness.py').read_text()
        for token in ('step primary-upgrade-test-equal','step primary-preserved','step restart-equality equal after-tests after-restart','step test-restart-equality equal test-final test-restart','equal_index','Source head changed during proof'):
            self.assertIn(token,text)
        for token in ('raw-row-changes.json','sequence-changes.json','teardown-preservation.json','raw-metadata-changes.json','No existing business rows may be flushed','Runtime clearance is pending'):
            self.assertIn(token,h)
    def test_accepted_review_and_failed_proof_formats_are_distinct(self):
        text=(ROOT/'scripts/impact805_inputs.py').read_text()
        self.assertIn("manifest['artifacts']",text);self.assertIn("v['runtime_inputs']['review_result']",text)
        for token in ('PARTIAL_804A_RESOURCE_STOP_NOT_ACCEPTED','PARTIAL_798A_FAILED_NOT_ACCEPTED','PARTIAL_797A_FAILED_NOT_ACCEPTED','PARTIAL_797B_FAILED_NOT_ACCEPTED'):
            self.assertIn(token,text)
        self.assertNotIn('django',text)
        tree=ast.parse(text)
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('connect','cursor','migrate') for n in ast.walk(tree)))
if __name__=='__main__':unittest.main()
