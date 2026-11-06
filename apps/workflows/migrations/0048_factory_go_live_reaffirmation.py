"""Verify the explicit native evidence head, while retaining the single go-live anchor."""
from importlib import import_module
from django.db import migrations

SQL=import_module('apps.workflows.migrations.0047_factory_go_live').SQL
OLD="AND g.kind='go_live'"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,"AND g.kind IN ('go_live','go_live_reaffirmation')")

class Migration(migrations.Migration):
    dependencies=[('workflows','0047_factory_go_live'),('pmo','0042_go_live_reaffirmation')]
    operations=[migrations.RunSQL(SQL)]
