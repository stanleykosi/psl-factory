from django.db import migrations

SQL="""
CREATE OR REPLACE FUNCTION psl_factory_execution_binding_scope() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM workflows_factorywork w JOIN policy_configuration c ON c.case_id=w.case_id
   JOIN core_evidence e ON e.case_id=w.case_id
   JOIN policy_registeredreference r ON r.case_id=c.case_id
    AND r.ref=c.envelope->'value'->>'artifact_ref'
    AND r.version=(c.envelope->'value'->>'artifact_version')::integer
    AND r.sha256=c.envelope->'value'->>'sha256'
    AND r.schema_ref='schema:psl/factory-recovery-authority/v1'
   WHERE w.id=NEW.work_id AND c.id=NEW.configuration_id AND c.component='OPS.factory_recovery_authority'
    AND e.id=NEW.evidence_id AND e.kind='policy_decision'
    AND r.content->'rules' @> jsonb_build_array(NEW.rule)
    AND (SELECT state FROM policy_policystate WHERE configuration_id=c.id ORDER BY id DESC LIMIT 1)='active'
    AND NEW.rule->>'method'='reviewed_execution_principal_v1' AND NEW.rule->>'review_role' IS NOT NULL
    AND NEW.rule->'independent_of_worker' IN ('true'::jsonb,'false'::jsonb)
    AND (NEW.rule->'independent_of_worker'='false'::jsonb OR NEW.principal_id<>NEW.reviewer_id)
    AND (NEW.rule->>'valid_from')::timestamptz<=statement_timestamp() AND statement_timestamp()<(NEW.rule->>'valid_until')::timestamptz
    AND NEW.previous_id IS NOT DISTINCT FROM w.execution_binding_id AND NEW.work_revision=w.revision+1
    AND NEW.rule->>'definition'=w.definition
    AND (NEW.rule->>'principal_id')::bigint=NEW.principal_id AND (NEW.rule->>'reviewer_id')::bigint=NEW.reviewer_id)
 THEN RAISE EXCEPTION 'Exact active registered recovery rule, same-work evidence and current predecessor required'; END IF;
 IF NEW.sequence<>COALESCE((SELECT sequence+1 FROM workflows_factoryexecutionbinding WHERE id=NEW.previous_id AND work_id=NEW.work_id),1)
 THEN RAISE EXCEPTION 'Execution recovery sequence cannot fork or skip history'; END IF;
 RETURN NEW;
END $$;
"""

class Migration(migrations.Migration):
    dependencies=[('workflows','0052_factory_execution_binding')]
    operations=[migrations.RunSQL(SQL)]
