"""Populated delivery assessment0026→0027; source-only until accepted797 pins exist."""
import os,inspect
from pathlib import Path
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase
from scripts.impact795_upgrade_lifecycle import unchanged_except_capture_audit

class RecoveryImpactUpgradeTests(TransactionTestCase):
    def test_populated_delivery_impact_assessment_survives_upgrade(self):
        from scripts.impact798_upgrade import TARGET,PREVIOUS,upgrade
        from tests.test_delivery import DeliveryFixture
        from tests.helpers import rev
        from apps.pmo import delivery_closure
        from apps.documents import delivery as worker
        from adapters.publications import InternalPublicationAdapter
        from apps.policy.services import active_component
        from apps.policy import impact
        from apps.policy.models import ImpactAssessment,ImpactReview
        from apps.identity.models import Grant
        from django.contrib.auth import get_user_model
        self.assertEqual(os.environ.get('RUN798_RUNTIME_CLEARANCE'),'coordinator-cleared-impact798')
        self.assertEqual(connection.settings_dict['NAME'],'test_psl_sourceunit777')
        self.assertTrue(connection.get_autocommit());self.assertFalse(connection.in_atomic_block)
        applied=MigrationRecorder(connection).applied_migrations();self.assertIn(PREVIOUS,applied);self.assertNotIn(TARGET,applied)
        root=Path(os.environ['PSL_IMPACT798_UPGRADE_EVIDENCE']);self.assertTrue(root.is_dir());self.assertFalse(any(root.iterdir()))
        self.assertEqual(InternalPublicationAdapter.deliver.__module__,'adapters.publications')
        self.assertIn('adapter=adapter or InternalPublicationAdapter()',inspect.getsource(worker.run_publication_once))
        f=DeliveryFixture();f.setup_delivery();f.accepted();f.criteria();f.observations()
        prerequisite=delivery_closure.evaluate_hypercare(f.actor,f.case.pk,f.d.pk,f.e['requirements'].pk,'Synthetic prior qualification',rev(f.case))
        old=active_component('D11.hypercare_criteria_ref',f.case);f.criteria();new=active_component(old.component,f.case)
        assessment=impact.capture(f.actor,f.case.pk,old.pk,new.pk,['pmo.delivery_prerequisites'],f.e['policy_decision'].pk,'Existing797 delivery impact')
        self.assertEqual([r['id'] for r in assessment.observation['domains']['pmo.delivery_prerequisites']],[prerequisite.pk])
        reviewer=get_user_model().objects.create_user(username='impact798-old-reviewer')
        Grant.objects.bulk_create([Grant(case=f.case,user=reviewer,action=g.action) for g in Grant.objects.filter(case=f.case,user=f.actor)])
        review=impact.review(reviewer,f.case.pk,assessment.pk,'accept',f.e['policy_decision'].pk,'Independent prior delivery review')
        before=dict(ImpactAssessment.objects.values().get(pk=assessment.pk));review_before=dict(ImpactReview.objects.values().get(pk=review.pk))
        self.assertEqual(upgrade(connection,root)['status'],'EXACT_DECLARED_UPGRADE_ONLY')
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
        from tests.recovery_impact798_helpers import fixture,policy
        from django.apps import apps
        f=fixture(username='impact798-new');new=policy(f)
        def effects():
            return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models()
                if m._meta.app_label in ('finance','pmo','core','documents','workflows')}
        baseline=effects()
        row=impact.capture(f['a'],f['c'].pk,f['policy'].pk,new.pk,['pmo.signed_adoption_recovery_requests'],f['e']['policy_decision'].pk,'New request metadata only')
        rows=row.observation['domains']['pmo.signed_adoption_recovery_requests'];self.assertEqual([r['id'] for r in rows],[f['request'].pk])
        self.assertFalse(rows[0]['request_snapshot_current'])
        for flag in ('authority_recovered','approval_granted','effects_performed'):self.assertFalse(rows[0][flag])
        self.assertEqual(set(rows[0]),{'id','kind','metadata_only','domain_route','adoption','snapshot_sha256','request_snapshot_current','state','authority_recovered','approval_granted','effects_performed'})
        unchanged_except_capture_audit(baseline,effects(),actor=f['a'].pk,case=f['c'].pk,assessment=row.pk,previous=f['policy'].pk,successor=new.pk)
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
