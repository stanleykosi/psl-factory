"""One-shot native upgrade scenario, excluded from ordinary regression discovery selection.

Requires the reviewed existing empty-business test DB still at policy0017. The
owned harness must gate identity, full raw baseline and runtime clearance first.
There is no reverse migration, custom flush, reseed or primary fixture.
"""
import os
from pathlib import Path
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase


class ApprovalRouteUpgradeTests(TransactionTestCase):
    def test_populated_old_ledger_binding_survives_one_way_upgrade(self):
        from scripts.approval788_upgrade import TARGET, PREVIOUS, upgrade
        from tests.ledger_helpers import fixture, capture, verify
        from tests.test_pilot_preflight import selection
        from tests.test_document_guard import payload
        from tests.helpers import rev
        from apps.policy import pilot, pilot_bindings
        from apps.policy.models import PilotBinding
        self.assertEqual(os.environ.get('RUN788_RUNTIME_CLEARANCE'), 'coordinator-cleared-approval788')
        self.assertEqual(connection.settings_dict['NAME'], 'test_psl_sourceunit777')
        self.assertTrue(connection.get_autocommit())
        self.assertFalse(connection.in_atomic_block)
        applied = MigrationRecorder(connection).applied_migrations()
        self.assertIn(PREVIOUS, applied)
        self.assertNotIn(TARGET, applied)
        root = Path(os.environ['PSL_APPROVAL788_UPGRADE_EVIDENCE'])
        self.assertTrue(root.is_dir())
        self.assertFalse(any(root.iterdir()))
        value=fixture(username='approval788-upgrade',reviewer_username='approval788-reviewer')
        a=value['actor'];b=value['reviewer'];c=value['case'];w=capture(value);x=verify(value,w)
        contract_value=selection(a,c);contract_value['operations']=['ledger.review'];contract_value['participants']=[{'user_id':b.pk,'actions':['ledger.review']}]
        contract=pilot.configure(a,c.pk,contract_value)
        selected=payload(a,c,type('Subject',(),{'pk':1})())
        selected['guards']=[{'operation':'ledger.review','user_id':b.pk,'arguments':{'expected_revision':rev(c),'ledger_check_id':x.pk,'ledger_review_evidence_id':value['e'].pk,'ledger_verdict':'approve'}}]
        binding=pilot_bindings.configure(a,c.pk,contract.pk,selected)
        self.assertEqual(binding.payload['guards'][0]['operation'], 'ledger.review')
        before = dict(PilotBinding.objects.values().get(pk=binding.pk))
        result = upgrade(connection, root)
        self.assertEqual(result['status'], 'EXACT_DECLARED_UPGRADE_ONLY')
        self.assertEqual(dict(PilotBinding.objects.values().get(pk=binding.pk)), before)
        # Exact populated migration preservation above precedes every new fixture.
        # Prove the newly installed SQL/service variant before primary migration.
        from tests.approval_helpers import fixture as approval_fixture
        from adapters.pilot_guards import check
        from apps.pmo.models import ApprovalRouteJob, ApprovalRouteReceipt
        from apps.core.models import Audit
        f=approval_fixture('approval788-post-upgrade');actor=f['actor'];case=f['case']
        contract_value=selection(actor,case);contract_value['operations']=['approval.route']
        contract_value['participants']=[{'user_id':actor.pk,'actions':['approval.route']}]
        approval_contract=pilot.configure(actor,case.pk,contract_value)
        guard={'operation':'approval.route','user_id':actor.pk,'arguments':{'expected_revision':rev(case),'approval_request_id':f['request'].pk,'approval_purpose':'request'}}
        selected=payload(actor,case,type('Subject',(),{'pk':1})());selected['guards']=[guard]
        new_binding=pilot_bindings.configure(actor,case.pk,approval_contract.pk,selected)
        self.assertEqual(new_binding.payload['guards'][0]['operation'],'approval.route')
        # Binding creation is engineering metadata; refresh revision for observation.
        guard['arguments']['expected_revision']=rev(case)
        before_observation=(Audit.objects.count(),rev(case),ApprovalRouteJob.objects.count(),ApprovalRouteReceipt.objects.count())
        observed=check(actor,case,guard)
        self.assertEqual(observed['state'],'READY_AT_OBSERVATION')
        self.assertFalse(observed['business_approval']);self.assertFalse(observed['effects_scheduled'])
        self.assertEqual(before_observation,(Audit.objects.count(),rev(case),ApprovalRouteJob.objects.count(),ApprovalRouteReceipt.objects.count()))
        # TransactionTestCase's ordinary teardown removes only this isolated test
        # fixture. Its raw after-state must be checked against the upgraded empty
        # baseline by the wrapper. The migration marker/function remain installed.
