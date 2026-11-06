from django.db import migrations

SQL=r"""
CREATE FUNCTION psl_domain_contract_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE c workflows_domaincontract; p workflows_reconstitutionplan; o workflows_domainobservation;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'domain contract history is immutable'; END IF;
 IF TG_TABLE_NAME='workflows_domaincontract' THEN
   SELECT * INTO p FROM workflows_reconstitutionplan WHERE id=NEW.plan_id;
   IF NEW.kind NOT IN ('provider','destination') OR NEW.version<1 OR length(NEW.reference)=0 OR NEW.sha256 !~ '^[a-f0-9]{64}$' OR
      NOT EXISTS(SELECT 1 FROM core_evidence e WHERE e.id=NEW.evidence_id AND e.case_id=p.case_id AND e.kind='integration_contract') OR
      NEW.payload->>'implementation' NOT IN ('authenticated_json_v1','reference_only') OR
      NOT NEW.payload ?& ARRAY['implementation','target_key','credential_ref','credential_revision','principal_ref','provider_ref','contract_version'] THEN
      RAISE EXCEPTION 'typed same-case evidenced domain contract required'; END IF;
   IF NEW.kind='destination' AND (NEW.payload->>'destination_ref' IS DISTINCT FROM p.payload->>'destination_ref' OR
      NEW.payload->'activation_enabled' IS DISTINCT FROM 'false'::jsonb OR NEW.payload->'archived_authority_accepted' IS DISTINCT FROM 'false'::jsonb OR
      NOT NEW.payload ?& ARRAY['identity_ref','database_ref','store_ref','provisioning_ref','outbound_ref']) THEN RAISE EXCEPTION 'inert intended destination required'; END IF;
   IF NEW.kind='provider' AND (NEW.payload->>'operation_mapping' IS DISTINCT FROM 'sha256_original_operation_key_v1' OR
      NEW.payload->>'intent_mapping' IS DISTINCT FROM 'postgres_jsonb_archived_job_row_sha256_v1' OR
      NEW.payload->>'evidence_semantics' IS DISTINCT FROM 'authenticated_remote_receipt_claim' OR NOT NEW.payload ? 'family') THEN
      RAISE EXCEPTION 'reviewed metadata mapping; no vendor-proof inference'; END IF;
   RETURN NEW;
 END IF;
 SELECT * INTO c FROM workflows_domaincontract WHERE id=NEW.contract_id;
 SELECT * INTO p FROM workflows_reconstitutionplan WHERE id=c.plan_id;
 IF NEW.pin->>'contract_sha256' IS DISTINCT FROM c.sha256 OR
    NEW.pin->'reconstitution'->>'plan_sha256' IS DISTINCT FROM p.sha256 OR
    NEW.pin->'reconstitution'->>'runtime_sha256' IS DISTINCT FROM p.payload->'inventory'->>'runtime_sha256' OR
    NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=NEW.pin->>'policy' AND case_id=p.case_id AND component='OPS.domain_contracts') OR
    NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=NEW.pin->'reconstitution'->>'policy' AND case_id=p.case_id AND component='OPS.reconstitution') OR
    NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=NEW.pin->'reconstitution'->>'role_policy' AND case_id=p.case_id AND component='D05.role_principal_assignments') THEN
    RAISE EXCEPTION 'exact same-case contract and policy lineage required'; END IF;
 IF TG_TABLE_NAME='workflows_domainobservation' THEN
   IF NEW.request->>'contract_sha256' IS DISTINCT FROM c.sha256 OR NEW.request->>'plan_sha256' IS DISTINCT FROM p.sha256 OR
      NEW.request->>'archive_sha256' IS DISTINCT FROM (SELECT receipt->>'archive_sha256' FROM workflows_coldrecoveryjob WHERE id=p.recovery_id) OR
      NEW.request->>'destination_ref' IS DISTINCT FROM p.payload->>'destination_ref' OR
      NEW.result->>'provider_ref' IS DISTINCT FROM c.payload->>'provider_ref' OR
      NEW.result->>'principal_ref' IS DISTINCT FROM c.payload->>'principal_ref' OR
      NEW.result->>'contract_version' IS DISTINCT FROM c.payload->>'contract_version' OR
      NEW.result->'direct_vendor_verification' IS DISTINCT FROM 'false'::jsonb OR
      NEW.result->'activation_enabled' IS DISTINCT FROM 'false'::jsonb OR NEW.result->'business_jobs_reenacted' IS DISTINCT FROM 'false'::jsonb THEN
      RAISE EXCEPTION 'exact non-activating authenticated observation required'; END IF;
   IF c.kind='provider' AND (NEW.request->'effect'->>'effect_key' IS DISTINCT FROM NEW.effect_key OR
      NEW.request->'effect'->>'family' IS DISTINCT FROM c.payload->>'family' OR
      NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p.payload->'inventory'->'effects') r WHERE
        r->>'effect_key'=NEW.effect_key AND r->>'family'=c.payload->>'family' AND
        r->>'case_id'=NEW.request->'effect'->>'case_id' AND
        r->>'operation_sha256'=NEW.request->'effect'->>'operation_sha256' AND
        r->>'intent_sha256'=NEW.request->'effect'->>'intent_sha256') OR
      coalesce(NEW.result->>'outcome','') NOT IN ('present','unknown','conflict')) THEN RAISE EXCEPTION 'exact inventoried family/effect metadata required'; END IF;
   IF c.kind='destination' AND (NEW.effect_key<>'' OR NEW.result->'provisioning_executed' IS DISTINCT FROM 'false'::jsonb) THEN RAISE EXCEPTION 'read-only destination preflight required'; END IF;
 ELSE
   IF NEW.verdict NOT IN ('approve','hold') OR length(trim(NEW.rationale))=0 OR NEW.actor_id=c.actor_id OR
      EXISTS(SELECT 1 FROM workflows_domainobservation WHERE contract_id=c.id AND actor_id=NEW.actor_id) THEN RAISE EXCEPTION 'independent explicit source-owned review required'; END IF;
   IF NEW.observation_id IS NOT NULL THEN
     SELECT * INTO o FROM workflows_domainobservation WHERE id=NEW.observation_id;
     IF o.contract_id IS DISTINCT FROM c.id OR NEW.pin->>'observation' IS DISTINCT FROM o.id::text OR
        NEW.pin - ARRAY['observation','observation_sha256'] IS DISTINCT FROM o.pin THEN RAISE EXCEPTION 'exact same-contract observation review required'; END IF;
   ELSIF NEW.pin->'observation' IS DISTINCT FROM 'null'::jsonb OR NEW.pin->'observation_sha256' IS DISTINCT FROM 'null'::jsonb THEN RAISE EXCEPTION 'contract-only review binding required'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER domain_contract_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_domaincontract FOR EACH ROW EXECUTE FUNCTION psl_domain_contract_guard();
CREATE TRIGGER domain_observation_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_domainobservation FOR EACH ROW EXECUTE FUNCTION psl_domain_contract_guard();
CREATE TRIGGER domain_review_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_domaincontractreview FOR EACH ROW EXECUTE FUNCTION psl_domain_contract_guard();
"""

class Migration(migrations.Migration):
    dependencies=[('workflows','0028_domain_contracts')]
    operations=[migrations.RunSQL(SQL,reverse_sql=migrations.RunSQL.noop)]
