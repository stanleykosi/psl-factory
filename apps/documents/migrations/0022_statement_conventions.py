"""Add native current-convention publication check without weakening prior scopes."""
from importlib import import_module
from django.db import migrations
PREVIOUS=import_module('apps.documents.migrations.0021_factory_performance_scope').SQL
GUARD="""
 IF EXISTS(SELECT 1 FROM finance_financedocumentbinding b JOIN finance_financerun r ON r.id=b.run_id
  WHERE b.version_id=NEW.version_id AND r.kind='statement' AND (NOT psl_statement_conventions_current(r.id)
   OR b.snapshot->>'output_review' IS DISTINCT FROM (SELECT id::text FROM finance_financereview WHERE run_id=r.id AND purpose='output' ORDER BY finance_financereview.id DESC LIMIT 1)))
 THEN RAISE EXCEPTION 'Exact current reviewed producer and conversion declaration required'; END IF;
"""
assert PREVIOUS.count(' RETURN NEW;')==1
SQL=PREVIOUS.replace(' RETURN NEW;',GUARD+' RETURN NEW;')
assert SQL.replace(GUARD,'')==PREVIOUS
class Migration(migrations.Migration):
    dependencies=[('documents','0021_factory_performance_scope'),('workflows','0065_statement_conventions')]
    operations=[migrations.RunSQL(SQL)]
