"""Add only the source-bound native Finance report publication contract."""
from importlib import import_module
from django.db import migrations

SQL=import_module('apps.documents.migrations.0017_factory_go_live_scope').SQL
MARKER='\n   ))'
assert SQL.count(MARKER)==1
BRANCH=r"""
    OR
    (w.definition='finance-accounts/v1' AND p.component='OPS.factory_accounting_execution'
     AND e.kind='agent_private_accounting_intake'
     AND EXISTS(SELECT 1 FROM finance_financedocumentbinding b JOIN finance_financerun r ON r.id=b.run_id
      JOIN finance_financesource s ON s.id=r.source_id WHERE b.version_id=v.id AND r.case_id=w.case_id
       AND r.kind='formula' AND s.id=(e.body::jsonb->>'source')::bigint AND s.batch_id=(w.request->>'batch')::bigint))
"""
SQL=SQL.replace(MARKER,BRANCH+MARKER)

class Migration(migrations.Migration):
    dependencies=[('documents','0017_factory_go_live_scope'),('workflows','0050_factory_accounting')]
    operations=[migrations.RunSQL(SQL)]
