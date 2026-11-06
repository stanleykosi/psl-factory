"""Add selected-line statement proof without weakening existing formula verification."""
from importlib import import_module
from django.db import migrations

PREVIOUS=import_module('apps.workflows.migrations.0062_rfp_historical_outcome').SQL
START=PREVIOUS.index(" IF NEW.definition='finance-accounts/v1' AND NEW.status='verified'")
END=PREVIOUS.index(" END IF;",START)+len(' END IF;')
ORIGINAL='\n'+PREVIOUS[START:END]+'\n'
PREFIX=" IF NEW.definition='finance-accounts/v1' AND NEW.status='verified' AND NOT EXISTS("
SUFFIX="\n THEN RAISE EXCEPTION 'Current native accounting binding/output review and all exact recipient receipts required'; END IF;\n"
assert ORIGINAL.startswith('\n'+PREFIX) and ORIGINAL.endswith(SUFFIX)
query=ORIGINAL[len('\n'+PREFIX):-len(SUFFIX)]
assert query.endswith(')')
query=query[:-1]
statement=query.replace("r.kind='formula'", "r.kind='statement'")
statement += """
   AND EXISTS(SELECT 1 FROM policy_configuration pc JOIN policy_registeredreference pr ON pr.case_id=pc.case_id
    AND pr.ref=pc.envelope->'value'->>'artifact_ref' AND pr.version=(pc.envelope->'value'->>'artifact_version')::integer
    AND pr.sha256=pc.envelope->'value'->>'sha256'
    WHERE pc.id=NEW.policy_id AND pc.component='OPS.factory_accounting_execution'
     AND pr.schema_ref='schema:psl/factory-accounting-execution/v3' AND pr.content->>'statement_contract_id'=r.request->>'contract_id')
   AND r.result->>'status'='complete' AND r.result->>'scope'='selected_statement_lines'
   AND r.result->'whole_statement_certified'='false'::jsonb
   AND EXISTS(SELECT 1 FROM finance_financereview cr JOIN policy_configuration cc ON cc.id=cr.configuration_id
    WHERE cc.id=(r.request->>'contract_id')::bigint AND cc.case_id=r.case_id AND cc.component='D06.statement_contract'
     AND cr.purpose='formula' AND cr.verdict='approve'
     AND cr.id=(SELECT max(id) FROM finance_financereview WHERE configuration_id=cc.id AND purpose='formula')
     AND cr.id::text=r.snapshot->'reviews'->'D06.statement_contract'->>'id'
     AND (SELECT state FROM policy_policystate WHERE configuration_id=cc.id ORDER BY id DESC LIMIT 1)='active')
   AND jsonb_array_length(r.snapshot->'inputs')>0
   AND (SELECT count(*) FROM finance_financestatementinput si WHERE si.statement_id=r.id)=jsonb_array_length(r.snapshot->'inputs')
   AND NOT EXISTS(SELECT 1 FROM finance_financestatementinput si
    JOIN finance_financerun sr ON sr.id=si.source_run_id
    JOIN finance_financereview rv ON rv.id=si.source_review_id
    JOIN finance_financesource ss ON ss.id=sr.source_id
    WHERE si.statement_id=r.id AND (sr.case_id<>r.case_id OR rv.run_id<>sr.id OR rv.verdict<>'approve'
     OR rv.id<>(SELECT max(id) FROM finance_financereview WHERE run_id=sr.id AND purpose='output')
     OR sr.result->>'period'<>r.result->>'period' OR sr.result->>'entity'<>r.result->>'entity'
     OR sr.result->>'currency'<>r.result->>'currency' OR ss.accounting_basis IS DISTINCT FROM r.result->>'accounting_basis'
     OR si.declaration->>'source_sign' IS NULL OR si.declaration->>'source_sign' IS DISTINCT FROM si.declaration->>'destination_sign'
     OR sr.result->'company'->si.metric->'value' IS DISTINCT FROM r.result->'company'->si.destination->'value'
     OR sr.result->'company'->si.metric->>'unit' IS DISTINCT FROM si.declaration->>'unit'))
"""
REPLACEMENT='\n'+PREFIX+query+') AND NOT EXISTS('+statement+')'+SUFFIX
assert PREVIOUS.count(ORIGINAL)==1
SQL=PREVIOUS.replace(ORIGINAL,REPLACEMENT)
# Removing just the additive statement condition reconstructs all prior guard bytes.
assert SQL.replace(REPLACEMENT,ORIGINAL)==PREVIOUS

class Migration(migrations.Migration):
    dependencies=[('workflows','0062_rfp_historical_outcome'),('finance','0063_statement_inputs')]
    operations=[migrations.RunSQL(SQL,PREVIOUS)]
