"""Retain0048's evidence-head support alongside0050's accounting verification guard."""
from importlib import import_module
from django.db import migrations

SQL = import_module('apps.workflows.migrations.0050_factory_accounting').SQL
OLD = "AND g.kind='go_live'"
assert SQL.count(OLD) == 1
SQL = SQL.replace(OLD, "AND g.kind IN ('go_live','go_live_reaffirmation')")


class Migration(migrations.Migration):
    dependencies = [('workflows', '0053_factory_execution_rule_scope')]
    operations = [migrations.RunSQL(SQL)]
