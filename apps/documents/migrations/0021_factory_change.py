"""Explicit change publication scope; earlier native envelopes remain unchanged."""
from importlib import import_module
from django.db import migrations
PREVIOUS=import_module('apps.documents.migrations.0020_statement_scope').SQL
BRANCH=r"""
    OR
    (w.definition='pmo-change/v1' AND p.component='OPS.factory_change_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND e.kind='agent_private_change_intake'
     AND EXISTS(SELECT 1 FROM pmo_changedocumentbinding b
      JOIN pmo_changeauthorization ca ON ca.id=b.authorization_id JOIN pmo_changeversion cv ON cv.id=ca.version_id
      JOIN pmo_changerequest cr ON cr.id=cv.change_id
      WHERE b.version_id=v.id AND b.purpose IN ('notice','go_live') AND v.audience='client'
       AND cr.case_id=w.case_id AND cr.id=(w.request->>'change')::bigint AND cr.current_id=cv.id
       AND cv.id=(e.body::jsonb->>'change_version_id')::bigint
       AND ca.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint
       AND v.template_id=(e.body::jsonb->'inputs'->>'template_id')::bigint
       AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
        WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed'
         AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text AND a.result->>'purpose'=b.purpose)))
"""
MARKER='\n   ))'
assert PREVIOUS.count(MARKER)==1
SQL=PREVIOUS.replace(MARKER,BRANCH+MARKER)
assert SQL.replace(BRANCH,'')==PREVIOUS
class Migration(migrations.Migration):
    dependencies=[('documents','0020_statement_scope'),('workflows','0064_factory_change')]
    operations=[migrations.RunSQL(SQL,PREVIOUS)]
