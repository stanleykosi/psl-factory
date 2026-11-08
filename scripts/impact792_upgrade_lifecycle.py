"""One-shot populated impact function upgrade; requires separately cleared harness."""
import os
from pathlib import Path
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase

class RecognitionImpactUpgradeTests(TransactionTestCase):
    def test_populated_prior_impact_assessment_survives_upgrade(self):
        from scripts.impact792_upgrade import TARGET, PREVIOUS, upgrade
        from tests.test_policy_impact import setup
        from apps.policy import impact
        from apps.policy.models import ImpactAssessment, ImpactReview
        self.assertEqual(os.environ.get('RUN792_RUNTIME_CLEARANCE'),'coordinator-cleared-impact792')
        self.assertEqual(connection.settings_dict['NAME'],'test_psl_sourceunit777')
        self.assertTrue(connection.get_autocommit());self.assertFalse(connection.in_atomic_block)
        applied=MigrationRecorder(connection).applied_migrations()
        self.assertIn(PREVIOUS,applied);self.assertNotIn(TARGET,applied)
        root=Path(os.environ['PSL_IMPACT792_UPGRADE_EVIDENCE'])
        self.assertTrue(root.is_dir());self.assertFalse(any(root.iterdir()))
        a,b,c,e,old,new=setup()
        assessment=impact.capture(a,c.pk,old.pk,new.pk,['pmo.decisions'],e['policy_decision'].pk,'Prior native impact792 fixture')
        review=impact.review(b,c.pk,assessment.pk,'accept',e['policy_decision'].pk,'Prior independently reviewed impact fixture')
        before=dict(ImpactAssessment.objects.values().get(pk=assessment.pk))
        before_review=dict(ImpactReview.objects.values().get(pk=review.pk))
        self.assertEqual(upgrade(connection,root)['status'],'EXACT_DECLARED_UPGRADE_ONLY')
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),before_review)
        from tests.recognition_helpers import fixture,reviewed,policy
        from apps.policy.recognition_validators import REVIEW
        from apps.finance.recognition_models import RecognitionRecord
        from apps.workflows.models import Outbox
        from copy import deepcopy
        f=fixture();record=reviewed(f)
        successor=policy(f['actor'],f['case'],REVIEW,deepcopy(f['config']['review']),f['evidence']['policy_decision'])
        prior_records=list(RecognitionRecord.objects.values());jobs=list(Outbox.objects.values())
        row=impact.capture(f['actor'],f['case'].pk,f['review_policy'].pk,successor.pk,['finance.recognition_records'],f['evidence']['policy_decision'].pk,'New bounded metadata impact')
        records=row.observation['domains']['finance.recognition_records']
        self.assertEqual([r['id'] for r in records],[record.pk]);self.assertFalse(records[0]['native_current'])
        self.assertFalse(records[0]['business_approval']);self.assertFalse(records[0]['accounting_effects_performed'])
        self.assertNotIn('Explicit synthetic human statement',str(row.observation))
        self.assertEqual(prior_records,list(RecognitionRecord.objects.values()));self.assertEqual(jobs,list(Outbox.objects.values()))
