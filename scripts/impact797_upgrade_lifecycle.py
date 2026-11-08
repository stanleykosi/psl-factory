"""Populated routing-impact assessment through exact0025→0026 only."""
import os
from pathlib import Path
from copy import deepcopy
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase
from scripts.impact795_upgrade_lifecycle import unchanged_except_capture_audit

class DeliveryImpactUpgradeTests(TransactionTestCase):
    def test_populated_routing_impact_assessment_survives_upgrade(self):
        from scripts.impact797_upgrade import TARGET,PREVIOUS,upgrade
        from tests.approval_helpers import fixture,policy
        from apps.pmo import approval_routing
        from apps.policy.services import active_component
        from apps.policy.approval_validators import ROUTES
        from apps.policy import impact
        from apps.policy.models import ImpactAssessment,ImpactReview
        from apps.identity.models import Grant
        from django.contrib.auth import get_user_model
        self.assertEqual(os.environ.get('RUN797_RUNTIME_CLEARANCE'),'coordinator-cleared-impact797')
        self.assertEqual(connection.settings_dict['NAME'],'test_psl_sourceunit777')
        self.assertTrue(connection.get_autocommit());self.assertFalse(connection.in_atomic_block)
        applied=MigrationRecorder(connection).applied_migrations();self.assertIn(PREVIOUS,applied);self.assertNotIn(TARGET,applied)
        root=Path(os.environ['PSL_IMPACT797_UPGRADE_EVIDENCE']);self.assertTrue(root.is_dir());self.assertFalse(any(root.iterdir()))
        f=fixture(prefix='impact797-old');job=approval_routing.reserve(f['actor'],f['case'].pk,f['request'].pk)
        old=active_component(ROUTES,f['case']);new=policy(f,ROUTES,deepcopy(f['v']['routes']))
        assessment=impact.capture(f['actor'],f['case'].pk,old.pk,new.pk,['pmo.approval_routing_jobs'],f['e']['policy_decision'].pk,'Existing796 routing impact')
        self.assertEqual([r['id'] for r in assessment.observation['domains']['pmo.approval_routing_jobs']],[job.pk])
        reviewer=get_user_model().objects.create_user(username='impact797-old-reviewer')
        Grant.objects.bulk_create([Grant(case=f['case'],user=reviewer,action=g.action) for g in Grant.objects.filter(case=f['case'],user=f['actor'])])
        review=impact.review(reviewer,f['case'].pk,assessment.pk,'accept',f['e']['policy_decision'].pk,'Preserve independent796 assessment')
        before=dict(ImpactAssessment.objects.values().get(pk=assessment.pk));review_before=dict(ImpactReview.objects.values().get(pk=review.pk))
        self.assertEqual(upgrade(connection,root)['status'],'EXACT_DECLARED_UPGRADE_ONLY')
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
        from tests.test_delivery import DeliveryFixture
        from tests.helpers import rev
        from apps.pmo import delivery_closure
        from apps.documents import delivery as publication_worker
        from adapters.publications import InternalPublicationAdapter
        from django.apps import apps
        import inspect
        self.assertEqual(InternalPublicationAdapter.deliver.__module__,'adapters.publications')
        self.assertIn('adapter=adapter or InternalPublicationAdapter()',inspect.getsource(publication_worker.run_publication_once))
        f=DeliveryFixture();f.setup_delivery();f.accepted();f.criteria();f.observations()
        prerequisite=delivery_closure.evaluate_hypercare(f.actor,f.case.pk,f.d.pk,f.e['requirements'].pk,'Synthetic original qualification',rev(f.case))
        old=active_component('D11.hypercare_criteria_ref',f.case);f.criteria();new=active_component(old.component,f.case)
        def effects():
            return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models()
                if m._meta.app_label in ('finance','pmo','core','documents','workflows')}
        # Native synthetic signing/local publication/evaluation are setup only.
        baseline=effects()
        row=impact.capture(f.actor,f.case.pk,old.pk,new.pk,['pmo.delivery_prerequisites'],f.e['policy_decision'].pk,'New delivery prerequisite metadata only')
        rows=row.observation['domains']['pmo.delivery_prerequisites'];self.assertEqual([r['id'] for r in rows],[prerequisite.pk])
        self.assertFalse(rows[0]['native_closure_prerequisite_current'])
        for flag in ('closure_authorized','deployment_authorized','debt_waived','effects_performed'):self.assertFalse(rows[0][flag])
        self.assertEqual(set(rows[0]),{'id','kind','record_kind','metadata_only','domain_route','dossier','snapshot_sha256','policy','head','native_closure_prerequisite_current','state','closure_authorized','deployment_authorized','debt_waived','effects_performed'})
        unchanged_except_capture_audit(baseline,effects(),actor=f.actor.pk,case=f.case.pk,assessment=row.pk,previous=old.pk,successor=new.pk)
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
