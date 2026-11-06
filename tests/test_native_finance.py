import os,sys,json,subprocess,base64
from uuid import uuid4
from django.db import connections
from adapters import native_application_archive as n
from psycopg import sql
from tests import test_reconstitution as prior

class NativeFinanceTests(prior.ReconstitutionTests):
    test_01_ui_missing_policy_scope_agent_and_inventory=None
    test_02_authenticated_receipts_unknown_and_human_dispositions=None
    test_03_complete_review_publication_and_changed_evidence=None
    test_04_duplicates_and_fresh_process_commit_recovery=None
    test_05_sql_guards_and_foreign_scope=None
    test_06_revoked_policy_roles_and_receipt_expiry=None

    @classmethod
    def child(cls,stage,v,cold=True):
        if stage in ['source','initialize','recover']:return prior.ReconstitutionTests.child(stage,v,cold)
        source_stage=stage in ['provider_seed','source_accept'] or stage.startswith('source_readback_')
        env=os.environ.copy();env.update(PGDATABASE=v['provider_database'] if source_stage else v['control'],
            DJANGO_SETTINGS_MODULE='config.settings' if source_stage else 'config.cold_settings')
        r=subprocess.run([sys.executable,'-m','tests.native_finance_scenario',stage],input=json.dumps(v),text=True,capture_output=True,env=env,timeout=900)
        if r.returncode:raise AssertionError(stage+' failed\n'+r.stdout+'\n'+r.stderr)
        return json.loads(r.stdout.strip().splitlines()[-1])

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.value.update(provider_database='psl_finance_provider_'+uuid4().hex[:18],provider_identity=base64.b64encode(os.urandom(32)).decode())
        # A new provider schema only, never a restored source/target or existing database.
        connections['default'].close()
        with n.connect('test_psl') as db:
            for table in n.tables(db):
                if table not in {'django_migrations','auth_permission','django_content_type'}:
                    assert db.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]==0,table
        with n.connect() as db:
            db.autocommit=True
            assert not db.execute('SELECT 1 FROM pg_database WHERE datname=%s',[cls.value['provider_database']]).fetchone()
            db.execute(sql.SQL('CREATE DATABASE {} TEMPLATE test_psl').format(sql.Identifier(cls.value['provider_database'])))
        cls.value.update(cls.child('provider_seed',cls.value))
        cls.child('provider_initialize',cls.value)

    def scenario(self,stage):
        v=dict(self.value);tag=uuid4().hex[:12];v['reference']=stage+'-'+tag
        for key in ['artifacts','gateway','companion']:
            p=self.root/(key+'-'+tag);p.mkdir();v[key]=str(p)
        return v,self.child(stage,v)

    def test_10_exact_native_receipts_unknown_conflict_mapping_and_ui(self):
        _,r=self.scenario('controls');self.assertEqual(r['outcomes'],['present','conflict','unknown']);self.assertTrue(r['native'])

    def test_11_native_scope_guards_rotation_expiry_and_revocation(self):
        _,r=self.scenario('negatives');self.assertTrue(r['sql_guards']);self.assertTrue(r['scope_held']);self.assertTrue(r['quarantine_held'])

    def test_12_reviewed_publication_crash_and_fresh_reconciliation(self):
        v,r=self.scenario('publication');v.update(r)
        result=self.child('reconcile',v);self.assertEqual(result['attempts'],3);self.assertEqual(result['files'],1);self.assertFalse(result['activation_enabled'])
