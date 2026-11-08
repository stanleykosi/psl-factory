"""Populated801 unsigned exemption assessment0030→0031; pending accepted801, no runtime clearance."""
import os
from pathlib import Path
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase
from scripts.impact795_upgrade_lifecycle import unchanged_except_capture_audit

class FactoryPlanningImpactUpgradeTests(TransactionTestCase):
    def test_populated_exemption_impact_assessment_survives_upgrade(self):
        from scripts.impact802_upgrade import TARGET,PREVIOUS,upgrade
        from apps.policy import impact
        from apps.policy.models import ImpactAssessment,ImpactReview
        from apps.identity.models import Grant
        from django.contrib.auth import get_user_model
        self.assertEqual(os.environ.get('RUN802_RUNTIME_CLEARANCE'),'coordinator-cleared-impact802')
        self.assertEqual(connection.settings_dict['NAME'],'test_psl_sourceunit777')
        self.assertTrue(connection.get_autocommit());self.assertFalse(connection.in_atomic_block)
        applied=MigrationRecorder(connection).applied_migrations();self.assertIn(PREVIOUS,applied);self.assertNotIn(TARGET,applied)
        root=Path(os.environ['PSL_IMPACT802_UPGRADE_EVIDENCE']);self.assertTrue(root.is_dir());self.assertFalse(any(root.iterdir()))
        from tests.exemption_impact801_helpers import fixture as old_fixture,policy as old_policy
        f=old_fixture(username='impact802-old');a,c,e=f['a'],f['c'],f['e']
        old=f['policy'];new=old_policy(f)
        assessment=impact.capture(a,c.pk,old.pk,new.pk,['pmo.baseline_signature_exemptions'],e['policy_decision'].pk,'Existing801 unsigned exemption metadata')
        self.assertEqual([r['id'] for r in assessment.observation['domains']['pmo.baseline_signature_exemptions']],[f['row'].pk])
        reviewer=get_user_model().objects.create_user(username='impact802-old-reviewer')
        Grant.objects.bulk_create([Grant(case=c,user=reviewer,action=g.action) for g in Grant.objects.filter(case=c,user=a)])
        review=impact.review(reviewer,c.pk,assessment.pk,'accept',e['policy_decision'].pk,'Independent prior unsigned exemption review')
        before=dict(ImpactAssessment.objects.values().get(pk=assessment.pk));review_before=dict(ImpactReview.objects.values().get(pk=review.pk))
        self.assertEqual(upgrade(connection,root)['status'],'EXACT_DECLARED_UPGRADE_ONLY')
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
        from tests.factory_planning_impact802_helpers import fixture,policy
        from django.apps import apps
        f=fixture(username='impact802-new');new=policy(f)
        def effects():return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label in ('finance','pmo','core','documents','workflows','agents')}
        # Both fixtures and policy successors are setup, not projection effects; new fixture remains unsigned.
        baseline=effects()
        row=impact.capture(f['a'],f['c'].pk,f['policy'].pk,new.pk,['workflows.factory_planning_profiles'],f['e']['policy_decision'].pk,'Selected planning profile metadata only')
        rows=row.observation['domains']['workflows.factory_planning_profiles'];self.assertEqual([r['id'] for r in rows],[f['work'].pk])
        self.assertEqual(rows[0]['policy'],f['policy'].pk)
        for flag in ('worker_started','authority_rebound','effects_performed'):self.assertFalse(rows[0][flag])
        self.assertEqual(set(rows[0]),{'id','kind','metadata_only','domain_route','definition','status','revision','policy','state','worker_started','authority_rebound','effects_performed'})
        unchanged_except_capture_audit(baseline,effects(),actor=f['a'].pk,case=f['c'].pk,assessment=row.pk,previous=f['policy'].pk,successor=new.pk)
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
