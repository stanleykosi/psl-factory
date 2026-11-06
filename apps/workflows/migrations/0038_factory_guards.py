from django.db import migrations

SQL=r"""
CREATE FUNCTION psl_factory_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Factory history cannot be deleted'; END IF;
 IF TG_TABLE_NAME='workflows_factorywork' AND TG_OP='UPDATE' THEN
  IF (NEW.case_id,NEW.actor_id,NEW.key,NEW.definition,NEW.request,NEW.request_hash,NEW.created_at)
    IS DISTINCT FROM (OLD.case_id,OLD.actor_id,OLD.key,OLD.definition,OLD.request,OLD.request_hash,OLD.created_at)
    OR NEW.budget_used<OLD.budget_used OR NEW.fence<OLD.fence OR NEW.revision<OLD.revision
    OR (OLD.budget_used>0 AND NEW.budget_limit<>OLD.budget_limit)
  THEN RAISE EXCEPTION 'Immutable factory identity and monotonic shared budget required'; END IF;
 END IF;
 IF TG_TABLE_NAME='workflows_factorywork' THEN
  IF (NEW.invoice_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_invoice i WHERE i.id=NEW.invoice_id AND i.case_id=NEW.case_id))
   OR (NEW.preparation_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_billingpreparation p WHERE p.id=NEW.preparation_id AND p.case_id=NEW.case_id))
   OR (NEW.policy_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM policy_configuration p WHERE p.id=NEW.policy_id AND p.case_id=NEW.case_id AND p.component='OPS.factory_execution'))
  THEN RAISE EXCEPTION 'Same-case native factory references required'; END IF;
 END IF;
 IF TG_TABLE_NAME='workflows_factorywork' AND NEW.status='verified' THEN
  IF NOT EXISTS(SELECT 1 FROM finance_invoiceissue i JOIN finance_invoicedelivery d ON d.invoice_id=i.invoice_id
    JOIN finance_invoice n ON n.id=i.invoice_id WHERE n.id=NEW.invoice_id AND n.case_id=NEW.case_id
    AND i.sha256=n.sha256 AND i.payload=n.payload)
  THEN RAISE EXCEPTION 'Native invoice receipts required; agent completion is not verification'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_factory_identity BEFORE INSERT OR UPDATE OR DELETE ON workflows_factorywork
 FOR EACH ROW EXECUTE FUNCTION psl_factory_identity();
CREATE FUNCTION psl_factory_activity_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Factory activity cannot be deleted'; END IF;
 IF TG_OP='UPDATE' AND (NEW.work_id,NEW.parent_id,NEW.kind,NEW.key,NEW.plan_revision)
  IS DISTINCT FROM (OLD.work_id,OLD.parent_id,OLD.kind,OLD.key,OLD.plan_revision)
 THEN RAISE EXCEPTION 'Factory activity identity is immutable'; END IF;
 IF NEW.parent_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM workflows_factoryactivity p WHERE p.id=NEW.parent_id AND p.work_id=NEW.work_id)
 THEN RAISE EXCEPTION 'Same-work parent required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_factory_activity_identity BEFORE INSERT OR UPDATE OR DELETE ON workflows_factoryactivity
 FOR EACH ROW EXECUTE FUNCTION psl_factory_activity_identity();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON workflows_factoryattempt
 FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE FUNCTION psl_factory_attempt_scope() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NEW.number<1 OR NEW.phase NOT IN ('started','observed','failed') THEN RAISE EXCEPTION 'Closed factory attempt event required'; END IF;
 IF NEW.agent_run_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM agents_agentrun a
  JOIN workflows_factoryactivity t ON t.id=NEW.activity_id JOIN workflows_factorywork w ON w.id=t.work_id
  WHERE a.id=NEW.agent_run_id AND a.case_id=w.case_id)
 THEN RAISE EXCEPTION 'Same-case AgentRun required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_factory_attempt_scope BEFORE INSERT ON workflows_factoryattempt FOR EACH ROW EXECUTE FUNCTION psl_factory_attempt_scope();
CREATE FUNCTION psl_factory_task_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='UPDATE' AND (NEW.kind,NEW.context,NEW.factory_key) IS DISTINCT FROM (OLD.kind,OLD.context,OLD.factory_key)
 THEN RAISE EXCEPTION 'Human task packet and source identity are immutable'; END IF;
 IF NEW.kind='document_review' AND NEW.version_id IS NULL THEN RAISE EXCEPTION 'Document review version required'; END IF;
 IF NEW.kind<>'document_review' AND (NEW.version_id IS NOT NULL OR NEW.factory_key IS NULL OR NEW.kind NOT IN ('factory_information','factory_review'))
 THEN RAISE EXCEPTION 'Closed factory task contract required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_factory_task_identity BEFORE INSERT OR UPDATE ON workflows_humantask
 FOR EACH ROW EXECUTE FUNCTION psl_factory_task_identity();
"""

class Migration(migrations.Migration):
    dependencies=[('workflows','0037_factory_coordination'),('finance','0062_exact_publication_review')]
    operations=[migrations.RunSQL(SQL,reverse_sql=migrations.RunSQL.noop)]
