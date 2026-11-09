"""Add exact native PPE inventory without weakening the formula input guard."""
import django.db.models.deletion
from django.db import migrations, models
from django.conf import settings

SQL="""
CREATE FUNCTION psl_statement_ppe_input_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(
  SELECT 1 FROM finance_financerun s
  JOIN finance_schedulework w ON w.id=NEW.schedule_id
  JOIN finance_schedulereview r ON r.id=NEW.schedule_review_id
  JOIN policy_configuration c ON c.id=NEW.contract_id
  JOIN policy_registeredreference cfg ON cfg.case_id=c.case_id
   AND cfg.ref=c.envelope->'value'->>'artifact_ref' AND cfg.version=(c.envelope->'value'->>'artifact_version')::integer
   AND cfg.sha256=c.envelope->'value'->>'sha256'
  WHERE s.id=NEW.statement_id AND s.kind='statement' AND w.kind='ppe_schedule'
   AND s.case_id=w.case_id AND c.case_id=s.case_id AND c.component='D06.statement_contract'
   AND r.work_id=w.id AND r.verdict='approve' AND r.authority->>'purpose'='schedule'
   AND NEW.declaration->>'source_type'='ppe_schedule'
   AND NEW.declaration->>'schedule_id'=w.id::text
   AND NEW.declaration->>'schedule_review_id'=r.id::text
   AND NEW.declaration->>'schedule_sha256'=w.sha256
   AND NEW.declaration->>'register_id'=w.payload->>'register_id'
   AND NEW.declaration->>'destination'=NEW.destination AND NEW.declaration->>'metric'=NEW.metric
   AND NEW.metric IN ('cost','accumulated','book_value','charge')
   AND NEW.declaration->>'source_location'='totals.'||NEW.metric
   AND NEW.declaration->>'source_sign' IS NOT NULL
   AND NEW.declaration->>'source_sign'=NEW.declaration->>'destination_sign'
   AND NEW.declaration->>'unit'=w.result->'scope'->>'unit'
   AND s.result->'company'->NEW.destination->'value'=w.result->'totals'->NEW.metric
   AND s.request->>'contract_id'=c.id::text
   AND cfg.schema_ref='schema:psl/finance-statement/v3'
   AND EXISTS(SELECT 1 FROM jsonb_array_elements(cfg.content->'inputs') line WHERE line=NEW.declaration)
   AND EXISTS(SELECT 1 FROM jsonb_array_elements(s.snapshot->'inputs') i
     WHERE i->'declaration'=NEW.declaration AND i->'review'->>'id'=r.id::text
      AND i->>'schedule_sha256'=w.sha256 AND i->>'operation_key'=w.operation_key)
   AND NOT EXISTS(SELECT 1 FROM finance_financestatementinput existing_input
     WHERE existing_input.statement_id=s.id AND existing_input.destination=NEW.destination)
 ) THEN RAISE EXCEPTION 'Exact native PPE statement input and review required'; END IF;
 RETURN NEW;
END $$;
CREATE FUNCTION psl_statement_source_exclusive() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM id FROM finance_financerun WHERE id=NEW.statement_id FOR UPDATE;
 IF (TG_TABLE_NAME='finance_financestatementppeinput' AND EXISTS(
   SELECT 1 FROM finance_financestatementinput WHERE statement_id=NEW.statement_id AND destination=NEW.destination))
 OR (TG_TABLE_NAME='finance_financestatementinput' AND EXISTS(
   SELECT 1 FROM finance_financestatementppeinput WHERE statement_id=NEW.statement_id AND destination=NEW.destination))
 THEN RAISE EXCEPTION 'Statement destination must have exactly one native source type'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_statement_source_exclusive BEFORE INSERT ON finance_financestatementinput FOR EACH ROW EXECUTE FUNCTION psl_statement_source_exclusive();
CREATE TRIGGER psl_statement_source_exclusive BEFORE INSERT ON finance_financestatementppeinput FOR EACH ROW EXECUTE FUNCTION psl_statement_source_exclusive();
CREATE TRIGGER psl_statement_ppe_identity BEFORE INSERT ON finance_financestatementppeinput FOR EACH ROW EXECUTE FUNCTION psl_statement_ppe_input_guard();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_financestatementppeinput FOR EACH ROW EXECUTE FUNCTION psl_append_only();
"""

CURRENT_SQL = r"""
CREATE OR REPLACE FUNCTION psl_statement_ppe_current(sid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_financerun s WHERE s.id=sid AND s.kind='statement'
  AND (SELECT count(*) FROM finance_financestatementppeinput WHERE statement_id=s.id)=
      (SELECT count(*) FROM jsonb_array_elements(s.snapshot->'inputs') i WHERE i->'declaration'->>'source_type'='ppe_schedule')
  AND NOT EXISTS(SELECT 1 FROM finance_financestatementppeinput si WHERE si.statement_id=s.id AND NOT EXISTS(
   SELECT 1 FROM finance_schedulework w JOIN finance_schedulereview rv ON rv.id=si.schedule_review_id
    JOIN core_evidence e ON e.id=(si.declaration->>'mapping_evidence_id')::bigint
   WHERE w.id=si.schedule_id AND w.case_id=s.case_id AND rv.work_id=w.id
    AND rv.authority->>'purpose'='schedule' AND psl_ppe_schedule_current(w.id) AND psl_ppe_review_current(rv.id)
    AND psl_ppe_grants(s.case_id,s.actor_id,ARRAY['case.read','finance.read','ppe.read'])
    AND si.declaration->>'schedule_sha256'=w.sha256 AND si.declaration->>'register_id'=w.payload->>'register_id'
    AND si.declaration->>'schedule_id'=w.id::text AND si.declaration->>'schedule_review_id'=rv.id::text
    AND si.declaration->>'destination'=si.destination AND si.declaration->>'metric'=si.metric
    AND si.declaration->>'source_location'='totals.'||si.metric
    AND si.declaration->>'source_sign' IS NOT NULL
    AND si.declaration->>'source_sign'=si.declaration->>'destination_sign'
    AND si.declaration->>'unit'=w.result->'scope'->>'unit'
    AND w.result->'scope'->>'entity'=s.result->>'entity' AND w.result->'scope'->>'currency'=s.result->>'currency'
    AND (w.parent_id IS NULL OR EXISTS(SELECT 1 FROM finance_financerun ledger JOIN finance_financesource basis ON basis.id=ledger.source_id WHERE ledger.id=w.parent_id AND basis.accounting_basis=s.result->>'accounting_basis'))
    AND si.declaration->'coverage'->>'period_start'=w.result->'scope'->>'period_start'
    AND si.declaration->'coverage'->>'period_end'=w.result->'scope'->>'period_end'
    AND si.declaration->'coverage'->>'label_as_of'=w.result->'scope'->>'label_as_of'
    AND s.result->'company'->si.destination->'value'=w.result->'totals'->si.metric
    AND s.result->'company'->si.destination->>'unit'=si.declaration->>'unit'
    AND e.case_id=s.case_id AND e.kind='policy_decision'
    AND e.body::jsonb=jsonb_build_object('protocol','ppe-statement-identity/v1','entity',s.result->>'entity',
      'period',s.result->>'period','currency',s.result->>'currency','accounting_basis',s.result->>'accounting_basis',
      'input',si.declaration-'mapping_evidence_id')
    AND EXISTS(SELECT 1 FROM jsonb_array_elements(s.snapshot->'inputs') i WHERE i->'declaration'=si.declaration
      AND i->'review'->>'id'=rv.id::text AND i->>'schedule_sha256'=w.sha256 AND i->>'operation_key'=w.operation_key)
  )));
$$;
"""
PROJECTION_SQL = r"""CREATE FUNCTION psl_statement_ppe_projection_valid(_run bigint, _evidence bigint, _actor bigint, _snapshot jsonb, _projection jsonb, _hash text) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(
 SELECT 1 FROM finance_financerun r JOIN core_evidence e ON e.id=_evidence
 JOIN finance_financereview rv ON rv.id=(_snapshot->>'output_review')::bigint
 JOIN policy_configuration c ON c.id=(_snapshot->>'projection_config')::bigint
 JOIN policy_registeredreference cfg ON cfg.case_id=c.case_id AND cfg.ref=c.envelope->'value'->>'artifact_ref'
  AND cfg.version=(c.envelope->'value'->>'artifact_version')::integer AND cfg.sha256=c.envelope->'value'->>'sha256'
 WHERE r.id=_run AND r.kind='statement' AND r.result->>'status'='complete'
  AND r.result->'whole_statement_certified'='false'::jsonb
  AND EXISTS(SELECT 1 FROM finance_financestatementppeinput i WHERE i.statement_id=r.id)
  AND psl_statement_ppe_current(r.id)
  AND e.case_id=r.case_id AND e.created_by_id=_actor
  AND e.kind='finance_report_snapshot' AND e.source='derived:ppe-statement:'||r.id::text
  AND e.sha256=_hash AND e.sha256=encode(sha256(convert_to(e.body,'UTF8')),'hex')
  AND e.body::jsonb=_projection
  AND _snapshot->>'run'=r.id::text AND _snapshot->>'run_key'=r.operation_key
  AND psl_ppe_grants(r.case_id,_actor,ARRAY['case.read','finance.read','ppe.read','finance.publish','document.draft'])
  AND rv.run_id=r.id AND rv.case_id=r.case_id AND rv.purpose='output' AND psl_ppe_finance_review_current(rv.id)
  AND psl_ppe_grants(r.case_id,rv.actor_id,ARRAY['case.read','finance.read','ppe.read'])
  AND psl_ppe_policy_current(r.case_id,(r.request->>'contract_id')::bigint)
  AND psl_ppe_finance_review_current((r.snapshot->'reviews'->'D06.statement_contract'->>'id')::bigint)
  AND c.case_id=r.case_id AND c.component='D10.audience_projection_rules' AND psl_ppe_policy_current(r.case_id,c.id)
  AND EXISTS(SELECT 1 FROM jsonb_array_elements(cfg.content->'audiences') a WHERE a=_snapshot->'projection' AND a->>'audience'=_snapshot->>'audience')
  AND EXISTS(SELECT 1 FROM policy_configuration roles
   CROSS JOIN LATERAL jsonb_array_elements_text(roles.envelope->'value') chosen(ref)
   JOIN policy_registeredreference role ON role.case_id=roles.case_id AND role.ref=chosen.ref AND role.version=1
   WHERE roles.case_id=r.case_id AND roles.component='D05.role_principal_assignments' AND psl_ppe_policy_current(r.case_id,roles.id)
    AND role.content->>'user_id'=_actor::text
    AND _snapshot->'projection'->'publisher_roles' ? (role.content->>'role')
    AND (NOT role.content ? 'eligibility' OR ((role.content->'eligibility'->>'valid_from')::timestamptz<=clock_timestamp() AND (role.content->'eligibility'->>'valid_until')::timestamptz>clock_timestamp())))
  AND _projection->>'entity'=r.result->>'entity' AND _projection->>'period'=r.result->>'period'
  AND _projection->>'currency'=r.result->>'currency' AND _projection->>'accounting_basis'=r.result->>'accounting_basis'
  AND _projection->>'source_run'=r.id::text AND _projection->'by_bu'='{}'::jsonb
  AND _projection->'company'=CASE WHEN _snapshot->'projection'->'include_company'='true'::jsonb THEN
   (SELECT coalesce(jsonb_object_agg(key,jsonb_build_object('value',r.result->'company'->key->'value','unit',r.result->'company'->key->'unit','rule_key',key)),'{}'::jsonb)
    FROM jsonb_array_elements_text(_snapshot->'projection'->'formula_keys') key)
   ELSE '{}'::jsonb END
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(_snapshot->'projection'->'formula_keys') key WHERE NOT r.result->'company' ? key)
  AND _projection->'columns'='["actual"]'::jsonb AND _projection->'included_periods'='[]'::jsonb
  AND _projection->'ratio_multiplier'='null'::jsonb AND _projection->'comparison_definition'='null'::jsonb
  AND _projection->'budget_version'='null'::jsonb
  AND _projection->'chart_spec'=CASE WHEN _snapshot->'projection'->'charts'='true'::jsonb
   THEN '{"implementation":"signed_grouped_bars_v1","data":[]}'::jsonb ELSE 'null'::jsonb END
  AND _projection->>'scope'='Selected statement lines only; full statement and balance-sheet oracle remain deferred. Selected source, reporting adjustments and configured metrics; not ledger posting, financial close, invoice or payment.'
  AND _projection-ARRAY['entity','period','currency','company','by_bu','source_run','accounting_basis','ratio_multiplier','comparison_definition','columns','included_periods','budget_version','chart_spec','scope']='{}'::jsonb

 );
$$;
CREATE FUNCTION psl_statement_ppe_projection_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT psl_statement_ppe_projection_valid(NEW.run_id,NEW.evidence_id,NEW.actor_id,NEW.snapshot,NEW.projection,NEW.payload_hash)
 THEN RAISE EXCEPTION 'Exact current native PPE projection, creator, source inventory and payload hash required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_statement_ppe_projection_identity BEFORE INSERT ON finance_financestatementppeprojection FOR EACH ROW EXECUTE FUNCTION psl_statement_ppe_projection_guard();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_financestatementppeprojection FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE FUNCTION psl_statement_ppe_document_valid(rid bigint, vid bigint, bound_snapshot jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT NOT EXISTS(SELECT 1 FROM finance_financerun r WHERE r.id=rid AND
  (EXISTS(SELECT 1 FROM finance_financestatementppeinput i WHERE i.statement_id=r.id)
   OR EXISTS(SELECT 1 FROM jsonb_array_elements(coalesce(r.snapshot->'inputs','[]'::jsonb)) i WHERE i->'declaration'->>'source_type'='ppe_schedule')))
 OR EXISTS(SELECT 1 FROM finance_financestatementppeprojection p JOIN finance_financerun r ON r.id=p.run_id
  JOIN core_evidence e ON e.id=p.evidence_id JOIN documents_version v ON v.id=vid
  JOIN documents_document d ON d.id=v.document_id JOIN documents_template t ON t.id=v.template_id
  WHERE p.run_id=rid AND p.snapshot=bound_snapshot AND d.case_id=r.case_id AND t.case_id=r.case_id
   AND psl_statement_ppe_projection_valid(p.run_id,p.evidence_id,p.actor_id,p.snapshot,p.projection,p.payload_hash)
   AND v.created_by_id=p.actor_id AND v.audience=p.snapshot->>'audience'
   AND d.title='Finance configured output '||r.id::text AND t.definition->>'document_type'='finance_report'
   AND v.source_manifest=jsonb_build_array(jsonb_build_object('id',e.id,'version',e.version,'sha256',e.sha256))
   AND v.fields->'executive_summary'->'evidence_ids'=jsonb_build_array(e.id)
   AND v.fields->'financial_metrics'->'evidence_ids'=jsonb_build_array(e.id)
   AND v.fields->'bu_totals'->'evidence_ids'=jsonb_build_array(e.id)
   AND v.fields-ARRAY['executive_summary','financial_metrics','bu_totals']='{}'::jsonb
   AND v.fields->'executive_summary'->>'text'='Configured Finance metrics for '||(p.projection->>'entity')||' / '||(p.projection->>'period')||' / '||(p.projection->>'currency')||'. '||(p.projection->>'scope')
   AND (v.fields->'financial_metrics'->>'text')::jsonb=jsonb_build_object('accounting_basis',p.projection->'accounting_basis',
    'figures',p.projection->'company','columns',p.projection->'columns','ratio_definition',p.projection->'comparison_definition',
    'ratio_multiplier',p.projection->'ratio_multiplier','periods',p.projection->'included_periods','chart_spec',p.projection->'chart_spec')
   AND (v.fields->'bu_totals'->>'text')::jsonb=p.projection->'by_bu'
   AND v.payload=jsonb_build_object('title',d.title,'type','finance_report','sections',
    (SELECT jsonb_agg(jsonb_build_object('heading',section,'text',v.fields->section->>'text') ORDER BY ordinal)
     FROM jsonb_array_elements_text(t.definition->'audience_fields'->v.audience) WITH ORDINALITY AS parts(section,ordinal)
     WHERE v.fields ? section)));
$$;
CREATE FUNCTION psl_statement_ppe_document_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT psl_statement_ppe_document_valid(NEW.run_id,NEW.version_id,NEW.snapshot)
 THEN RAISE EXCEPTION 'Exact model-bound native PPE projection required for controlled document'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_statement_ppe_document_identity BEFORE INSERT ON finance_financedocumentbinding FOR EACH ROW EXECUTE FUNCTION psl_statement_ppe_document_guard();
"""
SQL += CURRENT_SQL + PROJECTION_SQL

class Migration(migrations.Migration):
    dependencies=[('finance','0063_statement_inputs'),('workflows','0068_ppe_identity_dependency_replacement')]
    operations=[migrations.CreateModel(name='FinanceStatementPPEInput',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('destination',models.CharField(max_length=100)),('metric',models.CharField(max_length=100)),('declaration',models.JSONField()),
        ('statement',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='statement_ppe_inputs',to='finance.financerun')),
        ('schedule',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='+',to='finance.schedulework')),
        ('schedule_review',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='+',to='finance.schedulereview')),
        ('contract',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='+',to='policy.configuration')),
    ],options={'constraints':[models.UniqueConstraint(fields=('statement','destination'),name='finance_statement_ppe_destination')]}),
    migrations.CreateModel(name='FinanceStatementPPEProjection',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('snapshot',models.JSONField()),('projection',models.JSONField()),('payload_hash',models.CharField(max_length=64)),
        ('created_at',models.DateTimeField(auto_now_add=True)),
        ('run',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='ppe_projections',to='finance.financerun')),
        ('evidence',models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name='ppe_statement_projection',to='core.evidence')),
        ('actor',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='+',to=settings.AUTH_USER_MODEL)),
    ]),
    migrations.RunSQL(SQL,'DROP TRIGGER psl_statement_ppe_document_identity ON finance_financedocumentbinding; DROP FUNCTION psl_statement_ppe_document_guard(); DROP FUNCTION psl_statement_ppe_document_valid(bigint,bigint,jsonb); DROP TRIGGER psl_statement_ppe_projection_identity ON finance_financestatementppeprojection; DROP TRIGGER psl_immutable ON finance_financestatementppeprojection; DROP FUNCTION psl_statement_ppe_projection_guard(); DROP FUNCTION psl_statement_ppe_projection_valid(bigint,bigint,bigint,jsonb,jsonb,text); DROP FUNCTION psl_statement_ppe_current(bigint); DROP TRIGGER psl_statement_source_exclusive ON finance_financestatementinput; DROP TRIGGER psl_statement_source_exclusive ON finance_financestatementppeinput; DROP FUNCTION psl_statement_source_exclusive(); DROP TRIGGER psl_statement_ppe_identity ON finance_financestatementppeinput; DROP TRIGGER psl_immutable ON finance_financestatementppeinput; DROP FUNCTION psl_statement_ppe_input_guard();')]
