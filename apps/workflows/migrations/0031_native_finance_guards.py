from django.db import migrations
SQL=r"""
CREATE FUNCTION psl_native_finance_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE m workflows_nativefinancemapping; p workflows_reconstitutionplan; o workflows_nativefinanceobservation; k workflows_nativefinancepacket; r workflows_nativefinancereview; proof jsonb;
BEGIN
 IF TG_OP='DELETE' OR (TG_OP='UPDATE' AND TG_TABLE_NAME<>'workflows_nativefinancepublicationjob') THEN RAISE EXCEPTION 'native Finance evidence history is immutable'; END IF;
 IF TG_TABLE_NAME='workflows_nativefinancemapping' THEN
   SELECT * INTO p FROM workflows_reconstitutionplan WHERE id=NEW.plan_id;
   IF NEW.version<1 OR NEW.sha256 !~ '^[a-f0-9]{64}$' OR length(NEW.reference)=0 OR length(NEW.provider_ref)=0 OR
      NEW.payload->>'contract_version' IS DISTINCT FROM 'psl.internal-finance-handoff/v1' OR NEW.payload->>'effect_key' IS DISTINCT FROM NEW.effect_key OR
      NEW.payload - ARRAY['contract_version','effect_key','source_case_id','source_milestone_id','operation_sha256','source_row_sha256','payload_sha256']<>'{}' OR
      coalesce(NEW.payload->>'payload_sha256','') !~ '^[a-f0-9]{64}$' OR
      NOT EXISTS(SELECT 1 FROM core_evidence WHERE id=NEW.evidence_id AND case_id=p.case_id AND kind='integration_contract') OR
      NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p.payload->'inventory'->'effects') e WHERE e->>'effect_key'=NEW.effect_key AND e->>'family'='handoff' AND e->>'case_id'=NEW.payload->>'source_case_id' AND e->>'operation_sha256'=NEW.payload->>'operation_sha256' AND e->>'intent_sha256'=NEW.payload->>'source_row_sha256') THEN
       RAISE EXCEPTION 'exact same-case original Finance mapping required'; END IF;
   RETURN NEW;
 END IF;
 IF TG_TABLE_NAME='workflows_nativefinancepublicationjob' THEN
   SELECT * INTO k FROM workflows_nativefinancepacket WHERE id=NEW.packet_id;
   SELECT * INTO m FROM workflows_nativefinancemapping WHERE id=k.mapping_id;
   proof=NEW.intent->'pin';
 ELSE
   SELECT * INTO m FROM workflows_nativefinancemapping WHERE id=NEW.mapping_id;
   IF TG_TABLE_NAME<>'workflows_nativefinancepacket' THEN proof=NEW.pin; END IF;
 END IF;
 SELECT * INTO p FROM workflows_reconstitutionplan WHERE id=m.plan_id;
 IF TG_TABLE_NAME='workflows_nativefinancepacket' THEN
   SELECT * INTO o FROM workflows_nativefinanceobservation WHERE id=NEW.observation_id;
   IF o.mapping_id IS DISTINCT FROM m.id OR NEW.version<1 OR NEW.sha256 !~ '^[a-f0-9]{64}$' OR
      NEW.payload->>'format' IS DISTINCT FROM 'psl.native-finance-companion/v1' OR NEW.payload->>'scope' IS DISTINCT FROM 'single_handoff_companion' OR
      NEW.payload->>'mapping_sha256' IS DISTINCT FROM m.sha256 OR NEW.payload->>'effect_key' IS DISTINCT FROM m.effect_key OR
      NEW.payload->>'native_observation' IS DISTINCT FROM o.id::text OR NEW.payload->'native_result' IS DISTINCT FROM o.result OR
      NOT EXISTS(SELECT 1 FROM workflows_domainobservation d JOIN workflows_domaincontract c ON c.id=d.contract_id WHERE d.id=NEW.destination_id AND c.plan_id=m.plan_id AND c.kind='destination') OR
      NEW.payload->'activation_enabled' IS DISTINCT FROM 'false'::jsonb OR NEW.payload->'business_jobs_reenacted' IS DISTINCT FROM 'false'::jsonb OR
      NEW.payload->'debt_waived' IS DISTINCT FROM 'false'::jsonb OR NEW.payload->'archived_authority_accepted' IS DISTINCT FROM 'false'::jsonb THEN
      RAISE EXCEPTION 'exact same-plan inert native Finance companion required'; END IF;
   RETURN NEW;
 END IF;
 IF proof->>'mapping_sha256' IS DISTINCT FROM m.sha256 OR proof->'reconstitution'->>'plan_sha256' IS DISTINCT FROM p.sha256 OR
    NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=proof->>'policy' AND case_id=p.case_id AND component='OPS.native_finance_receipts') OR
    NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=proof->'reconstitution'->>'policy' AND case_id=p.case_id AND component='OPS.reconstitution') OR
    NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=proof->'reconstitution'->>'role_policy' AND case_id=p.case_id AND component='D05.role_principal_assignments') OR
    proof->'provider'->>'provider_ref' IS DISTINCT FROM m.provider_ref THEN RAISE EXCEPTION 'exact native Finance policy/provider lineage required'; END IF;
 IF TG_TABLE_NAME='workflows_nativefinanceobservation' THEN
   IF coalesce(NEW.result->>'outcome','') NOT IN ('present','unknown','conflict') OR
      NEW.result->>'classification' IS DISTINCT FROM 'native_postgres_finance_receipt' OR
      NEW.result->'direct_native_verification' IS DISTINCT FROM 'true'::jsonb OR NEW.result->'direct_vendor_verification' IS DISTINCT FROM 'false'::jsonb OR
      NEW.result->'business_jobs_reenacted' IS DISTINCT FROM 'false'::jsonb OR NEW.result->'debt_waived' IS DISTINCT FROM 'false'::jsonb OR
      ((NEW.result->>'outcome'='present') IS DISTINCT FROM (jsonb_typeof(NEW.result->'receipt_ref')='string' AND coalesce(NEW.result->>'receipt_sha256','') ~ '^[a-f0-9]{64}$')) THEN
      RAISE EXCEPTION 'typed native Finance result; unknown is not absence proof'; END IF;
   RETURN NEW;
 END IF;
 IF TG_TABLE_NAME='workflows_nativefinancereview' THEN
   IF NEW.actor_id=m.actor_id OR EXISTS(SELECT 1 FROM workflows_nativefinanceobservation WHERE mapping_id=m.id AND actor_id=NEW.actor_id) OR
      NEW.verdict NOT IN ('approve','hold') OR length(trim(NEW.rationale))=0 THEN RAISE EXCEPTION 'independent Finance human review required'; END IF;
   IF NEW.observation_id IS NOT NULL THEN
     SELECT * INTO o FROM workflows_nativefinanceobservation WHERE id=NEW.observation_id;
     IF o.mapping_id IS DISTINCT FROM m.id OR NEW.pin - ARRAY['observation_sha256','packet_sha256'] IS DISTINCT FROM o.pin THEN RAISE EXCEPTION 'same-mapping native observation review required'; END IF;
   END IF;
   IF NEW.packet_id IS NOT NULL THEN
     SELECT * INTO k FROM workflows_nativefinancepacket WHERE id=NEW.packet_id;
     IF k.mapping_id IS DISTINCT FROM m.id OR NEW.pin->>'packet_sha256' IS DISTINCT FROM k.sha256 THEN RAISE EXCEPTION 'same-mapping exact companion review required'; END IF;
   END IF;
   RETURN NEW;
 END IF;
 IF TG_OP='UPDATE' AND (NEW.packet_id,NEW.operation_key,NEW.intent,NEW.actor_id,NEW.created_at) IS DISTINCT FROM (OLD.packet_id,OLD.operation_key,OLD.intent,OLD.actor_id,OLD.created_at) THEN RAISE EXCEPTION 'companion publication intent is immutable'; END IF;
 IF TG_OP='UPDATE' AND (NEW.attempts<OLD.attempts OR NEW.fence<OLD.fence OR (OLD.receipt IS NOT NULL AND (NEW.receipt IS DISTINCT FROM OLD.receipt OR NEW.status<>'confirmed'))) THEN RAISE EXCEPTION 'publication receipt/fence history is immutable'; END IF;
 SELECT * INTO r FROM workflows_nativefinancereview WHERE id::text=NEW.intent->>'authorization';
 IF NEW.status NOT IN ('pending','leased','unknown','held','confirmed') OR NEW.operation_key !~ '^[a-f0-9]{64}$' OR
    NEW.intent->>'format' IS DISTINCT FROM 'psl.native-finance-companion/v1' OR NEW.intent->>'operation_key' IS DISTINCT FROM NEW.operation_key OR
    NEW.intent->>'packet_sha256' IS DISTINCT FROM k.sha256 OR NEW.intent->'manifest' IS DISTINCT FROM k.payload OR
    r.packet_id IS DISTINCT FROM k.id OR r.verdict IS DISTINCT FROM 'approve' OR r.pin - ARRAY['observation_sha256','packet_sha256'] IS DISTINCT FROM proof OR
    NEW.intent->>'store_binding' IS DISTINCT FROM proof->>'store_binding' THEN RAISE EXCEPTION 'exact independently reviewed inert companion publication required'; END IF;
 IF NEW.status='confirmed' AND NEW.receipt IS NULL THEN RAISE EXCEPTION 'confirmed companion requires immutable file receipt'; END IF;
 IF NEW.receipt IS NOT NULL AND (NEW.receipt->>'format' IS DISTINCT FROM NEW.intent->>'format' OR
    NEW.receipt->>'operation_key' IS DISTINCT FROM NEW.operation_key OR NEW.receipt->'payload' IS DISTINCT FROM k.payload OR
    NEW.receipt->'activation_enabled' IS DISTINCT FROM 'false'::jsonb OR NEW.receipt->'business_jobs_reenacted' IS DISTINCT FROM 'false'::jsonb OR
    NEW.receipt - ARRAY['format','operation_key','intent_sha256','payload','payload_sha256','activation_enabled','business_jobs_reenacted']<>'{}') THEN RAISE EXCEPTION 'exact non-activating companion receipt required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER native_finance_mapping_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_nativefinancemapping FOR EACH ROW EXECUTE FUNCTION psl_native_finance_guard();
CREATE TRIGGER native_finance_observation_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_nativefinanceobservation FOR EACH ROW EXECUTE FUNCTION psl_native_finance_guard();
CREATE TRIGGER native_finance_packet_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_nativefinancepacket FOR EACH ROW EXECUTE FUNCTION psl_native_finance_guard();
CREATE TRIGGER native_finance_review_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_nativefinancereview FOR EACH ROW EXECUTE FUNCTION psl_native_finance_guard();
CREATE TRIGGER native_finance_publication_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_nativefinancepublicationjob FOR EACH ROW EXECUTE FUNCTION psl_native_finance_guard();
"""
class Migration(migrations.Migration):
    dependencies=[('workflows','0030_native_finance')]
    operations=[migrations.RunSQL(SQL,reverse_sql=migrations.RunSQL.noop)]
