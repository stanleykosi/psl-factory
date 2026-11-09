"""Pure closure checks for the no-migration797b continuation."""
import ast
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]

class Impact797bCompatibilityComponentTests(unittest.TestCase):
    def test_compatibility_never_migrates_and_requires_existing0026(self):
        source=(ROOT/'scripts/impact797b_compatibility.py').read_text()
        tree=ast.parse(source)
        calls={ast.unparse(n.func).split('.')[-1] for n in ast.walk(tree) if isinstance(n,ast.Call)}
        self.assertFalse(calls & {'migrate','upgrade','call_command'})
        self.assertIn('self.assertIn(TARGET,applied)',source)
        self.assertIn('migration_plan',source)
        self.assertIn('body(TARGET[1])',source)
        self.assertIn('RUN797B_RUNTIME_CLEARANCE',source)
        self.assertIn('unchanged_except_capture_audit',calls)
        self.assertLess(source.index('baseline=effects()'),source.index('row=impact.capture'))
        self.assertEqual(source.count('self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)'),2)
        self.assertEqual(source.count('self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)'),2)
    def test_generic_findings_allowed_only_at_wrapper_with_closed_domain(self):
        tree=ast.parse((ROOT/'tests/test_delivery_policy_impact.py').read_text())
        fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='test_saved_review_agent_and_current_delivery_reader')
        source=ast.unparse(fn)
        self.assertIn("self.assertEqual(result['findings'],",source)
        self.assertIn('Delivery prerequisite qualification is not universal closure validity.',source)
        self.assertIn('self.assertEqual(set(record), closed)',source)
        self.assertIn("self.assertNotIn(key, str(result['observation']))",source)
        self.assertIn('self.assertNotIn(key, str(row.observation))',source)
        self.assertIn('self.assertNotIn(key, str(result))',source)
