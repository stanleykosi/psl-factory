"""A fresh source author requires an exact human instruction; preserve all prior output guards."""
from importlib import import_module
from django.db import migrations

SQL=import_module('apps.workflows.migrations.0055_current_accounting_document').SQL
GUARD=r"""
 IF TG_OP='UPDATE' AND NEW.definition IN ('delivery-release/v1','delivery-hypercare/v1')
 AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id THEN
  IF NEW.cancel_requested OR OLD.status IN ('cancelled','followup_needed') OR NEW.status<>'ready'
   OR (OLD.lease_until IS NOT NULL AND OLD.lease_until>statement_timestamp())
   OR NOT EXISTS(SELECT 1 FROM core_evidence n JOIN core_evidence o ON o.id=OLD.source_head_id
     JOIN core_audit a ON a.case_id=n.case_id AND a.actor_id=n.created_by_id
     JOIN core_evidence e ON e.case_id=n.case_id AND a.data->'evidence'=to_jsonb(e.id)
     WHERE n.id=NEW.source_head_id AND n.body=o.body AND n.version>o.version
      AND a.action='factory.delivery_intake_reaffirmed' AND a.data->>'work'=NEW.id::text
      AND a.data->>'previous'=OLD.source_head_id::text AND a.data->>'current'=n.id::text
      AND length(btrim(a.data->>'reason')) BETWEEN 1 AND 2000
      AND coalesce(a.data->>'packet','') ~ '^[a-f0-9]{64}$')
   OR EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity t ON t.id=a.activity_id
     WHERE t.work_id=NEW.id AND t.kind='ACT03' AND a.phase='started' AND a.result->>'schema'='factory-provider-request/v1'
      AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt done WHERE done.activity_id=a.activity_id AND done.number=a.number AND done.phase IN ('observed','failed'))
      AND NOT EXISTS(SELECT 1 FROM workflows_factoryplanningreceipt WHERE attempt_id=a.id))
  THEN RAISE EXCEPTION 'Exact fresh human source instruction and reconciled original effects required'; END IF;
 END IF;
"""
assert SQL.count(' RETURN NEW;')==1
SQL=SQL.replace(' RETURN NEW;',GUARD+' RETURN NEW;')

class Migration(migrations.Migration):
    dependencies=[('workflows','0058_planning_recovery_authority')]
    operations=[migrations.RunSQL(SQL)]
