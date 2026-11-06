"""Explicit Emergency retrospective publication scope; no ordinary change substitution."""
from importlib import import_module
from django.db import migrations
PREVIOUS=import_module('apps.documents.migrations.0021_factory_change').SQL
BRANCH=r"""
    OR
    (w.definition='pmo-emergency/v1' AND p.component='OPS.factory_emergency_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND e.kind='agent_private_emergency_intake'
     AND EXISTS(SELECT 1 FROM pmo_emergencydocumentbinding b JOIN pmo_emergencyoutcome o ON o.id=b.outcome_id
      JOIN pmo_emergencyprofile ep ON ep.id=o.profile_id JOIN pmo_changeversion cv ON cv.id=ep.version_id
      JOIN pmo_changerequest cr ON cr.id=cv.change_id JOIN pmo_emergencyretrospectiverecord rr ON rr.outcome_id=o.id
      JOIN pmo_emergencyauthorization ea ON ea.id=o.authorization_id AND ea.profile_id=ep.id
      WHERE b.version_id=v.id AND cr.case_id=w.case_id AND cr.id=(w.request->>'change')::bigint AND cr.current_id=cv.id
       AND ep.id=(e.body::jsonb->>'profile_id')::bigint AND o.id=(e.body::jsonb->'inputs'->>'outcome_id')::bigint
       AND ea.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint AND ea.created_at<=o.implemented_at
       AND b.manifest->>'reconciliation_id'=rr.id::text
       AND v.template_id=(e.body::jsonb->'inputs'->>'template_id')::bigint AND v.audience=e.body::jsonb->'inputs'->>'audience'
       AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
        WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed'
         AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text AND a.result->>'outcome'=o.id::text)))
"""
MARKER='\n   ))'
assert PREVIOUS.count(MARKER)==1
SQL=PREVIOUS.replace(MARKER,BRANCH+MARKER)
assert SQL.replace(BRANCH,'')==PREVIOUS
class Migration(migrations.Migration):
    dependencies=[('documents','0021_factory_change'),('workflows','0065_factory_emergency')]
    operations=[migrations.RunSQL(SQL,PREVIOUS)]
