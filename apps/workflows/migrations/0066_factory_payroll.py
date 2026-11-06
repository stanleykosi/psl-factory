"""Restricted payroll envelope composed from accepted Emergency697 schema."""
from importlib import import_module
from django.db import migrations
PREVIOUS=import_module('apps.workflows.migrations.0065_factory_emergency').SQL
SQL=PREVIOUS
marker="'rfp-response/v1','pmo-change/v1'"
assert SQL.count(marker)==1
SQL=SQL.replace(marker,marker+",'finance-payroll/v1'")
marker="WHEN 'pmo-change/v1' THEN 'OPS.factory_change_execution'"
assert SQL.count(marker)==1
SQL=SQL.replace(marker,marker+" WHEN 'finance-payroll/v1' THEN 'OPS.factory_payroll_execution'")
SOURCE="""
 IF NEW.definition='finance-payroll/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN finance_payrollrequest q ON q.id=(e.body::jsonb->>'request_id')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_payroll_intake'
    AND q.case_id=NEW.case_id AND q.reference=NEW.request->>'payroll_reference'
    AND e.body::jsonb->>'protocol'='factory-payroll-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','request_id','inputs']='{}'::jsonb
    AND (e.body::jsonb->'inputs')-ARRAY['input_ids','hr_snapshot_id']='{}'::jsonb
    AND jsonb_array_length(e.body::jsonb->'inputs'->'input_ids')=2
    AND (SELECT count(DISTINCT i.provider) FROM finance_payrollinput i
      WHERE i.id IN (SELECT value::bigint FROM jsonb_array_elements_text(e.body::jsonb->'inputs'->'input_ids'))
       AND i.request_id=q.id AND i.metadata->'accepted'='true'::jsonb)=2
    AND a.action IN ('factory.payroll_intake','factory.payroll_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-workspace restricted payroll provenance required'; END IF;
 END IF;
"""
marker=" IF NEW.status='verified' THEN"
assert SQL.count(marker)==1
SQL=SQL.replace(marker,SOURCE+marker)
VERIFIED="""
 IF NEW.definition='finance-payroll/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN finance_payrollrequest q ON q.id=(e.body::jsonb->>'request_id')::bigint
   JOIN finance_payrollrun ar ON ar.request_id=q.id AND ar.kind='aggregate'
   JOIN finance_payrollrun mr ON mr.id=ar.parent_id AND mr.kind='match'
   JOIN finance_payrollrun cr ON cr.id=mr.parent_id AND cr.kind='combine'
   JOIN finance_payrollpublication p ON p.run_id=ar.id AND p.request_id=q.id
   JOIN finance_payrollreview rv ON rv.id=p.review_id AND rv.run_id=ar.id
   JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
   JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
   JOIN policy_configuration pc ON pc.id=(p.policy_ids->>'F18.reporting_rules')::bigint
   JOIN policy_registeredreference pr ON pr.case_id=pc.case_id AND pr.ref=pc.envelope->'value'->>'artifact_ref'
    AND pr.version=(pc.envelope->'value'->>'artifact_version')::integer AND pr.sha256=pc.envelope->'value'->>'sha256'
  WHERE e.id=NEW.source_head_id AND q.case_id=NEW.case_id AND q.reference=NEW.request->>'payroll_reference'
   AND cr.request_id=q.id AND mr.request_id=q.id
   AND (cr.metadata->'input_ids') @> (e.body::jsonb->'inputs'->'input_ids')
   AND (cr.metadata->'input_ids') <@ (e.body::jsonb->'inputs'->'input_ids')
   AND mr.hr_snapshot_id=(e.body::jsonb->'inputs'->>'hr_snapshot_id')::bigint
   AND ar.metadata->>'status'='complete' AND mr.metadata->>'status'='complete' AND cr.metadata->>'status'='complete'
   AND rv.verdict='approve' AND rv.subject_sha256=ar.sha256
   AND rv.id=(SELECT max(id) FROM finance_payrollreview WHERE run_id=ar.id)
   AND p.payload->'by_bu'=ar.result->'by_bu' AND p.payload->'eligible_total'=ar.result->'eligible_total'
   AND p.payload->>'source_run'=ar.id::text AND p.payload->>'disclosure'='aggregate_only'
   AND NOT (p.payload ? 'rows') AND p.payload->'hr_written'='false'::jsonb AND p.payload->'ledger_posted'='false'::jsonb
   AND NOT EXISTS(SELECT 1 FROM finance_payrollpublication newer WHERE newer.request_id=q.id AND newer.version>p.version)
   AND NOT EXISTS(SELECT 1 FROM finance_payrollrequest newer WHERE newer.case_id=q.case_id AND newer.reference=q.reference AND newer.version>q.version)
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'publication'=p.id::text
   AND a.result->>'run'=ar.id::text AND a.result->>'request'=q.id::text
   AND jsonb_array_length(pr.content->'recipient_ids')>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(pr.content->'recipient_ids') recipient
     WHERE NOT EXISTS(SELECT 1 FROM finance_payrollreportreceipt rr WHERE rr.publication_id=p.id AND rr.actor_id=recipient::bigint
       AND a.result->'receipt_ids' @> to_jsonb(ARRAY[rr.id]))))
 THEN RAISE EXCEPTION 'Observed exact payroll aggregate and actual recipient-owned receipts required'; END IF;
"""
assert SQL.count(' RETURN NEW;')==1
SQL=SQL.replace(' RETURN NEW;',VERIFIED+' RETURN NEW;')

assert SQL.replace(SOURCE,'').replace(VERIFIED,'').replace(",'finance-payroll/v1'",'').replace(" WHEN 'finance-payroll/v1' THEN 'OPS.factory_payroll_execution'",'')==PREVIOUS

class Migration(migrations.Migration):
    dependencies=[('workflows','0065_factory_emergency')]
    operations=[migrations.RunSQL(SQL,PREVIOUS)]
