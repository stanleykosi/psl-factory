"""Bind RFP publication to the exact native response and observed document activity."""
from importlib import import_module
from django.db import migrations

SQL=import_module('apps.documents.migrations.0018_factory_accounting_scope').SQL
MARKER='\n   ))'
assert SQL.count(MARKER)==1
BRANCH=r"""
    OR
    (w.definition='rfp-response/v1' AND p.component='OPS.factory_rfp_execution'
     AND e.kind='agent_private_rfp_intake' AND w.policy_id=p.id AND w.source_head_id=e.id AND v.audience='client'
     AND EXISTS(SELECT 1 FROM pmo_rfpdocumentbinding b JOIN pmo_rfpresponse r ON r.id=b.response_id
      JOIN pmo_rfpcase root ON root.id=r.rfp_id JOIN pmo_commercialrevision cr ON cr.id=r.commercial_id
      JOIN core_evidence draft ON draft.id=(cr.sources->>'sow')::bigint
      WHERE b.version_id=v.id AND root.case_id=w.case_id AND root.id=(w.request->>'rfp')::bigint
       AND root.current_response_id=r.id AND root.current_intake_id=r.intake_id AND r.intake_id=(e.body::jsonb->>'intake')::bigint
       AND r.evidence_id=(e.body::jsonb->>'response_evidence')::bigint AND r.matrix=e.body::jsonb->'matrix'
       AND draft.body::jsonb->'public_terms_id'=e.body::jsonb->'public_terms'
       AND cr.sources->'requirements'=e.body::jsonb->'sources'->'requirements'
       AND cr.sources->'plan'=e.body::jsonb->'sources'->'plan' AND cr.sources->'costing'=e.body::jsonb->'sources'->'costing')
     AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
      WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed'
       AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text))
"""
SQL=SQL.replace(MARKER,BRANCH+MARKER)

class Migration(migrations.Migration):
    dependencies=[('documents','0018_factory_accounting_scope'),('workflows','0060_factory_rfp')]
    operations=[migrations.RunSQL(SQL)]
