import base64,copy,json,os,subprocess,sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from django.conf import settings
from django.test import SimpleTestCase
from adapters import native_application_archive as n
from psycopg import sql
from tests import test_cold_recovery as cold_tests


class ReconstitutionTests(SimpleTestCase):
    @classmethod
    def child(cls,stage,v,cold=True):
        env=os.environ.copy();env.update(PGDATABASE=v['control'] if cold else v['source'],DJANGO_SETTINGS_MODULE='config.cold_settings' if cold else 'config.settings')
        result=subprocess.run([sys.executable,'-m','tests.reconstitution_scenario',stage],input=json.dumps(v),text=True,capture_output=True,env=env,timeout=300)
        if result.returncode:raise AssertionError(stage+' failed\n'+result.stdout+'\n'+result.stderr)
        return json.loads(result.stdout.strip().splitlines()[-1])

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.directory=TemporaryDirectory(prefix='reconstitution-',dir=settings.BASE_DIR/'.runtime');cls.addClassCleanup(cls.directory.cleanup)
        root=Path(cls.directory.name);cls.root=root
        cls.value={'root':str(root),'source':'psl_fixture_source_'+uuid4().hex[:14],'control':'psl_cold_'+uuid4().hex[:14],
            'key':base64.b64encode(os.urandom(32)).decode(),'secret':base64.b64encode(os.urandom(32)).decode(),
            'receipt_key':base64.b64encode(os.urandom(32)).decode(),'pg_bin':str(settings.BASE_DIR/'.runtime/pgsql/bin'),'with_reconstitution_effects':True}
        for name in [cls.value['source'],cls.value['control']]:cold_tests.ColdRecoveryTests.provision(name,template=True)
        for label in ['archives','attachments','old-target-files']:(root/label).mkdir()
        cls.value['archive']=cls.child('source',cls.value,cold=False)
        with n.connect() as db:db.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(sql.Identifier(cls.value['source'])))
        cls.child('initialize',cls.value)
        cls.value['target']='test_psl_recovery_'+uuid4().hex[:18]
        cold_tests.ColdRecoveryTests.provision(cls.value['target'])
        target=root/'target';target.mkdir();cls.value['target_files']=str(target)
        cls.value.update(cls.child('recover',cls.value))

    def scenario(self,stage):
        value=copy.deepcopy(self.value);tag=uuid4().hex[:12]
        value['reference']=stage+'-'+tag
        for key in ['artifacts','gateway']:
            p=self.root/(key+'-'+tag);p.mkdir();value[key]=str(p)
        return value,self.child(stage,value)

    def test_01_ui_missing_policy_scope_agent_and_inventory(self):
        _,r=self.scenario('controls');self.assertTrue(r['inventory_complete']);self.assertTrue(r['source_unavailable'])

    def test_02_authenticated_receipts_unknown_and_human_dispositions(self):
        _,r=self.scenario('receipts');self.assertTrue(r['unknown_not_retried']);self.assertTrue(r['invalid_evidence_rejected'])

    def test_03_complete_review_publication_and_changed_evidence(self):
        _,r=self.scenario('publication');self.assertTrue(r['reviewed']);self.assertFalse(r['activation_enabled']);self.assertTrue(r['stale_review_rejected'])

    def test_04_duplicates_and_fresh_process_commit_recovery(self):
        v,r=self.scenario('crash');v.update(r)
        result=self.child('reconcile',v);self.assertEqual(result['attempts'],3);self.assertEqual(result['artifact_count'],1)

    def test_05_sql_guards_and_foreign_scope(self):
        _,r=self.scenario('guards');self.assertTrue(r['guards']);self.assertTrue(r['foreign_scope_rejected'])

    def test_06_revoked_policy_roles_and_receipt_expiry(self):
        _,r=self.scenario('authority');self.assertTrue(r['authority_rejected'])
