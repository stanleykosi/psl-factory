import base64
import copy
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, Event
from unittest.mock import patch
from uuid import uuid4

import psycopg
from psycopg import sql
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction, close_old_connections, DatabaseError
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import register_reference, transition
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.application_recovery_validators import COMPONENT, SCHEMA, validate_reference
from apps.workflows import application_recovery as d
from apps.workflows.application_recovery_models import ApplicationRecoveryJob as Job, ApplicationRecoveryReview as Review
from apps.agents import application_recovery as agent
from apps.agents.models import AgentRun
from adapters import native_application_archive as native
from .helpers import setup_case, activate


class RecoveryFixture:
    def fixture(self, configured=True, attachment=True, target=False):
        self.a, self.c = setup_case(username='archive-' + uuid4().hex[:12])
        self.b = get_user_model().objects.create_user(username='archive-review-' + uuid4().hex[:12])
        for actor in [self.a, self.b]:
            for action in ['case.read', 'recovery.read', 'recovery.database', 'recovery.capture', 'recovery.operate', 'recovery.review', 'recovery.agent', 'recovery.attachment']:
                Grant.objects.get_or_create(user=actor, case=self.c, action=action)
        self.root = Path(self.enterContext(TemporaryDirectory(prefix='application-recovery-', dir=settings.BASE_DIR / '.runtime')))
        roots = [self.root / p for p in ['archives', 'attachments', 'restored-attachments']]
        for p in roots:
            p.mkdir()
        self.target = 'test_psl_recovery_' + uuid4().hex[:16]
        self.runtime = {'sources': {'synthetic-source': {'database': connection.settings_dict['NAME'], 'archives': str(roots[0]), 'attachments': str(roots[1]), 'revision': 'synthetic-v1'}},
                        'targets': {'synthetic-target': {'database': self.target, 'attachments': str(roots[2]), 'revision': 'synthetic-v1'}},
                        'keys': {'test-key': os.urandom(32)}, 'principals': [self.a.pk, self.b.pk],
                        'build_ref': 'synthetic-reviewed-build-v1', 'pg_bin': str(settings.BASE_DIR / '.runtime/pgsql/bin')}
        self.enterContext(override_settings(APPLICATION_RECOVERY=self.runtime))
        self.ev = add_evidence(self.a, self.c.pk, 'policy_decision', 'Explicit synthetic recovery configuration; no actual owner appointment', 'synthetic:native-archive')
        refs = [register_reference(self.a, self.c.pk, 'archive-role:' + str(a.pk), 'schema:psl/role-assignment/v1', {'user_id': a.pk, 'role': role}, self.ev.pk).ref for a, role in [(self.a, 'PM'), (self.b, 'PMO')]]
        activate(self.a, self.c, 'D05.role_principal_assignments', refs, self.ev)
        self.attachment = d.attach(self.a, self.c.pk, 'synthetic-source', 'Synthetic managed attachment', b'synthetic attachment bytes') if attachment else None
        self.values = dict(source_ref='synthetic-source', target_ref='synthetic-target', key_ref='test-key', operator_id=self.a.pk, operator_role='PM', reviewer_id=self.b.pk, reviewer_role='PMO',
                           attachment_ids=[self.attachment.pk] if self.attachment else [], max_archive_bytes=33554432, max_attachment_bytes=1048576,
                           max_seconds=30, lease_seconds=180, max_attempts=2, retention_days=7, authorization_valid_seconds=3600, archive_valid_seconds=3600, allow_synthetic=True)
        self.plan = d.capture(self.a, self.c.pk, 'native-application', {k: self.values[k] for k in ['source_ref', 'target_ref', 'key_ref']})
        if configured:
            self.configure()
        if target:
            self.provision(self.target)
        return self.plan

    def configure(self, changes=None):
        self.config = draft_operator_policy(self.a, self.c.pk, COMPONENT, {**self.values, **(changes or {})}, self.ev.pk, timezone.now() - timedelta(seconds=1))
        transition(self.a, self.config.pk, 'validated')
        transition(self.a, self.config.pk, 'active')
        return self.config

    def authorize(self, key='authorization'):
        return d.review(self.b, self.c.pk, self.plan.pk, 'authorize', 'approve', 'Synthetic independent review of exact source/target/key and configured limits', key)

    def provision(self, name):
        assert connection.settings_dict['NAME'] == 'test_psl' and name.startswith('test_psl_recovery_')
        args = connection.get_connection_params()
        with psycopg.connect(**args, autocommit=True) as db:
            assert not db.execute('SELECT 1 FROM pg_database WHERE datname=%s', [name]).fetchone()
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))

    def effect(self, kind):
        job = d.reserve(self.a, self.c.pk, self.plan.pk, kind)
        self.assertTrue(d.run_once())
        job.refresh_from_db()
        self.assertEqual(job.status, 'confirmed', job.error)
        return job


class ApplicationRecoveryPolicyTests(RecoveryFixture, TestCase):
    def test_actual_http_policy_activation_human_authorization_queue_and_live_guidance(self):
        self.fixture(configured=False, attachment=False)
        self.client.force_login(self.a)
        url = reverse('application_recovery', args=[self.c.pk])
        self.assertEqual(self.client.post(url, {'action': 'capture', 'reference': 'ui-native', **self.plan.payload}).status_code, 302)
        p = d.Plan.objects.get(case=self.c, reference='ui-native')
        self.assertEqual(self.client.post(url, {'action': 'policy', 'content': json.dumps(self.values), 'evidence_id': self.ev.pk}).status_code, 302)
        from apps.policy.models import Configuration
        config = Configuration.objects.get(case=self.c, component=COMPONENT)
        for state in ['validated', 'active']:
            self.assertEqual(self.client.post(reverse('policy', args=[self.c.pk]), {'action': state, 'configuration': config.pk}).status_code, 302)
        self.client.force_login(self.b)
        self.assertEqual(self.client.post(url, {'action': 'review', 'plan': p.pk, 'phase': 'authorize', 'decision': 'approve', 'rationale': 'Synthetic independent native UI authorization', 'operation_key': 'ui-authorize'}).status_code, 302)
        self.client.force_login(self.a)
        self.assertEqual(self.client.post(url, {'action': 'reserve', 'plan': p.pk, 'kind': 'archive'}).status_code, 302)
        self.assertEqual(Job.objects.get(plan=p, kind='archive').status, 'pending')
        count = AgentRun.objects.count()
        response = self.client.post(url, {'action': 'investigate', 'plan': p.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['effect_tools'], [])
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(AgentRun.objects.count(), count)
        Grant.objects.filter(user=self.b, action='recovery.database').update(active=False)
        self.assertFalse(d.report(self.a, self.c.pk, p.pk)['authorization_current'])
        with self.assertRaises(PermissionDenied): d.reserve(self.a, self.c.pk, p.pk, 'archive')

    def test_narrow_cast_canonicalisation_preserves_real_schema_differences(self):
        before = "CHECK (x = ANY ((ARRAY['confirm'::character varying, 'return'::character varying])::text[]))"
        after = "CHECK (x = ANY (ARRAY[('confirm'::character varying)::text, ('return'::character varying)::text]))"
        self.assertEqual(native.canonical_definition(before), after)
        self.assertNotEqual(native.canonical_definition(before.replace('confirm', 'hold')), after)
        for value in [before.replace('character varying', 'character varying(3)'), "CHECK (x = ANY ((ARRAY[function_call()])::text[]))", 'CHECK (amount > 0)']:
            self.assertEqual(native.canonical_definition(value), value)
    def test_capture_missing_policy_typed_validation_ui_agent_and_private_scope(self):
        self.fixture(configured=False)
        self.assertEqual(d.capture(self.a, self.c.pk, self.plan.reference, self.plan.payload).pk, self.plan.pk)
        with self.assertRaises(ValidationError):
            d.reserve(self.a, self.c.pk, self.plan.pk, 'archive')
        self.client.force_login(self.a)
        url = reverse('application_recovery', args=[self.c.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'MISSING')
        self.assertContains(response, 'Synthetic managed attachment')
        self.assertContains(response, self.attachment.sha256)
        self.assertEqual(response['Cache-Control'], 'no-store')
        for changes in [{'reviewer_id': self.a.pk}, {'max_seconds': 0}, {'attachment_ids': [1, 1]}, {'lease_seconds': 10}, {'max_archive_bytes': None}, {'arbitrary_shell': 'forbidden'}, {'allow_synthetic': False}]:
            bad = type('Reference', (), {'schema_ref': SCHEMA, 'content': {**self.values, **changes}})()
            with self.assertRaises(ValidationError):
                validate_reference(COMPONENT, bad, self.c)
        self.configure()
        with self.assertRaises(ValidationError):
            d.reserve(self.a, self.c.pk, self.plan.pk, 'archive')
        with self.assertRaises(PermissionDenied):
            d.review(self.a, self.c.pk, self.plan.pk, 'authorize', 'approve', 'forbidden self review', 'self')
        self.authorize()
        authorization = Review.objects.filter(plan=self.plan, phase='authorize').last()
        with patch('apps.workflows.application_recovery.timezone.now', return_value=authorization.created_at + timedelta(seconds=self.values['authorization_valid_seconds'] + 1)):
            with self.assertRaises(ValidationError):
                d.reserve(self.a, self.c.pk, self.plan.pk, 'archive')
        count = AgentRun.objects.count()
        self.assertEqual(agent.prepare(self.a, self.c.pk, self.plan.reference, **self.plan.payload).pk, self.plan.pk)
        result = agent.investigate(self.a, self.c.pk, self.plan.pk)
        self.assertEqual(result['effect_tools'], [])
        self.assertFalse(result['production_activation'])
        self.assertEqual(AgentRun.objects.count(), count)
        other = Case.objects.create(tenant='private-foreign', title='Foreign private data', kind='support', synthetic=True)
        with self.assertRaises(PermissionDenied):
            agent.investigate(self.a, self.c.pk, self.plan.pk)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(reverse('application_recovery_report', args=[self.c.pk, self.plan.pk])).status_code, 403)

    def test_policy_lifecycle_runtime_identity_and_sql_immutability(self):
        self.fixture()
        self.authorize()
        for action in [lambda: d.Plan.objects.filter(pk=self.plan.pk).update(payload={}), lambda: Review.objects.filter(plan=self.plan).update(decision='hold'), lambda: d.Attachment.objects.filter(pk=self.attachment.pk).delete()]:
            with self.assertRaises(DatabaseError), transaction.atomic():
                action()
        job = d.reserve(self.a, self.c.pk, self.plan.pk, 'archive')
        with self.assertRaises(DatabaseError), transaction.atomic():
            Job.objects.filter(pk=job.pk).update(intent={**job.intent, 'kind': 'restore'})
        with self.assertRaises(DatabaseError), transaction.atomic():
            Job.objects.filter(pk=job.pk).update(status='confirmed', receipt={'format': native.FORMAT, 'live_authority_restored': True})
        with self.assertRaises(ValidationError):
            d.review(self.b, self.c.pk, self.plan.pk, 'recovered', 'approve', 'No actual restore', 'missing')
        changed = copy.deepcopy(self.runtime)
        changed['targets']['synthetic-target']['database'] = connection.settings_dict['NAME']
        with override_settings(APPLICATION_RECOVERY=changed), self.assertRaises(ValidationError):
            native.runtime(self.values)
        changed = copy.deepcopy(self.runtime)
        changed['keys']['test-key'] = os.urandom(32)
        with override_settings(APPLICATION_RECOVERY=changed), self.assertRaises(ValidationError):
            d.reserve(self.a, self.c.pk, self.plan.pk, 'archive')
        transition(self.a, self.config.pk, 'revoked')
        self.assertTrue(d.run_once())
        job.refresh_from_db()
        self.assertEqual(job.status, 'held')


class NativeApplicationRecoveryTests(RecoveryFixture, TransactionTestCase):
    def test_concurrent_foreign_case_cannot_enter_authorized_ui_inventory(self):
        self.fixture(configured=False)
        self.client.force_login(self.a)
        ready, proceed = Event(), Event()
        url = reverse('application_recovery', args=[self.c.pk])
        def request():
            close_old_connections()
            paused = False
            def gate(execute, statement, params, many, context):
                nonlocal paused
                if not paused and statement.lstrip().upper().startswith('SELECT') and '"workflows_recoveryattachment"' in statement:
                    paused = True
                    ready.set()
                    if not proceed.wait(15): raise AssertionError('Concurrent attachment fixture did not finish')
                return execute(statement, params, many, context)
            try:
                with connection.execute_wrapper(gate):
                    response = self.client.get(url)
                    return response.status_code, response.content.decode()
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as executor:
            result = executor.submit(request)
            self.assertTrue(ready.wait(15))
            try:
                other = get_user_model().objects.create_user(username='foreign-inventory-' + uuid4().hex[:12])
                case = Case.objects.create(tenant='foreign-private', title='FOREIGN_PRIVATE_NEW_CASE', kind='support', synthetic=True)
                Grant.objects.bulk_create([Grant(user=other, case=case, action=a) for a in ['case.read', 'recovery.attachment']])
                d.attach(other, case.pk, 'synthetic-source', 'FOREIGN_PRIVATE_NEW_ATTACHMENT', b'actual foreign managed attachment bytes')
            finally:
                proceed.set()
            status, body = result.result(timeout=30)
        self.assertEqual(status, 200)
        self.assertIn('Synthetic managed attachment', body)
        self.assertNotIn('FOREIGN_PRIVATE_NEW_CASE', body)
        self.assertNotIn('FOREIGN_PRIVATE_NEW_ATTACHMENT', body)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_real_archive_isolated_restore_human_review_and_physical_counterexamples(self):
        self.fixture(target=True)
        self.authorize()
        self.client.force_login(self.a)
        self.assertGreater(Grant.objects.count(), 0)
        archive = self.effect('archive')
        package, archive_sha = native.read_archive(archive.intent)
        self.assertTrue(base64.b64decode(package['dump']).startswith(b'PGDMP'))
        self.assertTrue(all(u['password'] == '!' and not u['is_active'] for u in package['users']))
        self.assertEqual(package['manifest']['tables']['django_session'][0], 0)
        self.assertEqual(package['manifest']['tables']['identity_grant'][0], 0)
        self.assertEqual(package['manifest']['attachments'][0]['sha256'], self.attachment.sha256)
        pending = d.reserve(self.a, self.c.pk, self.plan.pk, 'restore')
        _, _, key, roots, _ = native.runtime(self.values)
        path = native.archive_path(archive.intent, roots)
        original_sealed = path.read_bytes()
        for kind in ['wrong_type', 'wrong_build', 'missing_attachment', 'wrong_dump']:
            bad = copy.deepcopy(package)
            if kind == 'wrong_type': bad['manifest']['format'] = 'portable_metadata_v1'
            if kind == 'wrong_build': bad['manifest']['build_sha256'] = '0' * 64
            if kind == 'missing_attachment': bad['files'] = []
            if kind == 'wrong_dump': bad['dump'] = base64.b64encode(b'not a native PostgreSQL dump').decode()
            path.write_bytes(native.seal(archive.intent, bad, key))
            with self.assertRaises(ValidationError): native.restore(pending.intent, archive.intent)
            path.write_bytes(original_sealed)
        with native.connect(self.target) as db:
            self.assertEqual(native.tables(db), [])
        restored = self.effect('restore')
        self.assertTrue(restored.receipt['schema_and_rows_verified'])
        self.assertFalse(restored.receipt['live_authority_restored'])
        self.assertFalse(restored.receipt['operational_acceptance'])
        with native.connect(self.target) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM identity_grant').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT count(*) FROM auth_user WHERE is_active OR password<>%s', ['!']).fetchone()[0], 0)
            self.assertEqual(native.inventory(db), package['manifest']['tables'])
        decision = d.review(self.b, self.c.pk, self.plan.pk, 'recovered', 'approve', 'Exact recovered rows/schema/functions/managed attachment bytes verified; no deployment authority', 'recovery-owner')
        self.assertEqual(decision.pin['recovery_receipt_sha256'], native.digest(restored.receipt))
        report = d.report(self.a, self.c.pk, self.plan.pk)
        self.assertTrue(all(j['physical_receipt_current'] for j in report['jobs']))
        self.assertTrue(report['human_recovery_review_current'])
        from adapters.pilot_physical import read as physical
        from apps.policy import pilot
        from tests.test_pilot_preflight import selection
        projection=physical(self.a,self.c,'application',restored.pk)
        self.assertTrue(projection['receipt_verified']);self.assertTrue(projection['recovery_evidence']['native_restore_verified'])
        self.assertFalse(projection['recovery_evidence']['live_authority_restored'])
        p=selection(self.a,self.c);p['jobs']=[{'family':'application','id':restored.pk}]
        selected=pilot.configure(self.a,self.c.pk,p);pack=pilot.capture(self.a,self.c.pk,selected.pk)
        self.assertTrue(pilot.inspect(self.a,self.c.pk,pack.pk)['current'])
        self.a.refresh_from_db()
        self.assertTrue(self.a.is_active)
        self.assertTrue(Grant.objects.filter(user=self.a, active=True).exists())
        env = os.environ.copy()
        env['PGDATABASE'] = self.target
        isolated = subprocess.run([sys.executable, 'manage.py', 'check'], env=env, capture_output=True, text=True, timeout=20)
        self.assertNotEqual(isolated.returncode, 0)
        self.assertIn('quarantined', isolated.stderr.lower())
        # No cached SQL receipt can hide missing/corrupt physical evidence.
        _, _, _, roots, _ = native.runtime(self.values)
        file = roots[2] / self.attachment.sha256
        raw = file.read_bytes()
        file.unlink()
        self.assertFalse(physical(self.a,self.c,'application',restored.pk)['receipt_verified'])
        self.assertFalse(pilot.inspect(self.a,self.c.pk,pack.pk)['current'])
        with self.assertRaises(ValidationError):
            d.lookup(restored)
        file.write_bytes(raw)
        path = native.archive_path(archive.intent, roots)
        sealed = path.read_bytes()
        path.write_bytes(sealed[:-1] + bytes([sealed[-1] ^ 1]))
        with self.assertRaises(ValidationError):
            d.lookup(archive)
        path.write_bytes(sealed)
        self.assertEqual(d.lookup(archive)['archive_sha256'], archive_sha)
        path.unlink()
        with patch('adapters.native_application_archive.source_archive', side_effect=AssertionError('Lookup must not recapture')):
            self.assertIsNone(d.lookup(archive))
        path.write_bytes(sealed)
        # A nonempty unrelated target is held and its rows are untouched.
        other = 'test_psl_recovery_' + uuid4().hex[:16]
        self.provision(other)
        other_root = self.root / 'other-target'
        other_root.mkdir()
        self.runtime['targets']['other-target'] = {'database': other, 'attachments': str(other_root), 'revision': 'synthetic-v1'}
        with native.connect(other) as db:
            db.execute('CREATE TABLE untouched_marker(value text)')
            db.execute("INSERT INTO untouched_marker VALUES ('preserve')")
        candidate = copy.deepcopy(restored.intent)
        candidate['rules']['target_ref'] = 'other-target'
        candidate['runtime_sha256'] = native.runtime(candidate['rules'])[-1]
        with self.assertRaises(ValidationError):
            native.restore(candidate, archive.intent)
        with native.connect(other) as db:
            self.assertEqual(db.execute('SELECT value FROM untouched_marker').fetchall(), [('preserve',)])
        # Source database is deliberately unavailable in this independent process.
        runtime = copy.deepcopy(self.runtime)
        runtime['keys'] = {k: base64.b64encode(v).decode() for k, v in runtime['keys'].items()}
        code = "import sys,json,base64,os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; import django; django.setup(); from django.conf import settings; r=json.load(sys.stdin); r['keys']={k:base64.b64decode(v) for k,v in r['keys'].items()}; settings.APPLICATION_RECOVERY=r; from adapters.native_application_archive import inspect_offline; print(json.dumps(inspect_offline('synthetic-source',sys.argv[1])))"
        env['PGDATABASE'] = 'psl_unavailable_synthetic_recovery'
        offline = subprocess.run([sys.executable, '-c', code, archive.operation_key], input=json.dumps(runtime), text=True, capture_output=True, env=env, timeout=30)
        self.assertEqual(offline.returncode, 0, offline.stderr)
        inspected = json.loads(offline.stdout)
        self.assertEqual(inspected['archive_sha256'], archive_sha)
        self.assertFalse(inspected['source_database_needed'])
        self.assertFalse(inspected['restoration_authorized'])
        with native.connect(self.target) as db:
            db.execute("SELECT setval('public.auth_user_id_seq',1,true)")
        with self.assertRaisesRegex(ValidationError, 'sequence'):
            d.lookup(restored)
        # Extra predicate is a real schema change, never hidden by cast normalization.
        with native.connect(self.target) as db:
            db.execute('ALTER TABLE public.core_case ADD CONSTRAINT synthetic_tampered_revision CHECK (revision>1) NOT VALID')
        with self.assertRaisesRegex(ValidationError, 'schema/constraints'):
            d.lookup(restored)
        with native.connect(self.target) as db:
            db.execute('UPDATE public.core_case SET revision=revision+1')
        with self.assertRaisesRegex(ValidationError, 'row inventory'):
            d.lookup(restored)
        with native.connect(self.target) as db:
            db.execute('CREATE SCHEMA synthetic_unexpected')
        with self.assertRaisesRegex(ValidationError, 'unexpected schemas'):
            d.lookup(restored)
        # The owned target is intentionally left invalid; no schema/DB reset.

    def test_real_duplicate_workers_and_fresh_process_receipt_first_after_revocation(self):
        self.fixture(target=True)
        self.authorize()
        barrier = Barrier(2)
        def reserve():
            close_old_connections()
            a = get_user_model().objects.get(pk=self.a.pk)
            barrier.wait()
            try:
                return d.reserve(a, self.c.pk, self.plan.pk, 'archive').pk
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            ids = list(executor.map(lambda _: reserve(), range(2)))
        self.assertEqual(ids[0], ids[1])
        barrier = Barrier(2)
        def worker():
            close_old_connections()
            barrier.wait()
            try:
                return d.run_once()
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(lambda _: worker(), range(2)))
        archive = Job.objects.get(pk=ids[0])
        self.assertEqual(archive.status, 'confirmed')
        self.assertEqual(archive.attempts, 1)
        restore = d.reserve(self.a, self.c.pk, self.plan.pk, 'restore')
        original_cli = native.cli
        def fail_post_data(command, arguments, database, timeout):
            if command == 'psql':
                receipt = Path(next(a.split('=', 1)[1] for a in arguments if a.endswith('receipt.sql')))
                with receipt.open('a', encoding='utf-8') as out:
                    out.write('\nSELECT 1/0;\n')
            return original_cli(command, arguments, database, timeout)
        with patch('adapters.native_application_archive.cli', side_effect=fail_post_data):
            self.assertTrue(d.run_once())
        restore.refresh_from_db()
        self.assertEqual(restore.status, 'held')
        with native.connect(self.target) as db:
            self.assertEqual(native.tables(db), [])
            self.assertEqual(db.execute("SELECT current_setting('psl.recovery_quarantined')").fetchone()[0], 'on')
        self.assertIsNone(d.lookup(restore))
        self.client.force_login(self.a)
        response = self.client.post(reverse('application_recovery', args=[self.c.pk]), {'action': 'retry', 'job': restore.pk})
        self.assertEqual(response.status_code, 302)
        # Fault injection only at post-effect persistence: native SQL/files actually commit.
        with patch('apps.workflows.application_recovery.finish', side_effect=RuntimeError('simulated process loss after native commit')):
            with self.assertRaises(RuntimeError):
                d.run_once()
        restore.refresh_from_db()
        self.assertEqual(restore.status, 'leased')
        physical = d.lookup(restore)
        self.assertIsNotNone(physical)
        Grant.objects.filter(user=self.a, action='recovery.operate').update(active=False)
        Job.objects.filter(pk=restore.pk).update(lease_until=timezone.now() - timedelta(seconds=1))
        runtime = copy.deepcopy(self.runtime)
        runtime['keys'] = {k: base64.b64encode(v).decode() for k, v in runtime['keys'].items()}
        code = "import sys,json,base64,os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; import django; django.setup(); from django.conf import settings; r=json.load(sys.stdin); r['keys']={k:base64.b64decode(v) for k,v in r['keys'].items()}; settings.APPLICATION_RECOVERY=r; from apps.workflows.application_recovery import run_once; assert run_once()"
        env = os.environ.copy()
        env['PGDATABASE'] = 'test_psl'
        child = subprocess.run([sys.executable, '-c', code], input=json.dumps(runtime), text=True, capture_output=True, env=env, timeout=60)
        self.assertEqual(child.returncode, 0, child.stderr)
        restore.refresh_from_db()
        self.assertEqual(restore.status, 'confirmed')
        self.assertEqual(restore.attempts, 3)  # Receipt recovery precedes the original two-attempt limit.
        self.assertEqual(restore.receipt, physical)
        self.assertEqual(Job.objects.filter(plan=self.plan, kind='restore').count(), 1)
        self.assertFalse(Grant.objects.get(user=self.a, case=self.c, action='recovery.operate').active)
