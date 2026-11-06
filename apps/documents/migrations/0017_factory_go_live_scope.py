"""Explicit source-bound go-live publication; existing envelopes remain closed."""
from importlib import import_module
from django.db import migrations

SQL=import_module('apps.documents.migrations.0016_factory_handover_scope').SQL
start=SQL.index("    (w.definition='delivery-handover/v1'")
end=SQL.index('\n   ))',start)
branch=SQL[start:end].replace('delivery-handover/v1','delivery-go-live/v1').replace('factory_handover_execution','factory_go_live_execution')
branch=branch.replace('agent_private_handover_intake','agent_private_go_live_intake').replace("b.purpose='handover'","b.purpose='go_live' AND v.audience='client'")
SQL=SQL[:end]+'\n    OR\n'+branch+SQL[end:]

class Migration(migrations.Migration):
    dependencies=[('documents','0016_factory_handover_scope'),('workflows','0047_factory_go_live')]
    operations=[migrations.RunSQL(SQL)]
