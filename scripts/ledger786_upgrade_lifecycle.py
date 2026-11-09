"""One-shot native upgrade scenario, excluded from ordinary regression discovery selection.

Requires the reviewed existing empty-business test DB still at policy0016. The
owned harness must gate identity, full raw baseline and runtime clearance first.
There is no reverse migration, custom flush, reseed or primary fixture.
"""
import os
from pathlib import Path
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase


class LedgerReviewUpgradeTests(TransactionTestCase):
    def test_populated_old_pmo_binding_survives_one_way_upgrade(self):
        from scripts.ledger786_upgrade import TARGET, PREVIOUS, upgrade
        from tests.test_pilot_bindings import fixture
        from apps.policy.models import PilotBinding
        self.assertEqual(os.environ.get('RUN786_RUNTIME_CLEARANCE'), 'coordinator-cleared-ledger786')
        self.assertEqual(connection.settings_dict['NAME'], 'test_psl_sourceunit777')
        self.assertTrue(connection.get_autocommit())
        self.assertFalse(connection.in_atomic_block)
        applied = MigrationRecorder(connection).applied_migrations()
        self.assertIn(PREVIOUS, applied)
        self.assertNotIn(TARGET, applied)
        root = Path(os.environ['PSL_LEDGER786_UPGRADE_EVIDENCE'])
        self.assertTrue(root.is_dir())
        self.assertFalse(any(root.iterdir()))
        value = fixture(prefix='ledger786-upgrade')
        binding = value['binding']
        self.assertEqual(binding.payload['guards'][0]['operation'], 'pmo.decision.record')
        before = dict(PilotBinding.objects.values().get(pk=binding.pk))
        result = upgrade(connection, root)
        self.assertEqual(result['status'], 'EXACT_DECLARED_UPGRADE_ONLY')
        self.assertEqual(dict(PilotBinding.objects.values().get(pk=binding.pk)), before)
        # TransactionTestCase's ordinary teardown removes only this isolated test
        # fixture. Its raw after-state must be checked against the upgraded empty
        # baseline by the wrapper. The migration marker/function remain installed.
