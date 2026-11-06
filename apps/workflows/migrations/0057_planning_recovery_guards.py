"""Append-only receipt transport reviews and exact original-operation provenance."""
from django.db import migrations

SQL=r"""
CREATE FUNCTION psl_factory_planning_recovery_scope() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a workflows_factoryattempt; w workflows_factorywork; oldc workflows_integrationcontract;
 c workflows_integrationcontract; cfg policy_configuration; e core_evidence; seq bigint; k text;
BEGIN
 SELECT * INTO a FROM workflows_factoryattempt WHERE id=NEW.attempt_id;
 SELECT fw.* INTO w FROM workflows_factorywork fw JOIN workflows_factoryactivity fa ON fa.work_id=fw.id WHERE fa.id=a.activity_id FOR UPDATE OF fw;
 SELECT * INTO oldc FROM workflows_integrationcontract WHERE id=(a.result->>'contract')::bigint;
 SELECT * INTO c FROM workflows_integrationcontract WHERE id=NEW.contract_id;
 SELECT * INTO cfg FROM policy_configuration WHERE id=NEW.configuration_id;
 SELECT * INTO e FROM core_evidence WHERE id=NEW.evidence_id;
 SELECT coalesce(max(sequence),0)+1 INTO seq FROM workflows_factoryplanningrecovery WHERE attempt_id=NEW.attempt_id;
 IF a.id IS NULL OR a.phase<>'started' OR a.result->>'schema'<>'factory-provider-request/v1'
 OR NOT EXISTS(SELECT 1 FROM workflows_factoryactivity WHERE id=a.activity_id AND kind='ACT03')
 OR EXISTS(SELECT 1 FROM workflows_factoryplanningreceipt WHERE attempt_id=a.id)
 OR EXISTS(SELECT 1 FROM workflows_factoryattempt WHERE activity_id=a.activity_id AND number=a.number AND phase IN ('observed','failed'))
 OR NEW.sequence<>seq OR NEW.work_revision<>w.revision OR (w.lease_until IS NOT NULL AND w.lease_until>now())
 OR c.case_id IS DISTINCT FROM w.case_id OR oldc.case_id IS DISTINCT FROM w.case_id
 OR c.reference IS DISTINCT FROM oldc.reference OR c.version<=oldc.version
 OR EXISTS(SELECT 1 FROM workflows_integrationcontract WHERE case_id=c.case_id AND reference=c.reference AND version>c.version)
 OR cfg.case_id IS DISTINCT FROM w.case_id OR cfg.component IS DISTINCT FROM 'OPS.factory_receipt_recovery'
 OR (SELECT state FROM policy_policystate WHERE configuration_id=cfg.id ORDER BY id DESC LIMIT 1) IS DISTINCT FROM 'active'
 OR e.case_id IS DISTINCT FROM w.case_id OR e.kind<>'policy_decision' OR length(btrim(NEW.reason)) NOT BETWEEN 1 AND 2000
 THEN RAISE EXCEPTION 'Exact current original-request recovery review required'; END IF;
 FOREACH k IN ARRAY ARRAY['kind','family','implementation','principal_ref','contract_version','model_id','data_scope'] LOOP
  IF c.payload->k IS DISTINCT FROM oldc.payload->k THEN RAISE EXCEPTION 'Receipt recovery cannot change provider identity or scope'; END IF;
 END LOOP;
 IF c.payload->>'implementation'<>'authenticated_json_v1' OR c.payload->>'kind'<>'provider'
 OR NOT (c.payload->'capabilities' ? 'receipt_lookup') THEN RAISE EXCEPTION 'Authenticated original receipt lookup required'; END IF;
 FOREACH k IN ARRAY ARRAY['implementation','target','classification','auth_mode'] LOOP
  IF NEW.binding->k IS DISTINCT FROM a.result->'binding'->k OR NOT (NEW.binding ? k)
  THEN RAISE EXCEPTION 'Original receipt destination cannot change'; END IF;
 END LOOP;
 IF jsonb_typeof(NEW.authority) IS DISTINCT FROM 'object' OR NOT (NEW.authority ?& ARRAY['rule','readiness','pins'])
 OR NEW.authority->'rule'->>'method' IS DISTINCT FROM 'same_provider_receipt_lookup_v1'
 OR NEW.authority->'rule'->'reviewer_id' IS DISTINCT FROM to_jsonb(NEW.reviewer_id)
 OR jsonb_typeof(NEW.authority->'rule'->'review_role') IS DISTINCT FROM 'string'
 OR jsonb_typeof(NEW.authority->'rule'->'independent_of_requester') IS DISTINCT FROM 'boolean'
 OR jsonb_typeof(NEW.authority->'rule'->'valid_from') IS DISTINCT FROM 'string'
 OR jsonb_typeof(NEW.authority->'rule'->'valid_until') IS DISTINCT FROM 'string'
 OR (NEW.authority->'rule'->>'valid_from')::timestamptz>now()
 OR (NEW.authority->'rule'->>'valid_until')::timestamptz<=now()
 OR NOT EXISTS(SELECT 1 FROM policy_registeredreference r WHERE r.case_id=w.case_id
   AND r.ref=cfg.envelope->'value'->>'artifact_ref' AND r.version=(cfg.envelope->'value'->>'artifact_version')::int
   AND r.sha256=cfg.envelope->'value'->>'sha256' AND r.content=NEW.authority->'rule')
 THEN RAISE EXCEPTION 'Exact registered current receipt recovery authority required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_factory_planning_recovery_scope BEFORE INSERT ON workflows_factoryplanningrecovery FOR EACH ROW EXECUTE FUNCTION psl_factory_planning_recovery_scope();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON workflows_factoryplanningrecovery FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE FUNCTION psl_factory_planning_receipt_use_scope() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM workflows_factoryplanningreceipt p JOIN workflows_factoryplanningrecovery r ON r.attempt_id=p.attempt_id
 JOIN workflows_factoryattempt a ON a.id=p.attempt_id WHERE p.id=NEW.receipt_id AND r.id=NEW.recovery_id AND p.binding=a.result->'binding')
 THEN RAISE EXCEPTION 'Exact original receipt and reviewed transport required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_factory_planning_receipt_use_scope BEFORE INSERT ON workflows_factoryplanningreceiptuse FOR EACH ROW EXECUTE FUNCTION psl_factory_planning_receipt_use_scope();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON workflows_factoryplanningreceiptuse FOR EACH ROW EXECUTE FUNCTION psl_append_only();
"""

class Migration(migrations.Migration):
    dependencies=[('workflows','0056_factory_planning_recovery')]
    operations=[migrations.RunSQL(SQL)]
