from django.db import migrations
SQL=r"""
CREATE FUNCTION psl_complaint_summary_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE c core_case; r baas_complaintsummaryrequest; v baas_complaintsummaryversion;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Complaint summary evidence is immutable'; END IF;
 IF TG_TABLE_NAME='baas_complaintsummaryrequest' THEN
  SELECT * INTO c FROM core_case WHERE id=NEW.case_id;
  IF c.kind IS DISTINCT FROM 'support' OR NOT EXISTS(SELECT 1 FROM core_evidence WHERE id=NEW.evidence_id AND case_id=c.id AND kind='agent_private_support_summary_request') THEN RAISE EXCEPTION 'Same-workspace private summary request evidence required'; END IF;
 ELSIF TG_TABLE_NAME='baas_complaintsummaryversion' THEN
  SELECT * INTO r FROM baas_complaintsummaryrequest WHERE id=NEW.request_id;
  IF NEW.result->>'format' IS DISTINCT FROM 'psl.complaint-summary/v1' OR NEW.result->>'request_id' IS DISTINCT FROM NEW.request_id::text OR NEW.result->>'workspace_case_id' IS DISTINCT FROM r.case_id::text
     OR NEW.result->'source_bodies_included' IS DISTINCT FROM 'false'::jsonb OR NEW.result->'financial_execution_authorized' IS DISTINCT FROM 'false'::jsonb OR NEW.result->'corrective_credit_authorized' IS DISTINCT FROM 'false'::jsonb
     OR NEW.sha256 !~ '^[a-f0-9]{64}$' OR NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=NEW.pin->>'scope_policy' AND case_id=r.case_id AND component='B14.summary_scope') THEN
   RAISE EXCEPTION 'Exact inert summary source/scope contract required'; END IF;
 ELSE
  SELECT * INTO v FROM baas_complaintsummaryversion WHERE id=NEW.version_id;
  SELECT * INTO r FROM baas_complaintsummaryrequest WHERE id=v.request_id;
  IF NEW.verdict NOT IN ('approve','return','withdraw') OR NEW.pin->>'version_sha256' IS DISTINCT FROM v.sha256
     OR NOT EXISTS(SELECT 1 FROM core_evidence WHERE id=NEW.evidence_id AND case_id=r.case_id AND kind='agent_private_support_summary_review')
     OR NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=NEW.pin->>'review_policy' AND case_id=r.case_id AND component='B14.summary_review') THEN
   RAISE EXCEPTION 'Exact summary human review version and private source scope required'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER complaint_summary_guard BEFORE INSERT OR UPDATE OR DELETE ON baas_complaintsummaryrequest FOR EACH ROW EXECUTE FUNCTION psl_complaint_summary_guard();
CREATE TRIGGER complaint_summary_guard BEFORE INSERT OR UPDATE OR DELETE ON baas_complaintsummaryversion FOR EACH ROW EXECUTE FUNCTION psl_complaint_summary_guard();
CREATE TRIGGER complaint_summary_guard BEFORE INSERT OR UPDATE OR DELETE ON baas_complaintsummaryreview FOR EACH ROW EXECUTE FUNCTION psl_complaint_summary_guard();
"""
class Migration(migrations.Migration):
    dependencies=[('baas','0016_complaint_summaries')]
    operations=[migrations.RunSQL(SQL,'DROP TRIGGER complaint_summary_guard ON baas_complaintsummaryreview; DROP TRIGGER complaint_summary_guard ON baas_complaintsummaryversion; DROP TRIGGER complaint_summary_guard ON baas_complaintsummaryrequest; DROP FUNCTION psl_complaint_summary_guard();')]
