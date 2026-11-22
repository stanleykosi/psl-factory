from django.db import migrations


SQL = """
CREATE FUNCTION psl_invoice_draft_stopped(cid uuid, invoice_id bigint, artifact_hash text)
RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM core_audit a WHERE a.case_id=cid AND a.action='factory.cancel'
  AND a.data->>'schema'='invoice-draft-stop/v1' AND a.data->'invoice'=to_jsonb(invoice_id)
  AND a.data->>'invoice_sha256'=artifact_hash);
$$;

CREATE FUNCTION psl_invoice_draft_stop_effect_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cid uuid; artifact_hash text;
BEGIN
 SELECT case_id, sha256 INTO cid, artifact_hash FROM finance_invoice WHERE id=NEW.invoice_id;
 -- Both paths serialize on the same case as the native reservation command.
 PERFORM id FROM core_case WHERE id=cid FOR NO KEY UPDATE;
 IF psl_invoice_draft_stopped(cid,NEW.invoice_id,artifact_hash) THEN
  RAISE EXCEPTION 'Exact invoice draft was cancelled before issuance';
 END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION psl_invoice_draft_stop_audit_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE w record; i record; alternative bigint; original_issue bigint;
BEGIN
 IF jsonb_typeof(NEW.data->'work') IS DISTINCT FROM 'number'
    OR jsonb_typeof(NEW.data->'invoice') IS DISTINCT FROM 'number'
    OR jsonb_typeof(NEW.data->'reason') IS DISTINCT FROM 'string'
    OR NEW.data->>'reason' !~ '[^[:space:]]' OR length(NEW.data->>'reason')>2000
    OR COALESCE(jsonb_typeof(NEW.data->'existing_invoice'),'') NOT IN ('null','number')
    OR jsonb_typeof(NEW.data->'existing_invoice') IS DISTINCT FROM jsonb_typeof(NEW.data->'existing_issue') THEN
  RAISE EXCEPTION 'Typed invoice cancellation reason and evidence required';
 END IF;
 SELECT id,case_id,invoice_id,preparation_id,business_key,definition,status,cancel_requested,lease_until INTO w
 FROM workflows_factorywork WHERE id=(NEW.data->>'work')::bigint FOR NO KEY UPDATE;
 PERFORM id FROM core_case WHERE id=NEW.case_id FOR NO KEY UPDATE;
 SELECT id,case_id,preparation_id,obligation_key,sha256 INTO i FROM finance_invoice WHERE id=(NEW.data->>'invoice')::bigint;
 IF w.id IS NULL OR i.id IS NULL OR w.definition<>'pmo-finance/v1' OR w.case_id<>NEW.case_id
    OR i.case_id<>NEW.case_id OR w.status<>'cancelled' OR NOT w.cancel_requested OR w.lease_until IS NOT NULL
    OR w.invoice_id IS DISTINCT FROM i.id OR w.preparation_id IS DISTINCT FROM i.preparation_id
    OR i.obligation_key<>w.business_key OR NEW.data->>'invoice_sha256' IS DISTINCT FROM i.sha256
    OR NOT psl_schedules_grants(NEW.case_id,NEW.actor_id,ARRAY['case.read','finance.read','factory.manage'])
    OR NOT EXISTS(SELECT 1 FROM finance_billingpreparation p WHERE p.id=i.preparation_id AND p.case_id=NEW.case_id)
    OR NOT psl_invoice_draft_stop_source_read(NEW.case_id,i.preparation_id,NEW.actor_id)
    OR psl_invoice_draft_stopped(NEW.case_id,i.id,i.sha256)
    OR EXISTS(SELECT 1 FROM finance_invoicejob j WHERE j.invoice_id=i.id)
    OR EXISTS(SELECT 1 FROM finance_invoiceissue f WHERE f.invoice_id=i.id)
    OR EXISTS(SELECT 1 FROM finance_invoicedelivery d WHERE d.invoice_id=i.id)
    OR EXISTS(SELECT 1 FROM finance_invoicejob j JOIN finance_invoice n ON n.id=j.invoice_id
        WHERE n.case_id=w.case_id AND n.obligation_key=w.business_key AND j.kind IN ('issue','deliver')
         AND (j.intent->'factory_execution'->'work'=to_jsonb(w.id)
          OR EXISTS(SELECT 1 FROM workflows_factoryactivity a JOIN workflows_factoryattempt t ON t.activity_id=a.id
           WHERE a.work_id=w.id AND a.kind IN ('ACT11','ACT12') AND t.phase='observed'
            AND (t.result->'job'=to_jsonb(j.id) OR t.result->'dispatch_job'=to_jsonb(j.id)))))
    OR EXISTS(SELECT 1 FROM workflows_factoryactivity a JOIN workflows_factoryattempt t ON t.activity_id=a.id
        WHERE a.work_id=w.id AND a.kind='ACT03' AND t.phase='started'
         AND t.result->>'schema'='factory-provider-request/v1'
         AND NOT EXISTS(SELECT 1 FROM workflows_factoryplanningreceipt r WHERE r.attempt_id=t.id)
         AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt settled WHERE settled.activity_id=a.id
                         AND settled.number=t.number AND settled.phase IN ('observed','failed'))) THEN
  RAISE EXCEPTION 'Exact stopped invoice draft and current authority required before recording cancellation';
 END IF;
 alternative:=(NEW.data->>'existing_invoice')::bigint;
 original_issue:=(NEW.data->>'existing_issue')::bigint;
 IF alternative IS NOT NULL AND NOT EXISTS(
  SELECT 1 FROM finance_invoiceissue f JOIN finance_invoice n ON n.id=f.invoice_id
   JOIN finance_invoicejob j ON j.id=f.job_id JOIN finance_billingpreparation p ON p.id=n.preparation_id
  WHERE f.id=original_issue AND n.id=alternative AND n.id<>i.id
   AND n.case_id=w.case_id AND p.case_id=w.case_id AND n.obligation_key=w.business_key
   AND f.obligation_key=n.obligation_key AND f.sha256=n.sha256
   AND j.invoice_id=n.id AND j.kind='issue' AND j.status='confirmed'
   AND psl_invoice_draft_stop_source_read(w.case_id,p.id,NEW.actor_id)) THEN
  RAISE EXCEPTION 'Exact issued invoice for this billing obligation required';
 END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION psl_invoice_draft_stop_source_read(cid uuid, pid bigint, uid bigint)
RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_billingpreparation p WHERE p.id=pid AND p.case_id=cid
  AND (p.kind<>'fixed_contract' OR EXISTS(
   SELECT 1 FROM finance_coveragefixedcharge f JOIN finance_coverageassessment a ON a.id=f.assessment_id
    JOIN finance_coverageterms t ON t.id=a.terms_id JOIN finance_coveragesource r ON r.id=t.register_id
    JOIN finance_coveragesource c ON c.id=t.contract_id
   WHERE f.id=p.fixed_charge_id AND t.case_id=cid AND r.case_id=cid AND c.case_id=cid
    AND psl_fixed_reference(cid,uid,r.reference,'read') AND psl_fixed_reference(cid,uid,c.reference,'read'))));
$$;

CREATE TRIGGER psl_invoice_draft_stop_audit BEFORE INSERT ON core_audit FOR EACH ROW
 WHEN (NEW.action='factory.cancel' AND NEW.data->>'schema'='invoice-draft-stop/v1')
 EXECUTE FUNCTION psl_invoice_draft_stop_audit_guard();
CREATE TRIGGER psl_invoice_draft_stop_effect BEFORE INSERT ON finance_invoicejob FOR EACH ROW
 EXECUTE FUNCTION psl_invoice_draft_stop_effect_guard();
CREATE TRIGGER psl_invoice_draft_stop_effect BEFORE INSERT ON finance_invoicedelivery FOR EACH ROW
 EXECUTE FUNCTION psl_invoice_draft_stop_effect_guard();
"""

REVERSE_SQL = """
DROP TRIGGER psl_invoice_draft_stop_effect ON finance_invoicedelivery;
DROP TRIGGER psl_invoice_draft_stop_effect ON finance_invoicejob;
DROP TRIGGER psl_invoice_draft_stop_audit ON core_audit;
DROP FUNCTION psl_invoice_draft_stop_source_read(uuid,bigint,bigint);
DROP FUNCTION psl_invoice_draft_stop_audit_guard();
DROP FUNCTION psl_invoice_draft_stop_effect_guard();
DROP FUNCTION psl_invoice_draft_stopped(uuid,bigint,text);
"""


class Migration(migrations.Migration):
    dependencies = [
        ('finance', '0084_payroll_draft_match_guard'),
        ('workflows', '0084_invoice_preparation_binding'),
    ]
    operations = [migrations.RunSQL(SQL, REVERSE_SQL)]
