"""One-shot populated recognition-impact→planning-impact additive upgrade."""
import os
from pathlib import Path
from copy import deepcopy
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase

class PlanningImpactUpgradeTests(TransactionTestCase):
    def test_populated_recognition_impact_assessment_survives_upgrade(self):
        from scripts.impact793_upgrade import TARGET,PREVIOUS,upgrade
        from tests.recognition_helpers import fixture,reviewed,policy
        from apps.policy.recognition_validators import REVIEW
        from apps.policy import impact
        from apps.policy.models import ImpactAssessment,ImpactReview
        from apps.identity.models import Grant
        from django.contrib.auth import get_user_model
        self.assertEqual(os.environ.get('RUN793_RUNTIME_CLEARANCE'),'coordinator-cleared-impact793')
        self.assertEqual(connection.settings_dict['NAME'],'test_psl_sourceunit777')
        self.assertTrue(connection.get_autocommit());self.assertFalse(connection.in_atomic_block)
        applied=MigrationRecorder(connection).applied_migrations()
        self.assertIn(PREVIOUS,applied);self.assertNotIn(TARGET,applied)
        root=Path(os.environ['PSL_IMPACT793_UPGRADE_EVIDENCE'])
        self.assertTrue(root.is_dir());self.assertFalse(any(root.iterdir()))
        f=fixture();record=reviewed(f)
        successor=policy(f['actor'],f['case'],REVIEW,deepcopy(f['config']['review']),f['evidence']['policy_decision'])
        assessment=impact.capture(f['actor'],f['case'].pk,f['review_policy'].pk,successor.pk,['finance.recognition_records'],f['evidence']['policy_decision'].pk,'Existing792 recognition impact')
        reviewer=get_user_model().objects.create_user(username='impact793-old-reviewer')
        Grant.objects.bulk_create([Grant(case=f['case'],user=reviewer,action=g.action) for g in Grant.objects.filter(case=f['case'],user=f['actor'])])
        review=impact.review(reviewer,f['case'].pk,assessment.pk,'accept',f['evidence']['policy_decision'].pk,'Preserve independent792 assessment')
        before=dict(ImpactAssessment.objects.values().get(pk=assessment.pk));review_before=dict(ImpactReview.objects.values().get(pk=review.pk))
        self.assertEqual(upgrade(connection,root)['status'],'EXACT_DECLARED_UPGRADE_ONLY')
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
        from tests import planning_helpers as h
        from apps.pmo import planning
        from apps.policy.services import active_component
        from apps.policy.planning_validators import COMPONENT
        from apps.core.models import Evidence
        from apps.workflows.models import Outbox
        f=h.fixture(username='impact793-new-planning');h.observe(f)
        ready=planning.prepare(f['a'],f['c'].pk,f['packet'].pk)
        old=active_component(COMPONENT,f['c']);new=h.criteria(f,deepcopy(f['rules']))
        before_evidence=list(Evidence.objects.order_by('pk').values());before_jobs=list(Outbox.objects.order_by('pk').values())
        new_assessment=impact.capture(f['a'],f['c'].pk,old.pk,new.pk,['pmo.planning_readiness'],f['e']['policy_decision'].pk,'New direct planning metadata impact')
        rows=new_assessment.observation['domains']['pmo.planning_readiness']
        self.assertEqual([r['id'] for r in rows],[ready.pk]);self.assertFalse(rows[0]['native_current'])
        self.assertFalse(rows[0]['business_approval']);self.assertFalse(rows[0]['native_verified']);self.assertFalse(rows[0]['effects_performed'])
        self.assertNotIn(ready.body,str(new_assessment.observation))
        self.assertEqual(before_evidence,list(Evidence.objects.order_by('pk').values()));self.assertEqual(before_jobs,list(Outbox.objects.order_by('pk').values()))
