# Actual fixed-contract bridge after accepted allocation0066; guards frozen inline.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


FORWARD_SQL = r"""
-- New fixed-contract path only. Historical native stage/usage semantics stay unchanged.
CREATE FUNCTION psl_fixed_json(value jsonb) RETURNS text LANGUAGE plpgsql IMMUTABLE STRICT AS $$
DECLARE output text;
BEGIN
 IF jsonb_typeof(value)='object' THEN
  SELECT '{'||COALESCE(string_agg(to_jsonb(key)::text||':'||psl_fixed_json(val),',' ORDER BY key COLLATE "C"),'')||'}' INTO output FROM jsonb_each(value) e(key,val);
 ELSIF jsonb_typeof(value)='array' THEN
  SELECT '['||COALESCE(string_agg(psl_fixed_json(val),',' ORDER BY pos),'')||']' INTO output FROM jsonb_array_elements(value) WITH ORDINALITY e(val,pos);
 ELSE output:=value::text; END IF;
 RETURN output;
END $$;
CREATE FUNCTION psl_fixed_obligation(fid bigint) RETURNS text LANGUAGE sql STABLE AS $$
 SELECT encode(sha256(convert_to(psl_fixed_json(jsonb_build_object(
 'implementation','fixed-service-obligation/v1','case',t.case_id::text,
 'register',jsonb_build_object('system',r.payload->>'system','external_id',r.payload->>'external_id'),
 'contract',jsonb_build_object('system',c.payload->>'system','external_id',c.payload->>'external_id'),
 'customer',b.customer,'service',b.service,'contract_reference',b.contract,
 'period',jsonb_build_object('start',f.payload->'period'->>'start','end',f.payload->'period'->>'end'))),'UTF8')),'hex')
 FROM finance_coveragefixedcharge f JOIN finance_coverageassessment a ON a.id=f.assessment_id
 JOIN finance_coverageterms t ON t.id=a.terms_id JOIN finance_coveragesource r ON r.id=t.register_id
 JOIN finance_coveragesource c ON c.id=t.contract_id JOIN finance_billingcoverage b ON b.id=t.coverage_id WHERE f.id=fid;
$$;
CREATE FUNCTION psl_fixed_service(fid bigint) RETURNS text LANGUAGE sql STABLE AS $$
 SELECT encode(sha256(convert_to(psl_fixed_json(jsonb_build_object(
 'implementation','fixed-service-obligation/v1','case',t.case_id::text,
 'register',jsonb_build_object('system',r.payload->>'system','external_id',r.payload->>'external_id'),
 'contract',jsonb_build_object('system',c.payload->>'system','external_id',c.payload->>'external_id'),
 'customer',b.customer,'service',b.service,'contract_reference',b.contract)),'UTF8')),'hex')
 FROM finance_coveragefixedcharge f JOIN finance_coverageassessment a ON a.id=f.assessment_id
 JOIN finance_coverageterms t ON t.id=a.terms_id JOIN finance_coveragesource r ON r.id=t.register_id
 JOIN finance_coveragesource c ON c.id=t.contract_id JOIN finance_billingcoverage b ON b.id=t.coverage_id WHERE f.id=fid;
$$;
CREATE FUNCTION psl_fixed_overlap(fid bigint, own_key text DEFAULT NULL) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_coveragefixedcharge f JOIN finance_invoice i ON i.payload->'contract_period'->>'start'<=f.payload->'period'->>'end'
  AND i.payload->'contract_period'->>'end'>=f.payload->'period'->>'start'
 JOIN finance_billingpreparation p ON p.id=i.preparation_id
 WHERE f.id=fid AND p.kind='fixed_contract' AND p.snapshot->>'native_service'=psl_fixed_service(f.id)
 AND (own_key IS NULL OR i.obligation_key<>own_key)
 AND (EXISTS(SELECT 1 FROM finance_invoiceissue WHERE invoice_id=i.id)
  OR EXISTS(SELECT 1 FROM finance_invoicejob WHERE invoice_id=i.id AND kind='issue' AND status IN ('unknown','leased','held'))));
$$;
CREATE FUNCTION psl_fixed_reference(cid uuid, uid bigint, ref text, permission text) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_coverageaccess a WHERE a.case_id=cid AND a.principal_id=uid AND a.reference=ref
 AND a.id=(SELECT max(id) FROM finance_coverageaccess WHERE case_id=cid AND principal_id=uid AND reference=ref)
 AND a.permissions ? permission
 AND psl_schedules_grants(cid,uid,ARRAY['case.read',CASE permission WHEN 'verify' THEN 'coverage.invoice.verify' WHEN 'investigate' THEN 'agent.coverage' ELSE 'coverage.'||permission END])
 AND psl_schedules_grants(cid,a.actor_id,ARRAY['case.read','coverage.access'])
 AND EXISTS(SELECT 1 FROM auth_user WHERE id=uid AND is_active));
$$;
CREATE FUNCTION psl_fixed_terms(tid bigint, uid bigint, permission text) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_coverageterms t JOIN finance_coveragesource r ON r.id=t.register_id
 JOIN finance_coveragesource c ON c.id=t.contract_id JOIN finance_billingcoverage b ON b.id=t.coverage_id
 WHERE t.id=tid AND r.case_id=t.case_id AND c.case_id=t.case_id AND b.case_id=t.case_id
 AND r.kind='register' AND c.kind='contract' AND r.payload->>'status'='current' AND c.payload->>'status'='current'
 AND NOT EXISTS(SELECT 1 FROM finance_coveragesource n WHERE n.case_id=t.case_id AND ((n.reference=r.reference AND n.version>r.version) OR (n.reference=c.reference AND n.version>c.version)))
 AND NOT EXISTS(SELECT 1 FROM finance_coverageterms n WHERE n.coverage_id=b.id AND n.version>t.version AND EXISTS(SELECT 1 FROM finance_coveragetermsevent WHERE terms_id=n.id AND state='active'))
 AND NOT EXISTS(SELECT 1 FROM finance_billingcoverage n WHERE n.case_id=b.case_id AND n.reference=b.reference AND n.version>b.version)
 AND (SELECT state FROM finance_coveragetermsevent WHERE terms_id=t.id ORDER BY id DESC LIMIT 1)='active'
 AND psl_fixed_reference(t.case_id,uid,r.reference,permission) AND psl_fixed_reference(t.case_id,uid,c.reference,permission)
 AND psl_fixed_reference(t.case_id,r.actor_id,r.reference,'capture') AND psl_fixed_reference(t.case_id,c.actor_id,c.reference,'capture')
 AND psl_fixed_reference(t.case_id,t.actor_id,r.reference,'configure') AND psl_fixed_reference(t.case_id,t.actor_id,c.reference,'configure')
 AND psl_schedules_grants(t.case_id,t.actor_id,ARRAY['case.read','coverage.configure'])
 AND EXISTS(SELECT 1 FROM finance_coveragetermsevent e WHERE e.id=(SELECT max(id) FROM finance_coveragetermsevent WHERE terms_id=t.id)
  AND psl_schedules_grants(t.case_id,e.actor_id,ARRAY['case.read','coverage.activate'])
  AND psl_fixed_reference(t.case_id,e.actor_id,r.reference,'activate') AND psl_fixed_reference(t.case_id,e.actor_id,c.reference,'activate')
  AND (t.payload->>'review_requirement'='none' OR (t.payload->>'review_requirement'='required' AND t.payload->>'reviewer_id'=e.actor_id::text)))
 );
$$;
CREATE FUNCTION psl_fixed_charge_current(fid bigint, uid bigint, permission text) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_coveragefixedcharge f
 JOIN finance_coverageassessment a ON a.id=f.assessment_id JOIN finance_coverageterms t ON t.id=a.terms_id
 JOIN finance_coveragepreparationrequest r ON r.id=f.request_id
 WHERE f.id=fid AND psl_fixed_terms(t.id,uid,permission) AND psl_fixed_terms(t.id,f.actor_id,'configure')
 AND psl_schedules_grants(t.case_id,f.actor_id,ARRAY['case.read','coverage.configure'])
 AND NOT EXISTS(SELECT 1 FROM finance_coveragefixedcharge n WHERE n.request_id=r.id AND n.version>f.version)
 AND (f.assessment_id=COALESCE((SELECT assessment_id FROM finance_coveragepreparationroute WHERE request_id=r.id ORDER BY id DESC LIMIT 1),r.assessment_id)
 OR EXISTS(SELECT 1 FROM finance_coveragepreparationreceipt WHERE request_id=r.id))
 AND COALESCE((SELECT state FROM finance_coveragepreparationroute WHERE request_id=r.id ORDER BY id DESC LIMIT 1),'ready')='ready'
 AND EXISTS(SELECT 1 FROM jsonb_array_elements(a.result->'obligations') o WHERE o->>'key'=r.obligation_key AND o->>'status'='missing_invoice'
 AND f.payload->'period'=jsonb_build_object('start',o->>'start','end',o->>'end','bill_on',o->>'bill_on')));
$$;
CREATE FUNCTION psl_fixed_charge_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE t finance_coverageterms; r finance_coveragepreparationrequest; a finance_coverageassessment; e core_evidence;
BEGIN
 SELECT * INTO r FROM finance_coveragepreparationrequest WHERE id=NEW.request_id;
 SELECT * INTO a FROM finance_coverageassessment WHERE id=NEW.assessment_id;
 SELECT * INTO t FROM finance_coverageterms WHERE id=a.terms_id;
 SELECT * INTO e FROM core_evidence WHERE id=NEW.evidence_id;
 PERFORM id FROM core_case WHERE id=t.case_id FOR UPDATE;
 IF NOT psl_fixed_terms(t.id,NEW.actor_id,'configure') OR NOT psl_schedules_grants(t.case_id,NEW.actor_id,ARRAY['case.read','coverage.configure'])
 OR (NEW.assessment_id IS DISTINCT FROM COALESCE((SELECT assessment_id FROM finance_coveragepreparationroute WHERE request_id=r.id ORDER BY id DESC LIMIT 1),r.assessment_id)
 AND NOT EXISTS(SELECT 1 FROM finance_coveragepreparationreceipt WHERE request_id=r.id))
 OR COALESCE((SELECT state FROM finance_coveragepreparationroute WHERE request_id=r.id ORDER BY id DESC LIMIT 1),'ready')<>'ready'
 OR NEW.version<>COALESCE((SELECT max(version) FROM finance_coveragefixedcharge WHERE request_id=r.id),0)+1
 OR e.case_id IS DISTINCT FROM t.case_id OR e.kind IS DISTINCT FROM 'coverage_fixed_charge'
 OR e.body::jsonb IS DISTINCT FROM jsonb_build_object('request_id',r.id,'assessment_id',a.id,'charge',NEW.payload)
 OR NOT EXISTS(SELECT 1 FROM finance_coverageevidencescope s JOIN finance_coveragesource sr ON sr.id=t.register_id JOIN finance_coveragesource sc ON sc.id=t.contract_id
  WHERE s.evidence_id=e.id AND s.case_id=t.case_id AND s.purposes ? 'configure' AND s.references ? sr.reference AND s.references ? sc.reference)
 OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(a.result->'obligations') o WHERE o->>'key'=r.obligation_key AND o->>'status'='missing_invoice'
  AND NEW.payload->'period'=jsonb_build_object('start',o->>'start','end',o->>'end','bill_on',o->>'bill_on'))
 OR NOT EXISTS(SELECT 1 FROM finance_coverageterms original JOIN finance_coverageassessment oa ON oa.terms_id=original.id
  JOIN finance_coveragesource old_register ON old_register.id=original.register_id JOIN finance_coveragesource old_contract ON old_contract.id=original.contract_id
  JOIN finance_coveragesource current_register ON current_register.id=t.register_id JOIN finance_coveragesource current_contract ON current_contract.id=t.contract_id
  WHERE oa.id=r.assessment_id AND original.case_id=t.case_id AND original.payload->>'implementation'=t.payload->>'implementation'
   AND old_register.payload=current_register.payload AND old_contract.payload=current_contract.payload)
 OR NEW.payload->>'implementation' IS DISTINCT FROM 'exact-fixed-charge/v1'
 OR NEW.payload->>'currency' IS DISTINCT FROM (SELECT currency FROM finance_billingcoverage WHERE id=t.coverage_id)
 THEN RAISE EXCEPTION 'Exact current source-backed fixed charge and private authority required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_fixed_charge BEFORE INSERT ON finance_coveragefixedcharge FOR EACH ROW EXECUTE FUNCTION psl_fixed_charge_guard();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_coveragefixedcharge FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE FUNCTION psl_fixed_result_valid(fid bigint, result jsonb, snapshot jsonb) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE f finance_coveragefixedcharge; t finance_coverageterms; p jsonb; m jsonb; quantum numeric; net numeric; tax numeric; total numeric; pid bigint;
BEGIN
 SELECT * INTO f FROM finance_coveragefixedcharge WHERE id=fid;
 SELECT t0.* INTO t FROM finance_coverageterms t0 JOIN finance_coverageassessment a ON a.terms_id=t0.id WHERE a.id=f.assessment_id;
 p:=f.payload;
 IF result->'invoice_issued' IS DISTINCT FROM 'false'::jsonb OR result->'ledger_posted' IS DISTINCT FROM 'false'::jsonb OR result->'cash_received' IS DISTINCT FROM 'false'::jsonb OR result->'release_authorized' IS DISTINCT FROM 'false'::jsonb THEN RETURN false; END IF;
 IF result->>'status'='held' THEN RETURN result->'total'='null'::jsonb AND jsonb_array_length(result->'findings')>0; END IF;
 IF result->>'status' IS DISTINCT FROM 'prepared' OR result->'findings' IS DISTINCT FROM '[]'::jsonb
 OR jsonb_array_length(result->'lines')<>1 OR p->>'amount' IS NULL OR p->>'due_date' IS NULL OR p->>'decimal_places' IS NULL OR p->>'rule_reference' IS NULL OR p->>'tax_treatment_reference' IS NULL
 OR result->>'due_date' IS DISTINCT FROM p->>'due_date' OR result->>'currency' IS DISTINCT FROM p->>'currency'
 OR result->>'amount_basis' IS DISTINCT FROM 'gross_including_tax' OR p->>'amount_basis' IS DISTINCT FROM (SELECT amount_basis FROM finance_billingcoverage WHERE id=t.coverage_id)
 OR result->'lines'->0->>'kind' IS DISTINCT FROM 'fixed_contract'
 OR result->'lines'->0->'period' IS DISTINCT FROM p->'period'
 OR result->'lines'->0->>'source_amount' IS DISTINCT FROM p->>'amount'
 OR result->'lines'->0->>'source_basis' IS DISTINCT FROM p->>'amount_basis'
 OR result->'lines'->0->>'rule' IS DISTINCT FROM p->>'rule_reference'
 OR result->'lines'->0->>'tax_treatment' IS DISTINCT FROM p->>'tax_treatment_reference' THEN RETURN false; END IF;
 IF (p->>'amount')::numeric<0 OR (p->>'amount')::numeric>=1e24 OR (p->>'decimal_places')::int NOT BETWEEN 0 AND 8 THEN RETURN false; END IF;
 quantum:=power(10::numeric,(p->>'decimal_places')::int);
 IF p->>'method'='supplied_gross_total' AND p->>'amount_basis'='gross_including_tax' AND p->'tax_configuration_id'='null'::jsonb THEN
  total:=(p->>'amount')::numeric;
  IF trunc(total*quantum)<>total*quantum OR result->'lines'->0->'net'<>'null'::jsonb OR result->'lines'->0->'tax'<>'null'::jsonb OR result->'lines'->0->'raw_net'<>'null'::jsonb THEN RETURN false; END IF;
 ELSIF p->>'method'='configured_net_tax_v1' AND p->>'amount_basis'='net_exclusive' THEN
  pid:=(p->>'tax_configuration_id')::bigint;
  IF NOT psl_schedules_policy_current(t.case_id,pid) OR NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id=pid AND component='D08.tax_tier_rounding_rules')
   OR snapshot->'policies'->'D08.tax_tier_rounding_rules'->>'id' IS DISTINCT FROM pid::text THEN RETURN false; END IF;
  m:=psl_schedules_values(pid)->0;
  IF m->>'implementation'<>'net_exclusive_line_tax_v1' OR m->>'decimal_places'<>p->>'decimal_places' THEN RETURN false; END IF;
  net:=psl_fixed_round((p->>'amount')::numeric, (m->>'decimal_places')::int,m->>'rounding');
  tax:=psl_fixed_round(net*(m->>'tax_rate')::numeric,(m->>'decimal_places')::int,m->>'rounding');total:=net+tax;
  IF (result->'lines'->0->>'raw_net')::numeric IS DISTINCT FROM (p->>'amount')::numeric OR (result->'lines'->0->>'net')::numeric IS DISTINCT FROM net OR (result->'lines'->0->>'tax')::numeric IS DISTINCT FROM tax THEN RETURN false; END IF;
 ELSE RETURN false; END IF;
 RETURN (result->>'total')::numeric IS NOT DISTINCT FROM total AND (result->'lines'->0->>'total')::numeric IS NOT DISTINCT FROM total
 AND result->'invoice_issued'='false'::jsonb AND result->'ledger_posted'='false'::jsonb AND result->'cash_received'='false'::jsonb;
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;
CREATE FUNCTION psl_fixed_round(n numeric, places int, mode text) RETURNS numeric LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE scaled numeric; whole numeric; fraction numeric;
BEGIN
 scaled:=n*power(10::numeric,places);whole:=trunc(scaled);fraction:=scaled-whole;
 IF mode='half_up' THEN RETURN round(n,places);
 ELSIF mode='down' THEN RETURN whole/power(10::numeric,places);
 ELSIF mode='half_even' THEN
  RETURN (whole+CASE WHEN fraction>0.5 OR (fraction=0.5 AND mod(whole,2)=1) THEN 1 ELSE 0 END)/power(10::numeric,places);
 END IF;
 RAISE EXCEPTION 'Unsupported fixed charge rounding';
END $$;
CREATE FUNCTION psl_fixed_preparation_current(pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_billingpreparation p JOIN finance_coveragefixedcharge f ON f.id=p.fixed_charge_id
 JOIN finance_coverageassessment a ON a.id=f.assessment_id JOIN finance_coverageterms t ON t.id=a.terms_id
 JOIN finance_coveragepreparationrequest r ON r.id=f.request_id
 WHERE p.id=pid AND p.kind='fixed_contract' AND p.case_id=t.case_id AND p.coverage_id=t.coverage_id AND p.usage_id IS NULL AND p.handoff_id IS NULL
 AND p.actor_id=COALESCE((SELECT recipient_id FROM finance_coveragepreparationroute WHERE request_id=r.id ORDER BY id DESC LIMIT 1),r.recipient_id)
 AND psl_fixed_charge_current(f.id,p.actor_id,'receive')
 AND psl_schedules_grants(p.case_id,p.actor_id,ARRAY['case.read','finance.read','finance.billing.prepare','coverage.receive'])
 AND p.snapshot->>'charge'=f.id::text AND p.snapshot->>'charge_hash'=f.sha256 AND p.snapshot->>'request'=r.id::text
 AND p.snapshot->'period'=f.payload->'period' AND p.snapshot->>'obligation'=r.obligation_key
 AND p.snapshot->>'native_obligation'=psl_fixed_obligation(f.id) AND p.snapshot->>'native_service'=psl_fixed_service(f.id)
 AND NOT psl_fixed_overlap(f.id,p.snapshot->>'native_obligation')
 AND psl_fixed_result_valid(f.id,p.result,p.snapshot));
$$;
CREATE FUNCTION psl_fixed_preparation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE f finance_coveragefixedcharge; t finance_coverageterms; r finance_coveragepreparationrequest;
BEGIN
 IF NEW.kind<>'fixed_contract' AND NEW.fixed_charge_id IS NULL THEN RETURN NEW; END IF;
 SELECT * INTO f FROM finance_coveragefixedcharge WHERE id=NEW.fixed_charge_id;
 SELECT t0.* INTO t FROM finance_coverageterms t0 JOIN finance_coverageassessment a ON a.terms_id=t0.id WHERE a.id=f.assessment_id;
 SELECT * INTO r FROM finance_coveragepreparationrequest WHERE id=f.request_id;
 IF NEW.kind IS DISTINCT FROM 'fixed_contract' OR NEW.usage_id IS NOT NULL OR NEW.handoff_id IS NOT NULL OR NEW.case_id IS DISTINCT FROM t.case_id OR NEW.coverage_id IS DISTINCT FROM t.coverage_id
 OR NEW.actor_id IS DISTINCT FROM COALESCE((SELECT recipient_id FROM finance_coveragepreparationroute WHERE request_id=r.id ORDER BY id DESC LIMIT 1),r.recipient_id)
 OR NOT psl_fixed_charge_current(f.id,NEW.actor_id,'receive') OR NOT psl_schedules_grants(t.case_id,NEW.actor_id,ARRAY['case.read','finance.read','finance.billing.prepare','coverage.receive'])
 OR NEW.snapshot->>'charge' IS DISTINCT FROM f.id::text OR NEW.snapshot->>'charge_hash' IS DISTINCT FROM f.sha256
 OR NEW.snapshot->>'request' IS DISTINCT FROM r.id::text OR NEW.snapshot->>'obligation' IS DISTINCT FROM r.obligation_key
 OR NEW.snapshot->>'native_obligation' IS DISTINCT FROM psl_fixed_obligation(f.id)
 OR NEW.snapshot->>'native_service' IS DISTINCT FROM psl_fixed_service(f.id) OR psl_fixed_overlap(f.id)
 OR NEW.snapshot->'period' IS DISTINCT FROM f.payload->'period' OR NOT psl_fixed_result_valid(f.id,NEW.result,NEW.snapshot)
 THEN RAISE EXCEPTION 'Exact source-backed native fixed preparation required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_fixed_preparation BEFORE INSERT ON finance_billingpreparation FOR EACH ROW EXECUTE FUNCTION psl_fixed_preparation_guard();
CREATE FUNCTION psl_fixed_binding_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p finance_billingpreparation; f finance_coveragefixedcharge; r finance_coveragepreparationreceipt;
BEGIN
 SELECT * INTO p FROM finance_billingpreparation WHERE id=NEW.preparation_id;
 SELECT * INTO f FROM finance_coveragefixedcharge WHERE id=p.fixed_charge_id;
 SELECT * INTO r FROM finance_coveragepreparationreceipt WHERE id=NEW.receipt_id;
 IF p.kind IS DISTINCT FROM 'fixed_contract' OR r.request_id IS DISTINCT FROM f.request_id OR NEW.actor_id IS DISTINCT FROM r.actor_id OR NEW.actor_id IS DISTINCT FROM p.actor_id
 OR NOT psl_fixed_preparation_current(p.id) OR NEW.payload IS DISTINCT FROM jsonb_build_object('receipt',r.id,'request',f.request_id,'charge',f.id,'preparation',p.id,'operation_key',p.operation_key,'period',f.payload->'period','invoice_issued',false)
 THEN RAISE EXCEPTION 'Exact immutable acknowledgement to preparation binding required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_fixed_binding BEFORE INSERT ON finance_coveragenativepreparation FOR EACH ROW EXECUTE FUNCTION psl_fixed_binding_guard();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_coveragenativepreparation FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE FUNCTION psl_fixed_invoice_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p finance_billingpreparation; i finance_invoice; j finance_invoicejob; rv finance_invoicereview;
BEGIN
 IF TG_TABLE_NAME='finance_invoice' THEN
  SELECT * INTO p FROM finance_billingpreparation WHERE id=NEW.preparation_id;
  IF p.kind<>'fixed_contract' THEN RETURN NEW; END IF;
  PERFORM id FROM core_case WHERE id=p.case_id FOR UPDATE;
  IF psl_fixed_overlap(p.fixed_charge_id) OR NOT psl_fixed_preparation_current(p.id) OR p.result->>'status'<>'prepared' OR NEW.case_id<>p.case_id
   OR NEW.payload->'contract_period' IS DISTINCT FROM p.snapshot->'period' OR NEW.payload->>'coverage_obligation' IS DISTINCT FROM p.snapshot->>'obligation'
   OR NEW.payload->>'fixed_charge' IS DISTINCT FROM p.fixed_charge_id::text OR NEW.obligation_key IS DISTINCT FROM p.snapshot->>'native_obligation'
   OR (NEW.payload->>'amount')::numeric IS DISTINCT FROM NEW.amount
   OR NEW.payload->>'customer' IS DISTINCT FROM (SELECT customer FROM finance_billingcoverage WHERE id=p.coverage_id)
   OR NEW.payload->>'contract' IS DISTINCT FROM (SELECT contract FROM finance_billingcoverage WHERE id=p.coverage_id)
   OR NEW.payload->>'source_basis' IS DISTINCT FROM (SELECT amount_basis FROM finance_billingcoverage WHERE id=p.coverage_id)
   OR NEW.payload->>'coverage_completeness' IS DISTINCT FROM (SELECT completeness FROM finance_billingcoverage WHERE id=p.coverage_id)
   OR NEW.payload->'usage_completeness' IS DISTINCT FROM 'null'::jsonb
   OR NEW.payload->>'currency' IS DISTINCT FROM NEW.currency OR NEW.payload->>'amount_basis' IS DISTINCT FROM NEW.amount_basis
   OR NEW.payload->>'due_date' IS DISTINCT FROM NEW.due_date::text
   OR NEW.payload->>'preparation' IS DISTINCT FROM p.id::text OR NEW.payload->>'preparation_key' IS DISTINCT FROM p.operation_key
   OR NEW.payload->>'reference' IS DISTINCT FROM NEW.reference OR NEW.payload->>'version' IS DISTINCT FROM NEW.version::text
   OR NEW.amount IS DISTINCT FROM (p.result->>'total')::numeric OR NEW.currency IS DISTINCT FROM p.result->>'currency' OR NEW.amount_basis<>'gross_including_tax'
   OR NEW.due_date IS DISTINCT FROM (p.result->>'due_date')::date OR NEW.payload->'lines' IS DISTINCT FROM p.result->'lines'
   OR NOT EXISTS(SELECT 1 FROM finance_coveragenativepreparation WHERE preparation_id=p.id)
   OR EXISTS(SELECT 1 FROM finance_invoiceissue WHERE obligation_key=NEW.obligation_key)
  THEN RAISE EXCEPTION 'Exact native fixed-contract invoice lineage required'; END IF;
 ELSE
  SELECT * INTO i FROM finance_invoice WHERE id=NEW.invoice_id;SELECT * INTO p FROM finance_billingpreparation WHERE id=i.preparation_id;
  IF p.kind<>'fixed_contract' THEN RETURN NEW; END IF;
  PERFORM id FROM core_case WHERE id=p.case_id FOR UPDATE;
  IF psl_fixed_overlap(p.fixed_charge_id,i.obligation_key) THEN RAISE EXCEPTION 'Overlapping exact-source invoice effect requires reconciliation'; END IF;
  IF TG_TABLE_NAME='finance_invoicereview' THEN
   IF NOT psl_fixed_preparation_current(p.id) OR NOT psl_schedules_grants(i.case_id,NEW.actor_id,ARRAY['case.read','finance.invoice.review'])
    OR NOT psl_fixed_charge_current(p.fixed_charge_id,NEW.actor_id,'read') OR NEW.publication_packet->>'payload_hash' IS DISTINCT FROM i.sha256
    OR NEW.publication_packet->'sources' IS DISTINCT FROM p.snapshot
    OR NOT psl_schedules_role_current(i.case_id,NEW.actor_id,NEW.authority,NEW.role)
   THEN RAISE EXCEPTION 'Current exact fixed-contract review required'; END IF;
  ELSIF TG_TABLE_NAME='finance_invoicejob' THEN
   IF NEW.kind<>'issue' THEN RETURN NEW; END IF;
   SELECT * INTO rv FROM finance_invoicereview WHERE id=(NEW.intent->>'review')::bigint;
   IF NOT psl_fixed_preparation_current(p.id) OR NOT psl_schedules_grants(i.case_id,NEW.actor_id,ARRAY['case.read','finance.invoice.issue'])
    OR rv.invoice_id IS DISTINCT FROM i.id OR rv.verdict IS DISTINCT FROM 'approve'
    OR NOT psl_schedules_grants(i.case_id,rv.actor_id,ARRAY['case.read','finance.invoice.review'])
    OR NOT psl_fixed_charge_current(p.fixed_charge_id,rv.actor_id,'read')
    OR NOT psl_schedules_authority_current(i.case_id,rv.authority)
    OR NEW.intent->>'sha256' IS DISTINCT FROM i.sha256 OR rv.publication_packet->>'payload_hash' IS DISTINCT FROM i.sha256
    OR EXISTS(SELECT 1 FROM finance_invoiceissue WHERE obligation_key=i.obligation_key)
   THEN RAISE EXCEPTION 'Current reviewed fixed-contract issue reservation required'; END IF;
  ELSIF TG_TABLE_NAME='finance_invoiceissue' THEN
   -- Exact prior reserved effects are recovered without reauthorising them.
   SELECT * INTO j FROM finance_invoicejob WHERE id=NEW.job_id;
   SELECT * INTO rv FROM finance_invoicereview WHERE id=(j.intent->>'review')::bigint;
   IF j.invoice_id IS DISTINCT FROM i.id OR j.kind IS DISTINCT FROM 'issue' OR rv.invoice_id IS DISTINCT FROM i.id OR rv.verdict IS DISTINCT FROM 'approve'
    OR NEW.obligation_key IS DISTINCT FROM i.obligation_key OR NEW.payload IS DISTINCT FROM i.payload OR NEW.sha256 IS DISTINCT FROM i.sha256
    OR j.intent->>'sha256' IS DISTINCT FROM i.sha256 OR rv.publication_packet->>'payload_hash' IS DISTINCT FROM i.sha256
   THEN RAISE EXCEPTION 'Exact reserved fixed-contract issued receipt required'; END IF;
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_fixed_invoice BEFORE INSERT ON finance_invoice FOR EACH ROW EXECUTE FUNCTION psl_fixed_invoice_guard();
CREATE TRIGGER psl_fixed_invoice BEFORE INSERT ON finance_invoicereview FOR EACH ROW EXECUTE FUNCTION psl_fixed_invoice_guard();
CREATE TRIGGER psl_fixed_invoice BEFORE INSERT ON finance_invoicejob FOR EACH ROW EXECUTE FUNCTION psl_fixed_invoice_guard();
CREATE TRIGGER psl_fixed_invoice BEFORE INSERT ON finance_invoiceissue FOR EACH ROW EXECUTE FUNCTION psl_fixed_invoice_guard();
"""
REVERSE_SQL = r"""
DROP TRIGGER psl_fixed_invoice ON finance_invoiceissue;
DROP TRIGGER psl_fixed_invoice ON finance_invoicejob;
DROP TRIGGER psl_fixed_invoice ON finance_invoicereview;
DROP TRIGGER psl_fixed_invoice ON finance_invoice;
DROP TRIGGER psl_immutable ON finance_coveragenativepreparation;
DROP TRIGGER psl_fixed_binding ON finance_coveragenativepreparation;
DROP TRIGGER psl_fixed_preparation ON finance_billingpreparation;
DROP TRIGGER psl_immutable ON finance_coveragefixedcharge;
DROP TRIGGER psl_fixed_charge ON finance_coveragefixedcharge;
DROP FUNCTION psl_fixed_invoice_guard();
DROP FUNCTION psl_fixed_binding_guard();
DROP FUNCTION psl_fixed_preparation_guard();
DROP FUNCTION psl_fixed_preparation_current(bigint);
DROP FUNCTION psl_fixed_round(numeric, int, text);
DROP FUNCTION psl_fixed_result_valid(bigint, jsonb, jsonb);
DROP FUNCTION psl_fixed_charge_guard();
DROP FUNCTION psl_fixed_charge_current(bigint, bigint, text);
DROP FUNCTION psl_fixed_terms(bigint, bigint, text);
DROP FUNCTION psl_fixed_reference(uuid, bigint, text, text);
DROP FUNCTION psl_fixed_overlap(bigint, text);
DROP FUNCTION psl_fixed_service(bigint);
DROP FUNCTION psl_fixed_obligation(bigint);
DROP FUNCTION psl_fixed_json(jsonb);
"""

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_append_only_history'),
        ('finance', '0066_allocation_coverage'),
        ('workflows', '0071_factory_group_forecast'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CoverageFixedCharge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField()),
                ('payload', models.JSONField()),
                ('sha256', models.CharField(max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('assessment', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='finance.coverageassessment')),
                ('evidence', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.evidence')),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='finance.coveragepreparationrequest')),
            ],
        ),
        migrations.AddField(
            model_name='billingpreparation',
            name='fixed_charge',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='finance.coveragefixedcharge'),
        ),
        migrations.CreateModel(
            name='CoverageNativePreparation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payload', models.JSONField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('preparation', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='finance.billingpreparation')),
                ('receipt', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='finance.coveragepreparationreceipt')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddConstraint(
            model_name='coveragefixedcharge',
            constraint=models.UniqueConstraint(fields=('request', 'version'), name='coverage_fixed_charge_version'),
        ),
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]
