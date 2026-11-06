"""Historical recipient receipts cannot establish a superseded report as current."""
from importlib import import_module
from django.db import migrations

SQL=import_module('apps.workflows.migrations.0054_restore_go_live_reaffirmation_guard').SQL
OLD="AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,"AND d.current_id=v.id "+OLD)


class Migration(migrations.Migration):
    dependencies=[('workflows','0054_restore_go_live_reaffirmation_guard')]
    operations=[migrations.RunSQL(SQL)]
