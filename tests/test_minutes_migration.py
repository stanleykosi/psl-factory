"""Real P43 migration composition and populated native/P44 predecessor upgrade."""
import ast,json,hashlib
from importlib import import_module
from pathlib import Path
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase,TransactionTestCase
from django.utils import timezone

WORK=('workflows','0074_factory_minutes')
DOC=('documents','0028_factory_minutes')
PREVIOUS=[('documents','0027_factory_escalation'),('workflows','0073_factory_escalation')]

class MinutesMigrationTests(SimpleTestCase):
    def test_literal_workflow_extends_exact_actual_predecessor(self):
        prior=import_module('apps.workflows.migrations.0073_factory_escalation')
        current=import_module('apps.workflows.migrations.0074_factory_minutes')
        from scripts.p43_guard_sql import workflow
        self.assertEqual(current.PREVIOUS,prior.SQL);self.assertEqual(current.SQL,workflow(prior.SQL))
        self.assertEqual(current.Migration.dependencies,[('workflows','0073_factory_escalation'),('documents','0027_factory_escalation')])
        self.assertEqual(current.REVERSE,prior.SQL+'\nDROP FUNCTION psl_minutes_current(bigint,bigint,bigint);\n')

    def test_literal_document_extends_scope_without_replacing_group_date_guard(self):
        prior=import_module('apps.documents.migrations.0027_factory_escalation')
        current=import_module('apps.documents.migrations.0028_factory_minutes')
        from scripts.p43_guard_sql import documents,DOC_BRANCH
        self.assertEqual(current.PREVIOUS,prior.SQL);self.assertEqual(current.SQL,documents(prior.SQL))
        self.assertEqual(current.SQL.replace(DOC_BRANCH,'',1),prior.SQL);self.assertEqual(current.REVERSE,prior.SQL)
        self.assertEqual(current.Migration.dependencies,[('documents','0027_factory_escalation'),WORK])
        self.assertNotIn('psl_group_forecast_business_date',current.SQL)

    def test_only_literal_sql_and_all_exact_predecessor_bytes(self):
        expected=json.loads(Path('tests/p43_predecessor_migrations.json').read_text())
        for path,sha in expected['files'].items():self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),sha,path)
        for name in [WORK,DOC]:
            module=import_module('apps.'+name[0]+'.migrations.'+name[1]);tree=ast.parse(Path(module.__file__).read_text())
            imports=[n for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]
            self.assertEqual(len(imports),1);self.assertEqual(imports[0].module,'django.db')
            values={target.id:n.value for n in tree.body if isinstance(n,ast.Assign) for target in n.targets if isinstance(target,ast.Name)}
            for key in ['PREVIOUS','SQL','REVERSE']:self.assertIsInstance(values[key],ast.Constant)

    def test_actual_graph_retains_order_and_closed_family_registrations(self):
        plan=MigrationLoader(None).graph.forwards_plan(DOC)
        ordered=[('identity','0001_initial'),('workflows','0068_ppe_identity_dependency_replacement'),('workflows','0071_factory_group_forecast'),('workflows','0072_factory_weekly_report'),('documents','0026_group_forecast_business_date'),('workflows','0073_factory_escalation'),('documents','0027_factory_escalation'),WORK,DOC]
        self.assertEqual([plan.index(n) for n in ordered],sorted(plan.index(n) for n in ordered))
        self.assertNotIn(('workflows','0068_factory_ppe'),plan)
        from apps.workflows.factory_definitions import DEFINITIONS
        for key in ['pmo-minutes/v1','pmo-escalation/v1','pmo-weekly-report/v1','finance-forecast/v1','planning/v1']:self.assertIn(key,DEFINITIONS)

class PopulatedMinutesUpgradeTests(TransactionTestCase):
    """Downgrade only new function guards, seed native history, apply actual migrations."""
    def rows(self):
        result={}
        with connection.cursor() as cursor:
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'django_migrations' ORDER BY tablename")
            for name, in cursor.fetchall():
                cursor.execute('SELECT to_jsonb(t)::text FROM '+connection.ops.quote_name(name)+' t ORDER BY to_jsonb(t)::text')
                result[name]=cursor.fetchall()
        return result

    def test_populated_p44_to_p43_upgrade_preserves_history_and_native_effects(self):
        from tests.test_escalations import fixture,profile
        from tests.helpers import rev
        from tests.document_helpers import artifact
        from tests.meeting_helpers import MINUTES_DEFINITION
        from apps.core.services import add_evidence
        from apps.documents.controlled import register_template,request_review,review_version,reserve_publication
        from apps.documents.delivery import run_publication_once
        from apps.documents.models import PublicationReceipt,PublicationJob
        from apps.policy.operator_drafts import draft_operator_policy
        from apps.policy.services import transition
        from apps.pmo import escalations as native
        from apps.pmo.meetings import record_meeting,create_action,change_action
        from apps.pmo.reporting import draft_minutes
        from apps.workflows import factory,factory_escalation as escalation,factory_minutes as minutes
        from adapters.publications import PublicationTimeoutAfterAccept,InternalPublicationAdapter
        executor=MigrationExecutor(connection);leaves=executor.loader.graph.leaf_nodes()
        executor.migrate(PREVIOUS)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT name FROM django_migrations WHERE app='documents' AND name='0028_factory_minutes'");self.assertEqual(cursor.fetchall(),[])
                cursor.execute("SELECT to_regprocedure('psl_minutes_current(bigint,bigint,bigint)')");self.assertIsNone(cursor.fetchone()[0])
            from tests.minutes_upgrade_helpers import seed_predecessor
            seeded=seed_predecessor(self)
            actor,case,work,proof,notes,original,revised,action,unknown,first,first_pub,second,pending,mt,owner=(seeded[key] for key in ['actor', 'case', 'work', 'proof', 'notes', 'original', 'revised', 'action', 'unknown', 'first', 'first_pub', 'second', 'pending', 'mt', 'owner'])
            before=self.rows();old_receipts=list(PublicationReceipt.objects.values_list('pk',flat=True));spent=work.budget_used
            MigrationExecutor(connection).migrate(leaves)
            self.assertEqual(self.rows(),before)
            self.assertEqual(escalation.verify(work),proof);work.refresh_from_db();self.assertEqual(work.budget_used,spent)
            class LookupOnly(InternalPublicationAdapter):
                def deliver(self,*args):raise AssertionError('Existing receipt must prevent a replacement delivery')
            run_publication_once(LookupOnly(),job_id=pending.job.pk)
            self.assertEqual(PublicationJob.objects.get(publication=pending).status,'confirmed');self.assertEqual(list(PublicationReceipt.objects.values_list('pk',flat=True)),old_receipts)
            config={'definition':minutes.DEFINITION,'max_steps':60,'max_tokens':50000,'tokens_per_call':100,'max_children':100,'max_depth':3,'lease_seconds':30,'max_age_seconds':86400,'required_evidence_kinds':[minutes.KIND,'meeting_notes'],'information_resolver_id':None,'executor_id':actor.pk,'review_role':None,'provider':'synthetic_factory_v1','enabled':True,'extraction_provider':'synthetic_meeting_v1'}
            policy=draft_operator_policy(actor,case.pk,'OPS.factory_minutes_execution',config,owner.pk,timezone.now());transition(actor,policy.pk,'validated');transition(actor,policy.pk,'active')
            selection={'protocol':minutes.PROTOCOL,'meeting_version_id':revised.pk,'evidence_id':notes.pk,'template_id':mt.pk,'audience':'internal','publish':False}
            current=minutes.start(actor,case.pk,'UPGRADE-P43','UPGRADE-MEETING',selection,rev(case))
            fields={'kind':'status','occurred_at':revised.occurred_at.isoformat(),'purpose':revised.purpose,'summary':revised.summary,'participant_ids':[actor.pk],'decisions':[dict(d,change_evidence_id=None) for d in revised.decisions],'actions':[],'existing_action_ids':[action.pk,unknown.pk],'note':'Human retains actual commitments and attribution after additive upgrade.'}
            minutes.confirm(actor,current.pk,current.revision,rev(case),fields,None);factory.run_until_wait(current.pk);current.refresh_from_db();self.assertEqual(current.status,'verified',current.finding)
            self.assertFalse(minutes.verify(current,actor)['actions_completed']);action.refresh_from_db();unknown.refresh_from_db()
            self.assertEqual(action.current.status,'completed');self.assertIsNone(unknown.current.owner_id);self.assertIsNone(unknown.current.due_at)
        finally:
            MigrationExecutor(connection).migrate(leaves)
