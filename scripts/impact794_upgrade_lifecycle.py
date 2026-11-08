"""One-shot populated readiness-impact to comparison-impact additive upgrade."""
import os
from pathlib import Path
from copy import deepcopy
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase

class ComparisonImpactUpgradeTests(TransactionTestCase):
    def test_populated_readiness_impact_assessment_survives_upgrade(self):
        from scripts.impact794_upgrade import TARGET,PREVIOUS,upgrade
        from tests import planning_helpers as h
        from apps.pmo import planning
        from apps.policy.services import active_component
        from apps.policy.planning_validators import COMPONENT
        from apps.policy import impact
        from apps.policy.models import ImpactAssessment,ImpactReview
        from apps.identity.models import Grant
        from django.contrib.auth import get_user_model
        self.assertEqual(os.environ.get('RUN794_RUNTIME_CLEARANCE'),'coordinator-cleared-impact794')
        self.assertEqual(connection.settings_dict['NAME'],'test_psl_sourceunit777')
        self.assertTrue(connection.get_autocommit());self.assertFalse(connection.in_atomic_block)
        applied=MigrationRecorder(connection).applied_migrations();self.assertIn(PREVIOUS,applied);self.assertNotIn(TARGET,applied)
        root=Path(os.environ['PSL_IMPACT794_UPGRADE_EVIDENCE']);self.assertTrue(root.is_dir());self.assertFalse(any(root.iterdir()))
        f=h.fixture(username='impact794-old');h.observe(f);planning.prepare(f['a'],f['c'].pk,f['packet'].pk)
        old=active_component(COMPONENT,f['c']);new=h.criteria(f,deepcopy(f['rules']))
        assessment=impact.capture(f['a'],f['c'].pk,old.pk,new.pk,['pmo.planning_readiness'],f['e']['policy_decision'].pk,'Existing793 readiness impact')
        reviewer=get_user_model().objects.create_user(username='impact794-old-reviewer')
        Grant.objects.bulk_create([Grant(case=f['c'],user=reviewer,action=g.action) for g in Grant.objects.filter(case=f['c'],user=f['a'])])
        review=impact.review(reviewer,f['c'].pk,assessment.pk,'accept',f['e']['policy_decision'].pk,'Preserve independent793 assessment')
        before=dict(ImpactAssessment.objects.values().get(pk=assessment.pk));review_before=dict(ImpactReview.objects.values().get(pk=review.pk))
        self.assertEqual(upgrade(connection,root)['status'],'EXACT_DECLARED_UPGRADE_ONLY')
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
        from tests.test_planning_comparison_impact import comparison_fixture
        from apps.core.models import Evidence
        from apps.pmo.models import Baseline
        from apps.workflows.models import Outbox
        f,old,_,_,comparison=comparison_fixture(username='impact794-new')
        new=h.criteria(f,deepcopy(f['rules']))
        evidence=list(Evidence.objects.order_by('pk').values());jobs=list(Outbox.objects.order_by('pk').values());baselines=list(Baseline.objects.order_by('pk').values())
        row=impact.capture(f['a'],f['c'].pk,old.pk,new.pk,['pmo.planning_comparisons'],f['e']['policy_decision'].pk,'New comparison metadata only')
        rows=row.observation['domains']['pmo.planning_comparisons'];self.assertEqual([r['id'] for r in rows],[comparison.pk])
        self.assertFalse(rows[0]['native_current']);self.assertFalse(rows[0]['business_approval']);self.assertFalse(rows[0]['contract_renewed']);self.assertFalse(rows[0]['effects_performed'])
        self.assertNotIn(comparison.body,str(row.observation));self.assertEqual(evidence,list(Evidence.objects.order_by('pk').values()));self.assertEqual(jobs,list(Outbox.objects.order_by('pk').values()));self.assertEqual(baselines,list(Baseline.objects.order_by('pk').values()))
