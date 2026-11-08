"""One-shot native upgrade scenario, excluded from ordinary regression discovery selection.

Requires the reviewed existing empty-business test DB still at policy0018. The
owned harness must gate identity, full raw baseline and runtime clearance first.
There is no reverse migration, custom flush, reseed or primary fixture.
"""
import os
from pathlib import Path
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase


class PlanningReadinessUpgradeTests(TransactionTestCase):
    def test_populated_old_approval_binding_survives_one_way_upgrade(self):
        from scripts.planning789_upgrade import TARGET, PREVIOUS, upgrade
        from tests.approval_helpers import fixture as approval_fixture
        from tests.test_pilot_preflight import selection
        from tests.test_document_guard import payload
        from tests.helpers import rev
        from apps.policy import pilot, pilot_bindings
        from apps.policy.models import PilotBinding
        self.assertEqual(os.environ.get('RUN789_RUNTIME_CLEARANCE'), 'coordinator-cleared-planning789')
        self.assertEqual(connection.settings_dict['NAME'], 'test_psl_sourceunit777')
        self.assertTrue(connection.get_autocommit())
        self.assertFalse(connection.in_atomic_block)
        applied = MigrationRecorder(connection).applied_migrations()
        self.assertIn(PREVIOUS, applied)
        self.assertNotIn(TARGET, applied)
        root = Path(os.environ['PSL_PLANNING789_UPGRADE_EVIDENCE'])
        self.assertTrue(root.is_dir())
        self.assertFalse(any(root.iterdir()))
        value=approval_fixture('planning789-old-approval');a=value['actor'];c=value['case']
        contract_value=selection(a,c);contract_value['operations']=['approval.route'];contract_value['participants']=[{'user_id':a.pk,'actions':['approval.route']}]
        contract=pilot.configure(a,c.pk,contract_value)
        selected=payload(a,c,type('Subject',(),{'pk':1})())
        selected['guards']=[{'operation':'approval.route','user_id':a.pk,'arguments':{'expected_revision':rev(c),'approval_request_id':value['request'].pk,'approval_purpose':'request'}}]
        binding=pilot_bindings.configure(a,c.pk,contract.pk,selected)
        self.assertEqual(binding.payload['guards'][0]['operation'],'approval.route')
        before = dict(PilotBinding.objects.values().get(pk=binding.pk))
        result = upgrade(connection, root)
        self.assertEqual(result['status'], 'EXACT_DECLARED_UPGRADE_ONLY')
        self.assertEqual(dict(PilotBinding.objects.values().get(pk=binding.pk)), before)
        # Exact populated migration preservation above precedes every new fixture.
        # Prove the newly installed SQL/service variant before primary migration.
        from tests.planning_helpers import fixture as planning_fixture, observe
        from adapters.pilot_guards import check
        from apps.core.models import Audit, Evidence
        from apps.workflows.models import Outbox
        f=planning_fixture(username='planning789-post-upgrade');observe(f);actor=f['a'];case=f['c']
        contract_value=selection(actor,case);contract_value['operations']=['planning.readiness']
        contract_value['participants']=[{'user_id':actor.pk,'actions':['planning.prepare']}]
        new_contract=pilot.configure(actor,case.pk,contract_value)
        guard={'operation':'planning.readiness','user_id':actor.pk,'arguments':{'expected_revision':rev(case),'planning_packet_id':f['packet'].pk}}
        selected=payload(actor,case,type('Subject',(),{'pk':1})());selected['guards']=[guard]
        new_binding=pilot_bindings.configure(actor,case.pk,new_contract.pk,selected)
        self.assertEqual(new_binding.payload['guards'][0]['operation'],'planning.readiness')
        guard['arguments']['expected_revision']=rev(case)
        before_observation=(Audit.objects.count(),rev(case),Evidence.objects.count(),Outbox.objects.count())
        observed=check(actor,case,guard)
        self.assertEqual(observed['state'],'READY_AT_OBSERVATION')
        self.assertFalse(observed['business_approval']);self.assertFalse(observed['effects_scheduled'])
        self.assertEqual(before_observation,(Audit.objects.count(),rev(case),Evidence.objects.count(),Outbox.objects.count()))
        # TransactionTestCase's ordinary teardown removes only this isolated test
        # fixture. Its raw after-state must be checked against the upgraded empty
        # baseline by the wrapper. The migration marker/function remain installed.
