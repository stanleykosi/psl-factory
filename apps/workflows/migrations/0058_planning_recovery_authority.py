"""Use statement time for finite authority, and pin native reviewer provenance."""
from importlib import import_module
from django.db import migrations

BASE=import_module('apps.workflows.migrations.0057_planning_recovery_guards').SQL
SQL=BASE[:BASE.index('CREATE TRIGGER psl_factory_planning_recovery_scope')]
SQL=SQL.replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1).replace('now()','statement_timestamp()')
OLD="r.sha256=cfg.envelope->'value'->>'sha256' AND r.content=NEW.authority->'rule')"
NEW=OLD[:-1]+" AND r.schema_ref='schema:psl/factory-receipt-recovery/v1')"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,NEW)
GUARDS=r"""
 IF NEW.authority->'rule'->'independent_of_requester'='true'::jsonb AND NEW.reviewer_id=coalesce(
  (SELECT principal_id FROM workflows_factoryexecutionbinding WHERE work_id=w.id AND created_at<=a.created_at ORDER BY sequence DESC LIMIT 1),w.actor_id)
 THEN RAISE EXCEPTION 'Configured receipt reviewer must differ from historical requester'; END IF;
 IF jsonb_typeof(NEW.binding) IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(NEW.binding))<>7
 OR NOT (NEW.binding ?& ARRAY['implementation','target','classification','auth_mode','credential_ref','revision','credential_binding'])
 OR NEW.binding->>'credential_ref' IS DISTINCT FROM c.payload->>'credential_ref'
 OR NEW.binding->>'revision' IS DISTINCT FROM c.payload->>'credential_revision'
 OR coalesce(NEW.binding->>'credential_binding','') !~ '^[a-f0-9]{64}$'
 OR NOT EXISTS(SELECT 1 FROM workflows_integrationassessment ia JOIN workflows_integrationreview ir ON ir.assessment_id=ia.id
  WHERE ia.id=(NEW.authority->'pins'->>'assessment')::bigint AND ia.contract_id=c.id
   AND ir.id=(NEW.authority->'pins'->>'review')::bigint AND ir.actor_id=NEW.reviewer_id AND ir.verdict='confirm'
   AND ir.authority=NEW.authority->'readiness' AND ia.result->'capability_ready'='true'::jsonb
   AND NOT EXISTS(SELECT 1 FROM workflows_integrationassessment WHERE contract_id=c.id AND id>ia.id)
   AND NOT EXISTS(SELECT 1 FROM workflows_integrationreview WHERE assessment_id=ia.id AND id>ir.id))
 THEN RAISE EXCEPTION 'Exact reviewed successor credentials and native readiness proof required'; END IF;
"""
assert SQL.count(' RETURN NEW;')==1
SQL=SQL.replace(' RETURN NEW;',GUARDS+' RETURN NEW;')

class Migration(migrations.Migration):
    dependencies=[('workflows','0057_planning_recovery_guards')]
    operations=[migrations.RunSQL(SQL)]
