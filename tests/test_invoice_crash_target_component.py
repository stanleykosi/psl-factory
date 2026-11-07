"""Pure test-only guard checks; no Django, database or child process."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock
from tests import invoice_crash_target as g

class CrashTargetTests(unittest.TestCase):
    def owned(self):
        return {'PGDATABASE':g.OWNED,g.OPT_IN:g.SYSTEM,'PGHOST':'127.0.0.1','PGPORT':'55777','PGUSER':'psl'}

    def test_default_is_still_exact_test_psl(self):
        self.assertEqual(g.target({'PGDATABASE':'test_psl'}),'test_psl')
        for name in (None,'psl','test_psl_other'):
            with self.assertRaises(RuntimeError):g.target({'PGDATABASE':name})

    def test_owned_requires_every_exact_pin(self):
        self.assertEqual(g.target(self.owned()),g.OWNED)
        for key in self.owned():
            env=self.owned();env[key]='wrong'
            with self.subTest(key=key),self.assertRaises(RuntimeError):g.target(env)
        with self.assertRaises(RuntimeError):g.target({'PGDATABASE':g.OWNED})
        with self.assertRaises(RuntimeError):g.target({'PGDATABASE':g.DEFAULT,g.OPT_IN:g.SYSTEM})

    def test_resolved_connection_cannot_redirect(self):
        value={'NAME':g.OWNED,'HOST':'127.0.0.1','PORT':55777,'USER':'psl'}
        g.validate_connection(value,g.OWNED)
        for key in value:
            changed=dict(value);changed[key]='wrong'
            with self.subTest(key=key),self.assertRaises(RuntimeError):g.validate_connection(changed,g.OWNED)

    def test_actual_database_and_system_identity(self):
        cursor=Mock();cursor.fetchone.return_value=(g.OWNED,g.SYSTEM)
        g.verify_database(cursor,g.OWNED)
        cursor.execute.assert_called_once_with('SELECT current_database(), system_identifier::text FROM pg_control_system()')
        for result in [(g.DEFAULT,g.SYSTEM),(g.OWNED,'other'),None]:
            cursor.fetchone.return_value=result
            with self.assertRaises(RuntimeError):g.verify_database(cursor,g.OWNED)
        cursor.fetchone.return_value=(g.DEFAULT,);g.verify_database(cursor,g.DEFAULT)

    def test_job_stays_synthetic_issue_with_factory_identity(self):
        def job(synthetic=True,kind='issue',work=1):
            return NS(invoice=NS(case=NS(synthetic=synthetic)),kind=kind,intent={'factory_execution':{'work':work}})
        g.validate_job(job())
        for value in [job(False),job(kind='deliver'),job(work=True),job(work=None)]:
            with self.assertRaises(RuntimeError):g.validate_job(value)
