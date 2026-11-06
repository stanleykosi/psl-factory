"""Separate native Emergency evidence envelope on the accepted PMO change chain."""
from importlib import import_module
from django.db import migrations
PREVIOUS=import_module('apps.workflows.migrations.0064_factory_change').SQL
SQL=PREVIOUS
marker="'rfp-response/v1','pmo-change/v1'"
assert SQL.count(marker)==1
SQL=SQL.replace(marker,marker+",'pmo-emergency/v1'")
marker="WHEN 'pmo-change/v1' THEN 'OPS.factory_change_execution'"
assert SQL.count(marker)==1
SQL=SQL.replace(marker,marker+" WHEN 'pmo-emergency/v1' THEN 'OPS.factory_emergency_execution'")
SOURCE=r"""
 IF NEW.definition='pmo-emergency/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_emergencyprofile ep ON ep.id=(e.body::jsonb->>'profile_id')::bigint
   JOIN pmo_changeversion cv ON cv.id=ep.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_emergency_intake'
    AND cr.case_id=NEW.case_id AND cr.id=(NEW.request->>'change')::bigint AND cv.category='Emergency' AND cv.incident_id IS NOT NULL
    AND e.body::jsonb->>'protocol'='factory-emergency-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','profile_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object'
    AND a.action IN ('factory.emergency_intake','factory.emergency_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-project incident-linked native Emergency source required'; END IF;
 END IF;
"""
marker=" IF NEW.status='verified' THEN"
assert SQL.count(marker)==1
SQL=SQL.replace(marker,SOURCE+marker)
VERIFIED=r"""
 IF NEW.definition='pmo-emergency/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN pmo_emergencyprofile ep ON ep.id=(e.body::jsonb->>'profile_id')::bigint
  JOIN pmo_emergencyoutcome o ON o.id=(e.body::jsonb->'inputs'->>'outcome_id')::bigint AND o.profile_id=ep.id
  JOIN pmo_emergencyauthorization ea ON ea.id=o.authorization_id AND ea.profile_id=ep.id
  JOIN pmo_emergencyretrospectiverecord rr ON rr.outcome_id=o.id
  JOIN pmo_changeversion cv ON cv.id=ep.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
  JOIN pmo_emergencydocumentbinding b ON b.outcome_id=o.id
  JOIN documents_version v ON v.id=b.version_id JOIN documents_publication p ON p.version_id=v.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND cr.case_id=NEW.case_id AND cr.id=(NEW.request->>'change')::bigint AND cr.current_id=cv.id
   AND ea.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint AND ea.created_at<=o.implemented_at
   AND rr.snapshot->>'authorization_id'=ea.id::text AND rr.snapshot->>'status' IN ('evidenced_on_time','completed_with_lateness_exception')
   AND b.manifest->>'reconciliation_id'=rr.id::text AND b.manifest->>'outcome_id'=o.id::text
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id AND v.template_id=(e.body::jsonb->'inputs'->>'template_id')::bigint
   AND v.audience=e.body::jsonb->'inputs'->>'audience'
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'retrospective_record'=rr.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'retrospective_status'=rr.snapshot->>'status'
   AND EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient
    WHERE NOT EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint)))
 THEN RAISE EXCEPTION 'Observed exact native Emergency retrospective and every report receipt required; deployment and ordinary closure are not granted'; END IF;
"""
assert SQL.count(' RETURN NEW;')==1
SQL=SQL.replace(' RETURN NEW;',VERIFIED+' RETURN NEW;')
assert SQL.replace(SOURCE,'').replace(VERIFIED,'').replace(",'pmo-emergency/v1'",'').replace(" WHEN 'pmo-emergency/v1' THEN 'OPS.factory_emergency_execution'",'')==PREVIOUS
class Migration(migrations.Migration):
    dependencies=[('workflows','0064_factory_change')]
    operations=[migrations.RunSQL(SQL,PREVIOUS)]
