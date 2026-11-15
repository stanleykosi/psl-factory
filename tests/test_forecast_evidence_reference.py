"""PostgreSQL proof of forecast citation indexing and privacy equivalence."""
import json

from django.db import DatabaseError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.expressions import RawSQL
from django.test import TestCase, TransactionTestCase

from apps.agents.models import AgentRun
from apps.core.evidence_access import forecast_private, forecast_private_query, public_agent_runs, public_evidence, public_timeline
from apps.core.models import Evidence
from apps.core.services import add_evidence, event
from apps.documents.template_access import visible_sources
from apps.finance.models import ForecastEvidenceReference, ForecastScenario
from .forecast_helpers import payload, scenario
from .helpers import setup_case


def capture_source(actor, case, body):
    return add_evidence(actor, case.pk, 'policy_decision', body, 'synthetic:forecast-privacy')


class ForecastEvidenceReferenceTests(TestCase):
    def test_native_capture_hides_generic_evidence_timeline_and_agent_output(self):
        actor, case = setup_case()
        private = capture_source(actor, case, 'Linked private evidence')
        public = capture_source(actor, case, 'Unrelated public evidence')
        facts = payload(actor, case)
        for item in facts['items']:
            item['evidence_id'] = private.pk
        before = public_evidence(case.evidence.filter(pk__in=[private.pk, public.pk]))
        self.assertEqual(set(before.values_list('pk', flat=True)), {private.pk, public.pk})
        run = scenario(actor, case, facts)
        self.assertEqual(set(ForecastEvidenceReference.objects.filter(scenario=run).values_list('evidence_id', 'numeric_reference')), {
            (private.pk, True), (facts['openings'][0]['evidence_id'], True),
        })
        self.assertTrue(forecast_private(private))
        self.assertFalse(forecast_private(public))
        self.assertEqual(set(before.values_list('pk', flat=True)), {public.pk})
        self.assertFalse(visible_sources(actor, case, source_id=private.pk).exists())
        self.assertTrue(visible_sources(actor, case, source_id=public.pk).exists())
        event(actor, case, 'fixture.evidence', evidence=private.pk)
        public_event = event(actor, case, 'fixture.evidence', evidence=public.pk)
        self.assertEqual(list(public_timeline(case).filter(action='fixture.evidence').values_list('pk', flat=True)), [public_event.pk])
        runs = [
            AgentRun.objects.create(case=case, actor=actor, evidence=source, process_id='F09', provider='synthetic', result={})
            for source in (private, public)
        ]
        self.assertEqual(list(public_agent_runs(AgentRun.objects.filter(case=case)).values_list('pk', flat=True)), [runs[1].pk])
        with self.assertRaises(DatabaseError), transaction.atomic():
            ForecastEvidenceReference.objects.filter(scenario=run, evidence_id=private.pk).delete()

    def test_exact_read_plan_has_no_forecast_json_expansion(self):
        actor, case = setup_case()
        target = capture_source(actor, case, 'Indexed reference')
        unrelated = capture_source(actor, case, 'Unrelated')
        run = ForecastScenario.objects.create(case=case, reference='INDEX-PROOF', number=1, evidence=unrelated,
            payload={'items': [{'evidence_id': pk} for pk in range(100000, 102000)] + [{'evidence_id': target.pk}]},
            reason='Synthetic selective reference inventory', actor=actor)
        self.assertEqual(ForecastEvidenceReference.objects.filter(scenario=run).count(), 2001)
        query = Evidence.objects.filter(pk=target.pk).filter(forecast_private_query())
        sql, _ = query.query.sql_with_params()
        self.assertNotIn('jsonb_array_elements', sql)
        self.assertNotIn('"payload"', sql)
        with connection.cursor() as cursor:
            cursor.execute('ANALYZE finance_forecastevidencereference')
        plan = json.loads(query.explain(analyze=True, format='json'))[0]['Plan']
        nodes = [plan]
        for node in nodes:
            nodes.extend(node.get('Plans', []))
        self.assertTrue(any(
            node.get('Relation Name') == 'finance_forecastevidencereference'
            and node['Node Type'] in ('Index Scan', 'Index Only Scan')
            and 'evidence_id' in node.get('Index Cond', '')
            for node in nodes
        ), plan)
        self.assertFalse(any(node['Node Type'] == 'Function Scan' for node in nodes))
        self.assertTrue(query.exists())

    def test_invalid_legacy_shapes_fail_atomically_on_new_scenario(self):
        actor, case = setup_case()
        proof = capture_source(actor, case, 'Still public after failed write')
        for item in ({'evidence_id': 'invalid'}, {'evidence_id': None}, {}):
            with self.subTest(item=item), self.assertRaises(DatabaseError), transaction.atomic():
                ForecastScenario.objects.create(case=case, reference='INVALID', number=1, evidence=proof,
                    payload={'items': [{'evidence_id': proof.pk}, item]}, reason='Synthetic invalid history', actor=actor)
        self.assertFalse(ForecastScenario.objects.filter(case=case).exists())
        self.assertFalse(ForecastEvidenceReference.objects.filter(evidence_id=proof.pk).exists())
        self.assertTrue(public_evidence(case.evidence.filter(pk=proof.pk)).exists())


class ForecastEvidenceReferenceUpgradeTests(TransactionTestCase):
    def test_backfill_preserves_bigint_cast_and_global_privacy(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        executor.migrate([('finance', '0076_obligation_trigger_alias_repair')])
        try:
            actor, case = setup_case()
            other_actor, other_case = setup_case(username='other-forecast-owner')
            legacy = capture_source(actor, case, 'Legacy string reference')
            numeric = capture_source(actor, case, 'Numeric reference')
            external = capture_source(other_actor, other_case, 'Cross-case historical reference')
            public = capture_source(other_actor, other_case, 'Unrelated evidence')
            original = ForecastScenario.objects.create(case=case, reference='LEGACY', number=1, evidence=numeric,
                payload={'items': [{'evidence_id': f' +00{legacy.pk} '}, {'evidence_id': external.pk},
                                   {'evidence_id': str(numeric.pk)}, {'evidence_id': numeric.pk}],
                         'openings': [{'evidence_id': external.pk}]},
                reason='Synthetic pre-index history', actor=actor)
            candidates = Evidence.objects.filter(pk__in=[legacy.pk, numeric.pk, external.pk, public.pk])
            old_ids = RawSQL(
                "SELECT evidence_id FROM finance_forecastitemsupport UNION SELECT evidence_id FROM finance_forecastscenario "
                "UNION SELECT (item->>'evidence_id')::bigint FROM finance_forecastscenario CROSS JOIN LATERAL jsonb_array_elements(payload->'items') item "
                "UNION SELECT (opening->>'evidence_id')::bigint FROM finance_forecastscenario CROSS JOIN LATERAL jsonb_array_elements(payload->'openings') opening",
                [],
            )
            before = set(candidates.exclude(pk__in=old_ids).values_list('pk', flat=True))
            MigrationExecutor(connection).migrate(leaves)
            self.assertEqual(before, {public.pk})
            self.assertEqual(set(public_evidence(candidates).values_list('pk', flat=True)), before)
            self.assertEqual(set(ForecastEvidenceReference.objects.filter(scenario=original).values_list('evidence_id', 'numeric_reference')), {
                (legacy.pk, False), (numeric.pk, True), (external.pk, True),
            })
            self.assertFalse(forecast_private(legacy))
            self.assertFalse(forecast_private(external))
            self.assertEqual(ForecastScenario.objects.get(pk=original.pk).payload, original.payload)
        finally:
            MigrationExecutor(connection).migrate(leaves)
