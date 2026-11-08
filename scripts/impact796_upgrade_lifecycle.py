"""Populated accepted payment-impact assessment through exact0024→0025 only."""
import os,json
from pathlib import Path
from copy import deepcopy
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase
from scripts.impact795_upgrade_lifecycle import unchanged_except_capture_audit

class ApprovalImpactUpgradeTests(TransactionTestCase):
    def test_populated_payment_impact_assessment_survives_upgrade(self):
        from scripts.impact796_upgrade import TARGET,PREVIOUS,upgrade
        from tests.payment_impact795_helpers import fixture,assert_predeployment_fixture
        from tests.payment_helpers import configure
        from tests.helpers import rev
        from apps.finance import payments,invoice_delivery
        from adapters.invoices import InternalInvoiceAdapter
        from apps.policy.services import active_component
        from apps.policy.payment_validators import DENOMINATOR,FUNDS
        from apps.policy import impact
        from apps.policy.models import ImpactAssessment,ImpactReview
        from apps.identity.models import Grant
        from django.contrib.auth import get_user_model
        self.assertEqual(os.environ.get('RUN796_RUNTIME_CLEARANCE'),'coordinator-cleared-impact796')
        self.assertEqual(connection.settings_dict['NAME'],'test_psl_sourceunit777')
        self.assertTrue(connection.get_autocommit());self.assertFalse(connection.in_atomic_block)
        applied=MigrationRecorder(connection).applied_migrations();self.assertIn(PREVIOUS,applied);self.assertNotIn(TARGET,applied)
        root=Path(os.environ['PSL_IMPACT796_UPGRADE_EVIDENCE']);self.assertTrue(root.is_dir());self.assertFalse(any(root.iterdir()))
        self.assertIs(invoice_delivery._LOCAL_ADAPTER,InternalInvoiceAdapter)
        self.assertIs(invoice_delivery._LOCAL_LOOKUP,InternalInvoiceAdapter.lookup)
        self.assertIs(invoice_delivery._LOCAL_DELIVER,InternalInvoiceAdapter.deliver)
        settlement=json.loads((Path(__file__).resolve().parents[1]/'fixtures/finance-settlement.json').read_text())
        self.assertEqual(settlement['adapter']['implementation'],'internal_invoice_register_v1')
        f=fixture();configure(f.actor,f.case,f.cov,f.actor,components=[DENOMINATOR,FUNDS])
        payment=payments.assess(f.actor,f.case.pk,f.d.pk,f.cov.pk,rev(f.case))
        assert_predeployment_fixture(f)
        self.assertIsNone(payment.manifest['context']['deployment_request']);self.assertIsNone(payment.manifest['context']['external_ref'])
        old=active_component(FUNDS,f.case);new=configure(f.actor,f.case,f.cov,f.actor,components=[FUNDS])[0]
        assessment=impact.capture(f.actor,f.case.pk,old.pk,new.pk,['finance.payment_assessments'],f.e['policy_decision'].pk,'Existing795 payment impact')
        self.assertEqual([r['id'] for r in assessment.observation['domains']['finance.payment_assessments']],[payment.pk])
        reviewer=get_user_model().objects.create_user(username='impact796-old-reviewer')
        Grant.objects.bulk_create([Grant(case=f.case,user=reviewer,action=g.action) for g in Grant.objects.filter(case=f.case,user=f.actor)])
        review=impact.review(reviewer,f.case.pk,assessment.pk,'accept',f.e['policy_decision'].pk,'Preserve independent795 assessment')
        before=dict(ImpactAssessment.objects.values().get(pk=assessment.pk));review_before=dict(ImpactReview.objects.values().get(pk=review.pk))
        self.assertEqual(upgrade(connection,root)['status'],'EXACT_DECLARED_UPGRADE_ONLY')
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
        from tests.approval_helpers import fixture as routing_fixture,policy
        from apps.pmo import approval_routing
        from apps.policy.approval_validators import ROUTES
        from django.apps import apps
        f=routing_fixture(prefix='impact796-new')
        job=approval_routing.reserve(f['actor'],f['case'].pk,f['request'].pk)
        old=active_component(ROUTES,f['case']);new=policy(f,ROUTES,deepcopy(f['v']['routes']))
        def effects():
            return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models()
                if m._meta.app_label in ('finance','pmo','core','workflows')}
        # Native synthetic reserve is setup only; capture never dispatches a worker.
        baseline=effects()
        row=impact.capture(f['actor'],f['case'].pk,old.pk,new.pk,['pmo.approval_routing_jobs'],f['e']['policy_decision'].pk,'New routing metadata only')
        rows=row.observation['domains']['pmo.approval_routing_jobs'];self.assertEqual([r['id'] for r in rows],[job.pk])
        self.assertFalse(rows[0]['native_intent_current']);self.assertIsNone(rows[0]['receipt'])
        for flag in ('dispatch_readiness_evaluated','dispatch_authorized','approval_granted','effects_performed'):self.assertFalse(rows[0][flag])
        self.assertEqual(set(rows[0]),{'id','kind','metadata_only','domain_route','request','generation','purpose','status','intent_sha256','receipt','receipt_conflict','native_intent_current','state','dispatch_readiness_evaluated','dispatch_authorized','approval_granted','effects_performed'})
        unchanged_except_capture_audit(baseline,effects(),actor=f['actor'].pk,case=f['case'].pk,assessment=row.pk,previous=old.pk,successor=new.pk)
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
