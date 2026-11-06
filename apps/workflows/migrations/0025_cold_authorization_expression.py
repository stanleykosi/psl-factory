"""Forward repair; preserve the already applied0024 migration and all history."""
from importlib import import_module
from django.db import migrations

SQL = import_module('apps.workflows.migrations.0024_cold_recovery_guards').SQL.split('CREATE TRIGGER cold_identity_guard')[0]
SQL = SQL.replace('CREATE FUNCTION psl_cold_recovery_guard()', 'CREATE OR REPLACE FUNCTION psl_cold_recovery_guard()')
SQL = SQL.replace("r.pin=(NEW.intent->'pin'-'authorization_review')", "r.pin=((NEW.intent->'pin')-'authorization_review')")


class Migration(migrations.Migration):
    dependencies = [('workflows','0024_cold_recovery_guards')]
    operations = [migrations.RunSQL(SQL, reverse_sql=migrations.RunSQL.noop)]
