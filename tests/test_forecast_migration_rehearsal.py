"""Populated 0077 rehearsal. Run only against the Django PostgreSQL test database."""
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from time import perf_counter, sleep

from django.db import DatabaseError, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase

from apps.core.evidence_access import public_evidence
from apps.core.models import Case, Evidence
from apps.finance.models import ForecastEvidenceReference, ForecastScenario
from .forecast_helpers import scenario
from .helpers import setup_case


PREVIOUS = ('finance', '0076_obligation_trigger_alias_repair')
UPGRADE = ('finance', '0077_forecast_evidence_reference')


class ForecastMigrationRehearsalTests(TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        self.leaves = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(self.leaves))
        executor.migrate([PREVIOUS])
        self.actor, self.anchor = setup_case()
        scenario(self.actor, self.anchor)

    def fingerprint(self):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT count(*), md5(string_agg(row_to_json(s)::text, '' ORDER BY id))
                FROM finance_forecastscenario s
            """)
            return cursor.fetchone()

    def add_scenario(self, reference, evidence, items):
        return ForecastScenario.objects.create(
            case=self.anchor, reference=reference, number=1, evidence=evidence,
            payload={'items': items}, reason='Synthetic migration rehearsal', actor=self.actor,
        )

    def test_populated_backfill_fences_writes_and_preserves_privacy(self):
        cases = Case.objects.bulk_create([
            Case(tenant=f'rehearsal-{n % 8}', title=f'Synthetic forecast case {n}', kind='project', synthetic=True)
            for n in range(64)
        ])
        sources = Evidence.objects.bulk_create([
            Evidence(case=case, kind='policy_decision', version=n + 1, body='Synthetic forecast source',
                     source='synthetic:rehearsal', sha256='0' * 64, created_by=self.actor)
            for case in cases for n in range(24)
        ])
        rows = []
        expected_links = 0
        hidden = set()
        for index, case in enumerate(cases):
            case_sources = sources[index * 24:(index + 1) * 24]
            adjacent = sources[((index + 1) % len(cases)) * 24]
            for number in range(32):
                # Retained versions mix overlap, duplicate citations, legacy
                # string IDs, openings, and a cross-case historical citation.
                selected = [case_sources[(number + offset) % 20].pk for offset in range(12)]
                expected_links += len(set(selected + [adjacent.pk]))
                hidden.update(selected + [adjacent.pk, case_sources[21].pk])
                rows.append(ForecastScenario(
                    case=case, reference=f'REHEARSAL-{number // 4}', number=number % 4 + 1,
                    evidence=case_sources[21], actor=self.actor, reason='Synthetic retained forecast revision',
                    payload={
                        'items': [{'key': f'item-{offset}', 'evidence_id': pk if offset else f' +00{pk} '}
                                  for offset, pk in enumerate(selected)] + [{'evidence_id': selected[1]}],
                        'openings': [{'evidence_id': adjacent.pk}, {'evidence_id': selected[0]}],
                    },
                ))
        ForecastScenario.objects.bulk_create(rows, batch_size=128)
        writer_source = sources[22]
        ready = Queue()

        def migrate():
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()')
                    ready.put(cursor.fetchone()[0])
                MigrationExecutor(connection).migrate(self.leaves)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                late = self.add_scenario('CONCURRENT-WRITE', writer_source, [{'evidence_id': writer_source.pk}])
                before = self.fingerprint()
                future = pool.submit(migrate)
                backend = ready.get(timeout=15)
                blocked = False
                for _ in range(150):
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT count(*) FROM pg_locks
                            WHERE pid = %s AND relation = 'finance_forecastscenario'::regclass AND NOT granted
                        """, [backend])
                        blocked = cursor.fetchone()[0] > 0
                    if blocked or future.done():
                        break
                    sleep(.02)
                self.assertTrue(blocked, '0077 must wait for the prior scenario writer')
                released_at = perf_counter()
            future.result(timeout=90)
            elapsed = perf_counter() - released_at

        self.assertEqual(self.fingerprint(), before)
        self.assertEqual(ForecastEvidenceReference.objects.filter(scenario__case__in=cases).count(), expected_links)
        self.assertTrue(ForecastEvidenceReference.objects.filter(scenario=late, evidence_id=writer_source.pk).exists())
        hidden.add(writer_source.pk)
        candidates = Evidence.objects.filter(case__in=cases, kind='policy_decision')
        self.assertEqual(set(public_evidence(candidates).values_list('pk', flat=True)), {row.pk for row in sources} - hidden)
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_total_relation_size('finance_forecastevidencereference')")
            relation_bytes = cursor.fetchone()[0]
        print(f'0077 rehearsal: {before[0]} scenarios, {ForecastEvidenceReference.objects.count()} citations, '
              f'{relation_bytes} relation bytes, {elapsed:.3f}s after writer release')

    def test_malformed_predecessor_rolls_back_schema_and_data_projection(self):
        source = self.anchor.evidence.first()
        with transaction.atomic():
            self.add_scenario('MALFORMED', source, [{'evidence_id': 'invalid'}])
            before = self.fingerprint()
            with self.assertRaises(DatabaseError), transaction.atomic():
                MigrationExecutor(connection).migrate(self.leaves)
            self.assertEqual(self.fingerprint(), before)
            self.assertNotIn(UPGRADE, MigrationRecorder(connection).applied_migrations())
            self.assertNotIn('finance_forecastevidencereference', connection.introspection.table_names())
            transaction.set_rollback(True)  # Synthetic invalid predecessor only.
        MigrationExecutor(connection).migrate(self.leaves)
        self.assertEqual(ForecastScenario.objects.count(), 1)
        self.assertGreater(ForecastEvidenceReference.objects.count(), 0)
