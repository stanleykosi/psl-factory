"""Fresh postmigration compatibility only;795a failed upgrade case remains failed."""
import os
import json
from pathlib import Path
from copy import deepcopy
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase

def unchanged_except_capture_audit(before, after, *, actor, case, assessment, previous, successor):
    """Permit exactly the declared capture audit; preserve every other raw row."""
    if set(before) != set(after):
        raise AssertionError('Effect model set changed')
    original=before['core.Audit'];current=after['core.Audit']
    original_ids={r['id'] for r in original}
    retained=[r for r in current if r['id'] in original_ids]
    added=[r for r in current if r['id'] not in original_ids]
    if retained != original or len(added) != 1:
        raise AssertionError('Historical audit changed or unexpected audit append count')
    event=added[0]
    if (event['actor_id'],event['case_id'],event['action'],event['data']) != (
            actor,case,'policy.impact.captured',
            {'assessment':assessment,'previous':previous,'successor':successor}):
        raise AssertionError('Capture audit actor/case/action/payload differs')
    expected=dict(before);expected['core.Audit']=current
    if expected != after:
        raise AssertionError('Unexpected business-state effects')
    return event['id']

class PaymentImpactCompatibilityTests(TransactionTestCase):
    def test_postmigration_comparison_and_payment_compatibility(self):
        from scripts.impact795c_upgrade import TARGET,PREVIOUS
        from tests import planning_helpers as h
        from tests.test_planning_comparison_impact import comparison_fixture
        from apps.policy import impact
        from apps.policy.models import ImpactAssessment,ImpactReview
        from apps.identity.models import Grant
        from django.contrib.auth import get_user_model
        self.assertEqual(os.environ.get('RUN795C_RUNTIME_CLEARANCE'),'coordinator-cleared-impact795c')
        self.assertEqual(connection.settings_dict['NAME'],'test_psl_sourceunit777')
        self.assertTrue(connection.get_autocommit());self.assertFalse(connection.in_atomic_block)
        applied=MigrationRecorder(connection).applied_migrations();self.assertIn(PREVIOUS,applied);self.assertIn(TARGET,applied)
        from django.db.migrations.executor import MigrationExecutor
        executor=MigrationExecutor(connection)
        self.assertFalse(executor.migration_plan(executor.loader.graph.leaf_nodes()))
        f,old,_,_,comparison=comparison_fixture(username='impact795-old')
        new=h.criteria(f,deepcopy(f['rules']))
        assessment=impact.capture(f['a'],f['c'].pk,old.pk,new.pk,['pmo.planning_comparisons'],f['e']['policy_decision'].pk,'Existing794 comparison impact')
        self.assertEqual([r['id'] for r in assessment.observation['domains']['pmo.planning_comparisons']],[comparison.pk])
        reviewer=get_user_model().objects.create_user(username='impact795-old-reviewer')
        Grant.objects.bulk_create([Grant(case=f['c'],user=reviewer,action=g.action) for g in Grant.objects.filter(case=f['c'],user=f['a'])])
        review=impact.review(reviewer,f['c'].pk,assessment.pk,'accept',f['e']['policy_decision'].pk,'Preserve independent794 assessment')
        before=dict(ImpactAssessment.objects.values().get(pk=assessment.pk));review_before=dict(ImpactReview.objects.values().get(pk=review.pk))
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
        from tests.payment_helpers import configure
        from tests.payment_impact795_helpers import fixture
        from tests.helpers import rev
        from apps.finance import payments,invoice_delivery
        from adapters.invoices import InternalInvoiceAdapter
        from apps.policy.services import active_component
        from apps.policy.payment_validators import DENOMINATOR,FUNDS
        from django.apps import apps
        # Explicit canonical local-only worker identity BEFORE native fixture effects.
        self.assertIs(invoice_delivery._LOCAL_ADAPTER,InternalInvoiceAdapter)
        self.assertIs(invoice_delivery._LOCAL_LOOKUP,InternalInvoiceAdapter.lookup)
        self.assertIs(invoice_delivery._LOCAL_DELIVER,InternalInvoiceAdapter.deliver)
        settlement=json.loads((Path(__file__).resolve().parents[1]/'fixtures/finance-settlement.json').read_text())
        self.assertEqual(settlement['adapter']['implementation'],'internal_invoice_register_v1')
        f=fixture()
        configure(f.actor,f.case,f.cov,f.actor,components=[DENOMINATOR,FUNDS])
        payment=payments.assess(f.actor,f.case.pk,f.d.pk,f.cov.pk,rev(f.case))
        from tests.payment_impact795_helpers import assert_predeployment_fixture
        assert_predeployment_fixture(f)
        self.assertIsNone(payment.manifest['context']['deployment_request'])
        self.assertIsNone(payment.manifest['context']['external_ref'])
        old=active_component(FUNDS,f.case)
        new=configure(f.actor,f.case,f.cov,f.actor,components=[FUNDS])[0]
        def effects():
            return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models()
                if m._meta.app_label in ('finance','pmo','core','workflows')}
        # Fixture deliberately creates native synthetic local invoice/cash rows.
        # Read-only impact assertions start only after that setup is complete.
        baseline=effects()
        row=impact.capture(f.actor,f.case.pk,old.pk,new.pk,['finance.payment_assessments'],f.e['policy_decision'].pk,'New payment metadata only')
        rows=row.observation['domains']['finance.payment_assessments'];self.assertEqual([r['id'] for r in rows],[payment.pk])
        self.assertFalse(rows[0]['native_current'])
        for flag in ('assessment_renewed','debt_waived','deployment_authorized','deployment_dispatched','cash_moved'):
            self.assertFalse(rows[0][flag])
        self.assertEqual(set(rows[0]),{'id','kind','metadata_only','domain_route','sha256','dossier','coverage','native_current','state','assessment_renewed','debt_waived','deployment_authorized','deployment_dispatched','cash_moved'})
        unchanged_except_capture_audit(baseline,effects(),actor=f.actor.pk,case=f.case.pk,
            assessment=row.pk,previous=old.pk,successor=new.pk)
        self.assertEqual(dict(ImpactAssessment.objects.values().get(pk=assessment.pk)),before)
        self.assertEqual(dict(ImpactReview.objects.values().get(pk=review.pk)),review_before)
