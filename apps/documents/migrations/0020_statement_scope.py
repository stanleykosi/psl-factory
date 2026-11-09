"""Add only explicitly selected reviewed statement-line publication scope."""
from importlib import import_module
from django.db import migrations

PREVIOUS=import_module('apps.documents.migrations.0019_factory_rfp_scope').SQL
MARKER='\n   ))'
assert PREVIOUS.count(MARKER)==1
BRANCH=r"""
    OR
    (w.definition='finance-accounts/v1' AND p.component='OPS.factory_accounting_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND e.kind='agent_private_accounting_intake'
     AND EXISTS(SELECT 1 FROM finance_financedocumentbinding b JOIN finance_financerun r ON r.id=b.run_id
      JOIN finance_financesource s ON s.id=r.source_id
      JOIN policy_registeredreference cfg ON cfg.case_id=p.case_id
       AND cfg.ref=p.envelope->'value'->>'artifact_ref' AND cfg.version=(p.envelope->'value'->>'artifact_version')::integer
       AND cfg.sha256=p.envelope->'value'->>'sha256'
      WHERE b.version_id=v.id AND r.case_id=w.case_id AND r.kind='statement'
       AND cfg.schema_ref='schema:psl/factory-accounting-execution/v3'
       AND cfg.content->>'statement_contract_id'=r.request->>'contract_id'
       AND r.result->>'scope'='selected_statement_lines' AND r.result->'whole_statement_certified'='false'::jsonb
       AND r.result->>'status'='complete' AND s.id=(e.body::jsonb->>'source')::bigint AND s.batch_id=(w.request->>'batch')::bigint
       AND (SELECT count(*) FROM finance_financestatementinput si WHERE si.statement_id=r.id)=jsonb_array_length(r.snapshot->'inputs')
       AND jsonb_array_length(r.snapshot->'inputs')>0
       AND EXISTS(SELECT 1 FROM finance_financereview fr WHERE fr.run_id=r.id AND fr.purpose='output' AND fr.verdict='approve'
        AND fr.id=(SELECT max(id) FROM finance_financereview WHERE run_id=r.id AND purpose='output')
        AND b.snapshot->>'output_review'=fr.id::text)
       AND NOT EXISTS(SELECT 1 FROM finance_financestatementinput si JOIN finance_financereview fr ON fr.id=si.source_review_id
        WHERE si.statement_id=r.id AND (fr.verdict<>'approve' OR fr.run_id<>si.source_run_id
         OR fr.id<>(SELECT max(id) FROM finance_financereview WHERE run_id=si.source_run_id AND purpose='output')))))
"""
SQL=PREVIOUS.replace(MARKER,BRANCH+MARKER)
assert SQL.replace(BRANCH,'')==PREVIOUS

class Migration(migrations.Migration):
    dependencies=[('documents','0019_factory_rfp_scope'),('workflows','0063_statement_verification'),('finance','0063_statement_inputs')]
    operations=[migrations.RunSQL(SQL,PREVIOUS)]
