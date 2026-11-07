"""Explicit isolated guard harness, not a migration or accepted final schema.

The closed factory identity function is copied from the actual migrated database
and extended only for this new definition. No predecessor is invented.
"""
import os
from django.db import connection
from apps.workflows.ledger_factory_guard import SQL

def install():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_trigger WHERE tgname='psl_factory_ledger'")
        if cursor.fetchone():return
        if os.environ.get('PSL_LEDGER_PROVISIONAL')!='1':raise RuntimeError('Real0077 required; isolated diagnostics must explicitly opt into PSL_LEDGER_PROVISIONAL=1')
        cursor.execute("SELECT pg_get_functiondef('psl_factory_identity()'::regprocedure)")
        source=cursor.fetchone()[0]
        source=source.replace("NEW.definition NOT IN (", "NEW.definition NOT IN ('finance-ledger/v1',",1)
        source=source.replace('CASE NEW.definition ',"CASE NEW.definition WHEN 'finance-ledger/v1' THEN 'OPS.factory_ledger_execution' ",1)
        cursor.execute(source)
        cursor.execute(SQL)
