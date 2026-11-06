"""Real independent source/control/target PostgreSQL processes; no internal service mocks."""
import base64
import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from django.conf import settings
from django.test import SimpleTestCase
from django.db import connections
from psycopg import sql
from adapters import native_application_archive as n


class ColdRecoveryTests(SimpleTestCase):
    @classmethod
    def child(cls, stage, value, database, cold=True):
        env = os.environ.copy()
        env.update(PGDATABASE=database, DJANGO_SETTINGS_MODULE='config.cold_settings' if cold else 'config.settings')
        result = subprocess.run([sys.executable, '-m', 'tests.cold_recovery_scenario', stage],
            input=json.dumps(value), text=True, capture_output=True, env=env, timeout=300)
        if result.returncode:
            raise AssertionError(f'{stage} failed\n{result.stdout}\n{result.stderr}')
        return json.loads(result.stdout.strip().splitlines()[-1])

    @classmethod
    def provision(cls, name, template=False):
        assert name.startswith(('psl_fixture_source_', 'psl_cold_', 'test_psl_recovery_'))
        if template:
            # Copy schema/framework definitions only. Refuse any test business/authority rows.
            with n.connect('test_psl') as db:
                for table in n.tables(db):
                    if table not in {'django_migrations','auth_permission','django_content_type'}:
                        assert db.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0] == 0, table
            connections['default'].close()
        with n.connect() as db:
            db.autocommit = True
            assert not db.execute('SELECT 1 FROM pg_database WHERE datname=%s', [name]).fetchone()
            statement = sql.SQL('CREATE DATABASE {} TEMPLATE test_psl') if template else sql.SQL('CREATE DATABASE {}')
            db.execute(statement.format(sql.Identifier(name)))

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.directory = TemporaryDirectory(prefix='cold-recovery-', dir=settings.BASE_DIR / '.runtime')
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        cls.root = root
        cls.source = 'psl_fixture_source_' + uuid4().hex[:14]
        cls.control = 'psl_cold_' + uuid4().hex[:14]
        cls.provision(cls.source, template=True)
        cls.provision(cls.control, template=True)
        for label in ['archives', 'attachments', 'old-target-files']:
            (root / label).mkdir()
        cls.value = {'root': str(root), 'key': base64.b64encode(os.urandom(32)).decode(),
            'secret': base64.b64encode(os.urandom(32)).decode(), 'source': cls.source, 'control': cls.control,
            'pg_bin': str(settings.BASE_DIR / '.runtime/pgsql/bin'),'with_native_validation':True,'with_private_impact':True,'with_role_eligibility':True,'with_document_guard':True,'with_role_guard':True,'with_clock_guard':True}
        archive = cls.child('source', cls.value, cls.source, cold=False)
        cls.value['archive'] = archive
        # Only the new owned synthetic source is made unavailable; no operational/test DB changed.
        with n.connect() as db:
            db.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(sql.Identifier(cls.source)))
        cls.child('initialize', cls.value, cls.control)

    def scenario(self, stage):
        v = copy.deepcopy(self.value)
        v['target'] = 'test_psl_recovery_' + uuid4().hex[:18]
        self.provision(v['target'])
        files = self.root / v['target']
        files.mkdir()
        v['target_files'] = str(files)
        return v, self.child(stage, v, self.control)

    def test_fresh_ui_policy_scope_agent_and_sql_guards_without_source(self):
        _, result = self.scenario('controls')
        self.assertTrue(result['source_unavailable'])
        self.assertTrue(result['missing_policy_capture'])
        self.assertTrue(result['sql_guards'])

    def test_actual_native_sql_failure_commit_loss_and_fresh_process_reconciliation(self):
        v, prepared = self.scenario('crash')
        v.update(prepared)
        recovered = self.child('reconcile', v, self.control)
        self.assertEqual(recovered['attempts'], 3)
        self.assertTrue(recovered['physical_receipt_current'])
        self.assertFalse(recovered['authorization_current'])

    def test_duplicate_reservations_workers_and_independent_recovered_review(self):
        _, result = self.scenario('concurrency')
        self.assertEqual(result['jobs'], 1)
        self.assertEqual(result['attempts'], 1)
        self.assertTrue(result['human_recovered_review_current'])
        self.assertTrue(result['physical_tamper_invalidated'])
        self.assertTrue(result['impact_history_preserved'])
        self.assertTrue(result['pilot_history_preserved'])
        self.assertTrue(result['pilot_bindings_history_preserved'])
        self.assertTrue(result['native_validation_history_preserved'])
        self.assertTrue(result['private_impact_history_preserved'])
        self.assertTrue(result['role_eligibility_history_preserved'])
        self.assertTrue(result['document_guard_history_preserved'])
        self.assertTrue(result['role_guard_history_preserved'])
        self.assertTrue(result['clock_guard_history_preserved'])

    def test_revoked_expired_forged_and_cross_purpose_authority(self):
        _, result = self.scenario('authority')
        self.assertTrue(result['authority_rejected'])

    def test_preexisting_people_cannot_bootstrap_fresh_control_identity(self):
        value=copy.deepcopy(self.value)
        value['control']='psl_cold_'+uuid4().hex[:16]
        self.provision(value['control'],template=True)
        result=self.child('reject_bootstrap',value,value['control'])
        self.assertTrue(result['preexisting_people_rejected'])
