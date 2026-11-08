"""Fresh compatibility on already0032, never applies or replays migrations."""
import os
from pathlib import Path
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase
from scripts.impact795_upgrade_lifecycle import unchanged_except_capture_audit

class PlanningBindingImpactCompatibilityTests(TransactionTestCase):
    def test_populated_profile_and_binding_compatible_at0032(self):
        from scripts.impact804b_harness import verify_schema
        verify_schema(connection)
        from apps.policy import impact
        from apps.policy.models import ImpactAssessment,ImpactReview
        from apps.identity.models import Grant
        from django.contrib.auth import get_user_model
        self.assertEqual(os.environ.get('RUN804B_RUNTIME_CLEARANCE'),'coordinator-cleared-impact804b')
        self.assertEqual(connection.settings_dict['NAME'],'test_psl_sourceunit777')
        self.assertTrue(connection.get_autocommit());self.assertFalse(connection.in_atomic_block)
        from tests.factory_planning_impact802_helpers import fixture as old_fixture,policy as old_policy
        f=old_fixture(username='impact804-old');a,c,e=f['a'],f['c'],f['e'];old=f['policy'];new=old_policy(f)
        assessment=impact.capture(a,c.pk,old.pk,new.pk,['workflows.factory_planning_profiles'],e['policy_decision'].pk,'Existing802 planning profile metadata')
        self.assertEqual([r['id'] for r in assessment.observation['domains']['workflows.factory_planning_profiles']],[f['work'].pk])
        reviewer=get_user_model().objects.create_user(username='impact804-old-reviewer')
        Grant.objects.bulk_create([Grant(case=c,user=reviewer,action=g.action) for g in Grant.objects.filter(case=c,user=a)])
        review=impact.review(reviewer,c.pk,assessment.pk,'accept',e['policy_decision'].pk,'Independent prior planning profile review')
        before=dict(ImpactAssessment.objects.values().get(pk=assessment.pk));review_before=dict(ImpactReview.objects.values().get(pk=review.pk))
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
        from tests.factory_planning_binding804_helpers import fixture,policy
        from django.apps import apps
        f=fixture(username='impact804-new');new=policy(f)
        def effects():return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label in ('finance','pmo','core','documents','workflows','agents')}
        # Canonical bind and its pointer/fence/Audit effects belong strictly to fixture setup.
        baseline=effects()
        row=impact.capture(f['a'],f['c'].pk,f['policy'].pk,new.pk,['workflows.factory_planning_execution_bindings'],f['e']['policy_decision'].pk,'Historical planning binding metadata only')
        rows=row.observation['domains']['workflows.factory_planning_execution_bindings'];self.assertEqual([r['id'] for r in rows],[f['binding'].pk])
        self.assertEqual(rows[0]['configuration'],f['policy'].pk);self.assertFalse(rows[0]['effects_performed'])
        self.assertEqual(rows[0]['state'],'historical_planning_execution_binding')
        self.assertEqual(set(rows[0]),{'id','kind','metadata_only','domain_route','sequence','configuration','state','effects_performed'})
        unchanged_except_capture_audit(baseline,effects(),actor=f['a'].pk,case=f['c'].pk,assessment=row.pk,previous=f['policy'].pk,successor=new.pk)
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
