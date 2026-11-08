"""Populated800 emergency request assessment0029→0030; pending accepted800, no runtime clearance."""
import os
from pathlib import Path
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase
from scripts.impact795_upgrade_lifecycle import unchanged_except_capture_audit

class ExemptionImpactUpgradeTests(TransactionTestCase):
    def test_populated_emergency_impact_assessment_survives_upgrade(self):
        from scripts.impact801_upgrade import TARGET,PREVIOUS,upgrade
        from apps.policy import impact
        from apps.policy.models import ImpactAssessment,ImpactReview
        from apps.identity.models import Grant
        from django.contrib.auth import get_user_model
        self.assertEqual(os.environ.get('RUN801_RUNTIME_CLEARANCE'),'coordinator-cleared-impact801')
        self.assertEqual(connection.settings_dict['NAME'],'test_psl_sourceunit777')
        self.assertTrue(connection.get_autocommit());self.assertFalse(connection.in_atomic_block)
        applied=MigrationRecorder(connection).applied_migrations();self.assertIn(PREVIOUS,applied);self.assertNotIn(TARGET,applied)
        root=Path(os.environ['PSL_IMPACT801_UPGRADE_EVIDENCE']);self.assertTrue(root.is_dir());self.assertFalse(any(root.iterdir()))
        from tests.emergency_impact800_helpers import fixture as old_fixture,policy as old_policy
        f=old_fixture(username='impact801-old');a,c,e=f['a'],f['c'],f['e']
        old=f['policy'];new=old_policy(f)
        assessment=impact.capture(a,c.pk,old.pk,new.pk,['pmo.emergency_recovery_requests'],e['policy_decision'].pk,'Existing800 emergency request metadata')
        self.assertEqual([r['id'] for r in assessment.observation['domains']['pmo.emergency_recovery_requests']],[f['request'].pk])
        reviewer=get_user_model().objects.create_user(username='impact801-old-reviewer')
        Grant.objects.bulk_create([Grant(case=c,user=reviewer,action=g.action) for g in Grant.objects.filter(case=c,user=a)])
        review=impact.review(reviewer,c.pk,assessment.pk,'accept',e['policy_decision'].pk,'Independent prior emergency request review')
        before=dict(ImpactAssessment.objects.values().get(pk=assessment.pk));review_before=dict(ImpactReview.objects.values().get(pk=review.pk))
        self.assertEqual(upgrade(connection,root)['status'],'EXACT_DECLARED_UPGRADE_ONLY')
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
        from tests.exemption_impact801_helpers import fixture,policy
        from django.apps import apps
        f=fixture(username='impact801-new');new=policy(f)
        def effects():return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label in ('finance','pmo','core','documents','workflows','agents')}
        # Both fixtures and policy successors are setup, not projection effects; new fixture remains unsigned.
        baseline=effects()
        row=impact.capture(f['a'],f['c'].pk,f['policy'].pk,new.pk,['pmo.baseline_signature_exemptions'],f['e']['policy_decision'].pk,'Selected unsigned exemption metadata only')
        rows=row.observation['domains']['pmo.baseline_signature_exemptions'];self.assertEqual([r['id'] for r in rows],[f['row'].pk])
        self.assertFalse(rows[0]['selected_exemption_valid_now'])
        for flag in ('signature_created','signing_authorized','baseline_assurance_granted','effects_performed'):self.assertFalse(rows[0][flag])
        self.assertEqual(set(rows[0]),{'id','kind','metadata_only','domain_route','policy','authority','exemption_sha256','selected_exemption_valid_now','state','signature_created','signing_authorized','baseline_assurance_granted','effects_performed'})
        unchanged_except_capture_audit(baseline,effects(),actor=f['a'].pk,case=f['c'].pk,assessment=row.pk,previous=f['policy'].pk,successor=new.pk)
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
