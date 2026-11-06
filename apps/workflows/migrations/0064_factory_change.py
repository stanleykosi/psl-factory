"""Independent controlled-change envelope on the restored statement checkpoint."""
from importlib import import_module
from django.db import migrations
PREVIOUS=import_module('apps.workflows.migrations.0063_statement_verification').SQL
SQL=PREVIOUS
marker="'delivery-go-live/v1','finance-accounts/v1','rfp-response/v1'"
assert SQL.count(marker)==1
SQL=SQL.replace(marker,marker+",'pmo-change/v1'")
marker="WHEN 'delivery-go-live/v1' THEN 'OPS.factory_go_live_execution'"
assert SQL.count(marker)==1
SQL=SQL.replace(marker,marker+" WHEN 'pmo-change/v1' THEN 'OPS.factory_change_execution'")
SOURCE=r"""
 IF NEW.definition='pmo-change/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_changeversion v ON v.id=(e.body::jsonb->>'change_version_id')::bigint
   JOIN pmo_changerequest c ON c.id=v.change_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_change_intake'
    AND c.case_id=NEW.case_id AND c.id=(NEW.request->>'change')::bigint
    AND e.body::jsonb->>'protocol'='factory-change-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','change_version_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object'
    AND a.action IN ('factory.change_intake','factory.change_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-project native change intake provenance required'; END IF;
 END IF;
"""
marker=" IF NEW.status='verified' THEN"
assert SQL.count(marker)==1
SQL=SQL.replace(marker,SOURCE+marker)
VERIFIED=r"""
 IF NEW.definition='pmo-change/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN pmo_changeauthorization ca ON ca.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint
  JOIN pmo_changeversion cv ON cv.id=ca.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
  JOIN pmo_changeclosure cc ON cc.authorization_id=ca.id
  JOIN documents_publicationreceipt r ON r.id=cc.receipt_id JOIN documents_publication p ON p.id=r.publication_id
  JOIN pmo_changedocumentbinding b ON b.version_id=p.version_id AND b.authorization_id=ca.id AND b.purpose='go_live'
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND cv.id=(e.body::jsonb->>'change_version_id')::bigint
   AND cr.case_id=NEW.case_id AND cr.current_id=cv.id AND cr.id=(NEW.request->>'change')::bigint
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id
   AND cc.execution_ids=b.execution_ids AND cc.pm_signature_id<>cc.client_signature_id
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'closure'=cc.id::text
   AND a.result->>'document_version'=p.version_id::text
   AND EXISTS(SELECT 1 FROM documents_publication np JOIN pmo_changedocumentbinding nb ON nb.version_id=np.version_id
    JOIN documents_publicationreceipt nr ON nr.publication_id=np.id
    WHERE np.factory_work_id=NEW.id AND np.factory_source_id=e.id AND nb.authorization_id=ca.id AND nb.purpose='notice')
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient
    WHERE NOT EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint)))
 THEN RAISE EXCEPTION 'Observed exact native change closure and controlled recipient receipts required'; END IF;
"""
assert SQL.count(' RETURN NEW;')==1
SQL=SQL.replace(' RETURN NEW;',VERIFIED+' RETURN NEW;')
class Migration(migrations.Migration):
    dependencies=[('workflows','0063_statement_verification')]
    operations=[migrations.RunSQL(SQL,PREVIOUS)]
