import os,sys,json,subprocess,base64
from uuid import uuid4
from pathlib import Path
from django.test import SimpleTestCase
from django.db import connections
from psycopg import sql
from adapters import native_application_archive as n

class FinanceReadbackAdapterTests(SimpleTestCase):
    @classmethod
    def child(cls,stage,v):
        env=os.environ.copy();env.update(PGDATABASE=v['provider'] if stage in ['seed','receive','decide','supersede','revoke','conflict','lineage','lineage_revoke'] else 'test_psl',DJANGO_SETTINGS_MODULE='config.settings')
        r=subprocess.run([sys.executable,'-m','tests.finance_readback_adapter_scenario',stage],input=json.dumps(v),text=True,capture_output=True,env=env,timeout=180)
        if r.returncode:raise AssertionError(stage+' failed\n'+r.stdout+'\n'+r.stderr)
        return json.loads(r.stdout.strip().splitlines()[-1])
    def test_native_receipt_current_source_authority_bounds_and_revocation(self):
        v={'provider':'psl_finance_provider_'+uuid4().hex[:18],'case':str(uuid4()),'operational_case':str(uuid4()),'identity':base64.b64encode(os.urandom(32)).decode()}
        connections['default'].close()
        with n.connect('test_psl') as db:
            for t in n.tables(db):
                if t not in {'django_migrations','auth_permission','django_content_type'}:self.assertEqual(db.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(t))).fetchone()[0],0,t)
        with n.connect() as db:
            db.autocommit=True
            self.assertIsNone(db.execute('SELECT 1 FROM pg_database WHERE datname=%s',[v['provider']]).fetchone())
            db.execute(sql.SQL('CREATE DATABASE {} TEMPLATE test_psl').format(sql.Identifier(v['provider'])))
        v.update(self.child('seed',v));self.child('initialize',v)
        self.assertEqual(self.child('probe',v)['outcome'],'unknown')
        v.update(self.child('receive',v));ack=self.child('probe',v);self.assertEqual(ack['outcome'],'acknowledged');self.assertEqual(ack['disposition'],'absent')
        self.assertTrue(self.child('decide',v)['decision_current']);v['controls']=True
        current=self.child('probe',v);self.assertTrue(current['current_authority_verified']);v.pop('controls')
        v['key']='owner-successor';self.assertTrue(self.child('supersede',v)['decision_current'])
        successor=self.child('probe',v);self.assertNotEqual(current['decision_sha256'],successor['decision_sha256'])
        self.assertFalse(self.child('revoke',v)['decision_current']);revoked=self.child('probe',v)
        self.assertEqual(revoked['outcome'],'acknowledged');self.assertEqual(revoked['disposition'],'revoked');self.assertFalse(revoked['current_authority_verified'])
        self.child('conflict',v);self.assertEqual(self.child('probe',v)['outcome'],'conflict')
        for private in ['Synthetic exact current','test-only-password','owner_id','signed_delta']:self.assertNotIn(private,json.dumps(current))
