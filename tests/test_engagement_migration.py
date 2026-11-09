"""Actual engagement guard graph and populated P43-to-engagement preservation."""
import ast,hashlib,json
from pathlib import Path
from importlib import import_module
from django.test import SimpleTestCase,TransactionTestCase
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.executor import MigrationExecutor

WORK=('workflows','0075_factory_engagement')
PREVIOUS=[('workflows','0074_factory_minutes'),('documents','0028_factory_minutes')]


class EngagementMigrationTests(SimpleTestCase):
    def test_literal_extension_preserves_every_actual_predecessor_guard(self):
        prior=import_module('apps.workflows.migrations.0074_factory_minutes')
        current=import_module('apps.workflows.migrations.0075_factory_engagement')
        self.assertEqual(current.PREVIOUS,prior.SQL)
        prefix=current.SQL.split('CREATE OR REPLACE FUNCTION psl_engagement_factory_source',1)[0]
        restored=prefix.replace(" IF NEW.definition NOT IN ('engagement/v1',",' IF NEW.definition NOT IN (',1).replace("p.component=CASE NEW.definition WHEN 'engagement/v1' THEN 'OPS.factory_engagement_execution' ",'p.component=CASE NEW.definition ',1)
        self.assertEqual(restored.rstrip(),prior.SQL.rstrip())
        self.assertEqual(current.Migration.dependencies,PREVIOUS)
        self.assertTrue(current.REVERSE.startswith(prior.SQL))
        self.assertIn('DROP TRIGGER psl_engagement_factory_guard ON workflows_factorywork;',current.REVERSE)
        for name in ['factory_source','factory_identity_clear','public_source','planning_inputs_current','worker_current','factory_current','factory_guard']:
            self.assertIn('CREATE OR REPLACE FUNCTION psl_engagement_'+name+'(',current.SQL)
            self.assertIn('DROP FUNCTION psl_engagement_'+name+'(',current.REVERSE)

    def test_only_literal_sql_and_exact_accepted_predecessor_bytes(self):
        data=json.loads(Path('tests/engagement_predecessor_migrations.json').read_text());self.assertEqual(data['predecessor'],'3ac8056')
        for name,sha in data['files'].items():self.assertEqual(hashlib.sha256(Path(name).read_bytes()).hexdigest(),sha,name)
        module=import_module('apps.workflows.migrations.0075_factory_engagement');tree=ast.parse(Path(module.__file__).read_text())
        imports=[n for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]
        self.assertEqual(len(imports),1);self.assertEqual(imports[0].module,'django.db')
        values={target.id:n.value for n in tree.body if isinstance(n,ast.Assign) for target in n.targets if isinstance(target,ast.Name)}
        for key in ['PREVIOUS','SQL','REVERSE']:self.assertIsInstance(values[key],ast.Constant)

    def test_actual_graph_retains_all_accepted_family_and_date_guards(self):
        loader=MigrationLoader(None);plan=loader.graph.forwards_plan(WORK)
        ordered=[('identity','0001_initial'),('workflows','0068_ppe_identity_dependency_replacement'),('workflows','0071_factory_group_forecast'),('workflows','0072_factory_weekly_report'),('documents','0026_group_forecast_business_date'),('workflows','0073_factory_escalation'),('documents','0027_factory_escalation'),*PREVIOUS,WORK]
        self.assertEqual([plan.index(n) for n in ordered],sorted(plan.index(n) for n in ordered));self.assertNotIn(('workflows','0068_factory_ppe'),plan)
        self.assertNotIn(('documents','0029_factory_engagement'),loader.graph.nodes)
        from apps.workflows.factory_definitions import DEFINITIONS
        from apps.workflows.factory_views import INTAKES
        expected={'engagement/v1','pmo-weekly-report/v1','pmo-escalation/v1','pmo-minutes/v1','planning/v1'}
        self.assertTrue(expected<=set(DEFINITIONS));self.assertTrue(expected<={row[0] for row in INTAKES})


class PopulatedEngagementUpgradeTests(TransactionTestCase):
    def rows(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'django_migrations' ORDER BY tablename");names=[r[0] for r in cursor.fetchall()];result={}
            for name in names:
                cursor.execute('SELECT to_jsonb(t)::text FROM '+connection.ops.quote_name(name)+' t ORDER BY to_jsonb(t)::text');result[name]=cursor.fetchall()
            return result

    def test_populated_p43_upgrade_and_native_identity_connection_preserve_original_history(self):
        from tests.engagement_upgrade_helpers import seed_predecessor,reverify
        from tests.test_engagement_intake import activate
        from tests.helpers import rev
        from apps.workflows import factory,factory_engagement
        from apps.workflows.models import FactoryWork
        from apps.core.models import Case,Evidence,Audit
        from django.contrib.auth import get_user_model
        executor=MigrationExecutor(connection);leaves=executor.loader.graph.leaf_nodes();executor.migrate(PREVIOUS)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regprocedure('psl_engagement_factory_guard()')");self.assertIsNone(cursor.fetchone()[0])
            record=seed_predecessor(self);before=self.rows();MigrationExecutor(connection).migrate(leaves)
            self.assertEqual(self.rows(),before);reverify(record);self.assertEqual(self.rows(),before)
            MigrationExecutor(connection).migrate(leaves);self.assertEqual(self.rows(),before)
            actor=get_user_model().objects.get(pk=record['actor']);case=Case.objects.get(pk=record['case']);proof=Evidence.objects.get(pk=record['policy_evidence'])
            profile=json.loads(Path('fixtures/factory-engagement.json').read_text());profile.pop('classification');activate(actor,case,'OPS.factory_engagement_execution',profile,proof)
            work=factory_engagement.start(actor,case.pk,'UPGRADE-ENGAGEMENT',record['capture'],'Existing native project, same planning work',rev(case))
            factory.run_until_wait(work.pk);work.refresh_from_db();result=factory_engagement.verified_output(work)
            self.assertEqual(result['planning_work'],record['planning_work']);self.assertEqual(result['planning_packet'],record['packet'])
            self.assertEqual(FactoryWork.objects.get(pk=record['planning_work']).actor_id,record['planning_actor'])
            self.assertEqual(Audit.objects.filter(action=factory_engagement.LINKED).count(),1);reverify(record)
        finally:MigrationExecutor(connection).migrate(leaves)
