import os,base64,copy
from uuid import uuid4
from django.test import TransactionTestCase
from django.db import connection,transaction,DatabaseError,connections
from psycopg import sql
from adapters import native_application_archive as n
from .test_finance_readback import FinanceReadbackAdapterTests as Base

class SuccessorReadbackAdapterTests(Base):
    test_native_receipt_current_source_authority_bounds_and_revocation=None
    def test_native_current_lineage_separate_receipt_and_reviewer_revocation(self):
        v={'provider':'psl_finance_provider_'+uuid4().hex[:18],'case':str(uuid4()),'operational_case':str(uuid4()),'identity':base64.b64encode(os.urandom(32)).decode(),'include_successors':True}
        connections['default'].close()
        with n.connect('test_psl') as db:
            for t in n.tables(db):
                if t not in {'django_migrations','auth_permission','django_content_type'}:self.assertEqual(db.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(t))).fetchone()[0],0,t)
        with n.connect() as db:
            db.autocommit=True;self.assertIsNone(db.execute('SELECT 1 FROM pg_database WHERE datname=%s',[v['provider']]).fetchone())
            db.execute(sql.SQL('CREATE DATABASE {} TEMPLATE test_psl').format(sql.Identifier(v['provider'])))
        v.update(self.child('seed',v));self.child('initialize',v)
        self.assertEqual(self.child('probe',v)['successors']['lineage'],[])
        v.update(self.child('receive',v));v.update(self.child('lineage',v))
        current=self.child('probe',v);self.assertEqual(current['successors']['lineage'][0]['status'],'current');self.assertEqual(current['successors']['lineage'][0]['successor_receipt'],'present')
        for private in ['Synthetic exact','test-only-password','signed_delta','reviewer_id','quantity']:self.assertNotIn(private,__import__('json').dumps(current))
        self.child('lineage_revoke',v);stale=self.child('probe',v)
        self.assertTrue(stale['current_authority_verified']);self.assertEqual(stale['successors']['lineage'][0]['status'],'stale');self.assertFalse(stale['execution_authorized'])

class SuccessorMetadataSqlTests(TransactionTestCase):
    def test_installed_supplement_guard_allows_metadata_and_rejects_private_or_active_payload(self):
        # The real installed trigger is tested independently of expensive parent publication setup.
        # Full workflow/parent guards are exercised by the connected recovery suite.
        with connection.cursor() as cursor:
            cursor.execute('CREATE TEMP TABLE successor_guard_contract(pin jsonb,result jsonb)')
            cursor.execute('CREATE TRIGGER contract_guard BEFORE INSERT ON successor_guard_contract FOR EACH ROW EXECUTE FUNCTION psl_native_successor_metadata_guard()')
        pin={'lineage_contract':'psl.finance-successor-lineage/v1'}
        empty={'successors':{'format':pin['lineage_contract'],'lineage':[]}}
        import json
        def insert(result):
            with connection.cursor() as cursor:cursor.execute('INSERT INTO successor_guard_contract VALUES (%s::jsonb,%s::jsonb)',[json.dumps(pin),json.dumps(result)])
        try:
            insert(empty)
            row={'proposal_ref':'1','relation':'legal_correction','successor_ref':'2','status':'current','review_ref':'3','successor_receipt':'present','execution_authorized':False,'financial_effect_verified':False,'debt_waived':False}
            valid=copy.deepcopy(empty);valid['successors']['lineage']=[row];insert(valid)
            for change in [{'note':'Private notes forbidden'},{'execution_authorized':True},{'status':'proposed','successor_receipt':'present'}]:
                bad=copy.deepcopy(valid);bad['successors']['lineage'][0].update(change)
                with self.assertRaises(DatabaseError),transaction.atomic():insert(bad)
        finally:
            with connection.cursor() as cursor:cursor.execute('DROP TABLE successor_guard_contract')
