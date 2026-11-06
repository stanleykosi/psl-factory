"""Tenth closed production line; native Finance output and every recipient receipt required."""
from importlib import import_module
from django.db import migrations

SQL=import_module('apps.workflows.migrations.0047_factory_go_live').SQL
OLD="'pmo-finance/v1','planning/v1','commercial/v1','delivery-release/v1','delivery-hypercare/v1','delivery-archive/v1','delivery-handover/v1','delivery-closure/v1','delivery-go-live/v1'"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,OLD+",'finance-accounts/v1'")
OLD="WHEN 'delivery-go-live/v1' THEN 'OPS.factory_go_live_execution'"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,OLD+" WHEN 'finance-accounts/v1' THEN 'OPS.factory_accounting_execution'")
SOURCE=r"""
 IF NEW.definition='finance-accounts/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN finance_financesource s ON s.id=(e.body::jsonb->>'source')::bigint
   JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_accounting_intake'
    AND e.body::jsonb->>'schema'='factory-accounting-intake/v1' AND s.case_id=NEW.case_id
    AND s.batch_id=(NEW.request->>'batch')::bigint AND s.entity=NEW.request->>'entity'
    AND e.body::jsonb->'batch'=NEW.request->'batch' AND e.body::jsonb->'entity'=NEW.request->'entity'
    AND e.body::jsonb->'reference'=NEW.request->'reference'
    AND a.action='factory.accounting_inputs_recorded'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native exact accounting intake/source references required'; END IF;
 END IF;
"""
MARKER=" IF NEW.status='verified' THEN"
assert SQL.count(MARKER)==1
SQL=SQL.replace(MARKER,SOURCE+MARKER)
VERIFIED=r"""
 IF NEW.definition='finance-accounts/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM finance_financerun r JOIN finance_financesource s ON s.id=r.source_id
  JOIN finance_financedocumentbinding b ON b.run_id=r.id
  JOIN documents_version v ON v.id=b.version_id JOIN documents_document d ON d.id=v.document_id
  JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
  JOIN core_evidence h ON h.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE r.case_id=NEW.case_id AND s.case_id=NEW.case_id AND d.case_id=NEW.case_id AND r.kind='formula'
   AND s.id=(h.body::jsonb->>'source')::bigint AND s.batch_id=(NEW.request->>'batch')::bigint
   AND (p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id OR p.factory_work_id IS NULL)
   AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint))
   AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
   AND EXISTS(SELECT 1 FROM finance_financereview fr WHERE fr.run_id=r.id AND fr.purpose='output' AND fr.verdict='approve'
    AND fr.id=(SELECT max(last.id) FROM finance_financereview last WHERE last.run_id=r.id AND last.purpose='output'))
   AND a.result->'verified'='true'::jsonb AND a.result->>'run'=r.id::text AND a.result->>'source'=s.id::text
   AND a.result->>'binding'=b.id::text AND a.result->>'publication'=p.id::text AND a.result->>'document_version'=v.id::text
   AND a.result->'receipt_ids'=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id))
 THEN RAISE EXCEPTION 'Current native accounting binding/output review and all exact recipient receipts required'; END IF;
"""
assert SQL.count(' RETURN NEW;')==1
SQL=SQL.replace(' RETURN NEW;',VERIFIED+' RETURN NEW;')
TASK=import_module('apps.workflows.migrations.0049_factory_governance_task').SQL
OLD="'factory_information','factory_review','factory_governance'"
assert TASK.count(OLD)==1
TASK=TASK.replace(OLD,OLD+",'factory_accounting_review'")

class Migration(migrations.Migration):
    dependencies=[('workflows','0049_factory_governance_task'),('finance','0062_exact_publication_review')]
    operations=[migrations.RunSQL(SQL),migrations.RunSQL(TASK)]
