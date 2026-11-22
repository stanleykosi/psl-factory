"""Verify evidenced external replies alongside native recipient acknowledgements."""
from importlib import import_module

from django.db import migrations


ORIGINAL = import_module('apps.workflows.migrations.0088_rfp_portal_verification').SQL
START = " IF NEW.definition='delivery-handover/v1' AND NEW.status='verified' AND NOT EXISTS("
END = " THEN RAISE EXCEPTION 'Observed exact native handover and actual recipient acknowledgement required'; END IF;"
start = ORIGINAL.index(START)
end = ORIGINAL.index(END, start) + len(END)

HELPERS = r"""
CREATE FUNCTION psl_handover_recorded_reply(entry pmo_deliveryrecord, receipt_key bigint)
RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE att jsonb := entry.data->'attestation';
BEGIN
 IF jsonb_typeof(att) IS DISTINCT FROM 'object'
  OR NOT att ?& ARRAY['configuration','role','authority','party','channel','responded_at','proof_sha256','predecessor']
  OR att-ARRAY['configuration','role','authority','party','channel','responded_at','proof_sha256','predecessor']<>'{}'::jsonb
  OR entry.data-ARRAY['receipt_id','recipient_id','status','note','attestation']<>'{}'::jsonb
  OR jsonb_typeof(att->'party') IS DISTINCT FROM 'string'
  OR length(btrim(att->>'party')) NOT BETWEEN 1 AND 200
  OR jsonb_typeof(entry.data->'note') IS DISTINCT FROM 'string'
  OR length(btrim(entry.data->>'note')) NOT BETWEEN 1 AND 4000
 THEN RETURN false; END IF;
 RETURN EXISTS(
  SELECT 1 FROM pmo_deliverydossier d JOIN core_case c ON c.id=d.case_id
  JOIN documents_publicationreceipt r ON r.id=receipt_key
  JOIN documents_publication p ON p.id=r.publication_id
  JOIN documents_version v ON v.id=p.version_id
  JOIN documents_document doc ON doc.id=v.document_id
  JOIN pmo_deliverydocumentbinding b ON b.version_id=v.id AND b.dossier_id=d.id AND b.purpose='handover'
  JOIN core_evidence proof ON proof.id=entry.evidence_id AND proof.case_id=d.case_id
  JOIN policy_configuration cfg ON cfg.id=(att->>'configuration')::bigint AND cfg.case_id=d.case_id
  WHERE d.id=entry.dossier_id AND entry.kind='handover'
   AND entry.data->>'status' IN ('received','gaps')
   AND entry.data->>'receipt_id'=r.id::text AND entry.data->>'recipient_id'=r.recipient_id::text
   AND p.recipient_ids @> to_jsonb(ARRAY[r.recipient_id])
   AND doc.case_id=d.case_id AND doc.current_id=v.id AND v.audience='internal'
   AND r.payload=v.payload AND r.payload_sha256=v.payload_sha256 AND entry.snapshot=b.snapshot
   AND (att->>'responded_at')::timestamptz>=r.created_at
   AND (att->>'responded_at')::timestamptz<=entry.created_at
   AND COALESCE(entry.parent_id,0)=(att->>'predecessor')::bigint
   AND COALESCE(entry.parent_id,0)=COALESCE((SELECT max(prior.id) FROM pmo_deliveryrecord prior
    WHERE prior.dossier_id=d.id AND prior.kind='handover' AND prior.data->>'receipt_id'=r.id::text AND prior.id<entry.id),0)
   AND cfg.component='OPS.handover_reply_capture' AND psl_schedules_policy_current(d.case_id,cfg.id)
   AND psl_schedules_values(cfg.id)->0->'recorder_roles' ? (att->>'role')
   AND psl_schedules_values(cfg.id)->0->'channels' ? (att->>'channel')
   AND att->'authority'=jsonb_build_object('D05.role_principal_assignments',
        (att->'authority'->>'D05.role_principal_assignments')::bigint)
   AND psl_schedules_role_current(d.case_id,entry.actor_id,att->'authority',att->>'role')
   AND psl_schedules_grants(d.case_id,entry.actor_id,ARRAY['case.read','delivery.read','delivery.record_support_reply'])
   AND psl_schedules_grants(d.case_id,proof.created_by_id,ARRAY['evidence.add'])
   AND att->>'proof_sha256'=proof.sha256
   AND proof.kind<>ALL(ARRAY['qbo_native_intent','qbo_native_observation','template_current_source','ledger_source',
    'quickbooks_verification','ledger_resolution','ledger_resolution_review','approval_source','approval_observation',
    'migration_proof','d03_source','planning_packet','planning_prd_alignment','planning_scope_alignment',
    'planning_contract_comparison','planning_readiness','planning_department_review','finance_group_snapshot'])
   AND proof.source<>'psl:p56-confirmed-request/v1'
   AND NOT EXISTS(SELECT 1 FROM unnest(ARRAY['d03_control_','p14_','ops_','integration_','agent_private_',
    'coverage_','usage_intake_','payment_reminder_','forecast_']) AS prefixes(prefix) WHERE starts_with(proof.kind,prefix))
   AND NOT (proof.kind='finance_report_snapshot' AND
    (starts_with(proof.source,'derived:forecast:') OR starts_with(proof.source,'derived:ppe-statement:')))
   AND NOT EXISTS(SELECT 1 FROM finance_financestatementppeprojection WHERE evidence_id=proof.id)
   AND NOT EXISTS(SELECT 1 FROM finance_forecastevidencereference WHERE evidence_id=proof.id)
   AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario WHERE evidence_id=proof.id)
   AND NOT EXISTS(SELECT 1 FROM finance_forecastitemsupport WHERE evidence_id=proof.id)
 );
EXCEPTION WHEN invalid_text_representation OR datetime_field_overflow OR invalid_datetime_format OR numeric_value_out_of_range
 THEN RETURN false;
END;
$$;
CREATE FUNCTION psl_handover_recorded_reply_insert() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.kind='handover' AND NEW.data ? 'attestation'
  AND NOT psl_handover_recorded_reply(NEW,(NEW.data->>'receipt_id')::bigint)
 THEN RAISE EXCEPTION 'Exact configured recorder, reply source and handover receipt required'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER psl_handover_recorded_reply BEFORE INSERT ON pmo_deliveryrecord
 FOR EACH ROW EXECUTE FUNCTION psl_handover_recorded_reply_insert();
"""

VERIFIED = r"""
 IF NEW.definition='delivery-handover/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p
  JOIN documents_publicationjob job ON job.publication_id=p.id AND job.status='confirmed'
  JOIN documents_version v ON v.id=p.version_id
  JOIN documents_document doc ON doc.id=v.document_id AND doc.case_id=NEW.case_id AND doc.current_id=v.id
  JOIN pmo_deliverydocumentbinding b ON b.version_id=v.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND b.purpose='handover'
   AND b.dossier_id=(NEW.request->>'dossier')::bigint
   AND a.result->'verified'='true'::jsonb AND a.result->>'publication'=p.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'head'=NEW.source_head_id::text
   AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) destination WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt r
    JOIN pmo_deliveryrecord h ON h.dossier_id=b.dossier_id AND h.kind='handover'
    WHERE r.publication_id=p.id AND r.recipient_id=destination::bigint
     AND r.payload=v.payload AND r.payload_sha256=v.payload_sha256
     AND h.data->>'receipt_id'=r.id::text AND h.data->>'status'='received' AND h.snapshot=b.snapshot
     AND h.id=(SELECT max(current_reply.id) FROM pmo_deliveryrecord current_reply
      WHERE current_reply.dossier_id=b.dossier_id AND current_reply.kind='handover' AND current_reply.data->>'receipt_id'=r.id::text)
     AND a.result->'receipt_ids' @> to_jsonb(ARRAY[r.id]) AND a.result->'handover_ids' @> to_jsonb(ARRAY[h.id])
     AND ((NOT h.data ? 'attestation' AND h.actor_id=r.recipient_id
       AND psl_schedules_grants(NEW.case_id,h.actor_id,ARRAY['delivery.support_receive','document.receive:internal']))
      OR (psl_handover_recorded_reply(h,r.id) AND EXISTS(SELECT 1 FROM core_audit origin
       WHERE origin.case_id=NEW.case_id AND origin.actor_id=h.actor_id AND origin.action='delivery.handover'
        AND origin.data=jsonb_build_object('record',h.id,'dossier',b.dossier_id))))))
 ) THEN RAISE EXCEPTION 'Observed exact native handover and actual recipient acknowledgement required'; END IF;
"""
SQL = ORIGINAL[:start] + VERIFIED + ORIGINAL[end:]


class Migration(migrations.Migration):
    dependencies = [('workflows', '0088_rfp_portal_verification'),
                    ('pmo', '0059_archivecopyfile_archivecopyjob_archivecopyattempt_and_more'),
                    ('finance', '0077_forecast_evidence_reference')]
    operations = [
        migrations.RunSQL(HELPERS, '''DROP TRIGGER psl_handover_recorded_reply ON pmo_deliveryrecord;
DROP FUNCTION psl_handover_recorded_reply_insert();
DROP FUNCTION psl_handover_recorded_reply(pmo_deliveryrecord,bigint);'''),
        migrations.RunSQL(SQL, ORIGINAL),
    ]
