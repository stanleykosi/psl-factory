"""Independent F43 publication guard; frozen SQL, no application helper imports."""
from django.db import migrations

SQL=r"""
CREATE FUNCTION psl_group_role_assigned(config_id bigint, uid bigint, role_name text, pc uuid) RETURNS boolean LANGUAGE sql STABLE AS $$
 WITH assigned AS (
 SELECT rr.content v FROM policy_configuration c CROSS JOIN LATERAL jsonb_array_elements_text(c.envelope->'value') ref
 JOIN policy_registeredreference rr ON rr.case_id=c.case_id AND rr.ref=ref AND rr.version=1
 WHERE c.id=config_id AND c.case_id=pc AND c.component='D05.role_principal_assignments' AND rr.content->>'user_id'=uid::text)
 SELECT EXISTS(SELECT 1 FROM assigned WHERE v->>'role'=role_name)
 AND (SELECT count(DISTINCT v->>'role') FROM assigned)>0
 AND ((SELECT count(DISTINCT v->>'role') FROM assigned)=1
 OR (NOT EXISTS(SELECT 1 FROM assigned WHERE v ? 'eligibility') AND EXISTS(SELECT 1 FROM core_case WHERE id=pc AND synthetic))
 OR (NOT EXISTS(SELECT 1 FROM assigned WHERE NOT v ? 'eligibility' OR (v->'eligibility'->>'valid_from')::timestamptz>clock_timestamp() OR (v->'eligibility'->>'valid_until')::timestamptz<=clock_timestamp())
 AND (SELECT count(DISTINCT v->'eligibility') FROM assigned)=1
 AND (SELECT v->'eligibility'->'roles' FROM assigned LIMIT 1) @> (SELECT jsonb_agg(v->'role') FROM assigned)
 AND jsonb_array_length((SELECT v->'eligibility'->'roles' FROM assigned LIMIT 1))=(SELECT count(*) FROM assigned)))
 $$;
CREATE FUNCTION psl_group_forecast_publication() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v documents_version; b finance_forecastbinding; r finance_forecastrun;
 rv documents_controlledreview; pc uuid; p jsonb; projected jsonb; selected jsonb;
 meta jsonb; rowkey text; rowvalue jsonb; config_id bigint; cfg policy_configuration;
 state text; item record; source core_evidence; oracle core_evidence; fr finance_forecastreview; t documents_template;
BEGIN
 SELECT * INTO v FROM documents_version WHERE id=NEW.version_id;
 IF v.audience<>'group' THEN RETURN NEW; END IF;
 SELECT * INTO b FROM finance_forecastbinding WHERE version_id=v.id;
 SELECT * INTO r FROM finance_forecastrun WHERE id=b.run_id;
 SELECT * INTO rv FROM documents_controlledreview WHERE id=NEW.review_id;
 SELECT case_id INTO pc FROM documents_document WHERE id=v.document_id AND current_id=v.id;
 SELECT * INTO t FROM documents_template WHERE id=v.template_id;
 p=b.snapshot->'projection';
 IF b.id IS NULL OR pc IS NULL OR r.case_id IS DISTINCT FROM pc OR t.case_id IS DISTINCT FROM pc
 OR t.definition IS DISTINCT FROM '{"document_type":"finance_group_report","required_fields":["executive_summary","financial_metrics","bu_totals"],"audience_fields":{"group":["executive_summary","financial_metrics","bu_totals"]},"internal_review_required":true}'::jsonb
 OR p->>'implementation' IS DISTINCT FROM 'native_selected_items_v1'
 OR p->>'run_id' IS DISTINCT FROM r.id::text OR p->>'run_hash' IS DISTINCT FROM r.sha256
 OR b.snapshot->>'run_hash' IS DISTINCT FROM r.sha256
 OR b.snapshot->>'projection_implementation' IS DISTINCT FROM 'forecast-group/selected-items-v1'
 OR rv.id IS NULL OR rv.version_id IS DISTINCT FROM v.id OR rv.verdict IS DISTINCT FROM 'approve'
 OR rv.id IS DISTINCT FROM (SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
 OR rv.payload_sha256 IS DISTINCT FROM v.payload_sha256 OR rv.delegated
 OR rv.authority->>'group' IS DISTINCT FROM 'forecast-group/selected-items-v1'
 OR NOT p->'reviewer_roles' ? (rv.authority->>'role')
 OR (rv.actor_id=v.created_by_id AND p->'allow_preparer_review' IS DISTINCT FROM 'true'::jsonb)
 OR rv.authority->'policies' IS DISTINCT FROM NEW.policies
 OR rv.authority->'recipients' IS DISTINCT FROM NEW.recipient_ids
 OR rv.authority->>'retention_days' IS DISTINCT FROM NEW.retention_days::text
 OR NEW.recipient_ids IS DISTINCT FROM (SELECT jsonb_agg(x ORDER BY x::bigint) FROM jsonb_array_elements(p->'recipient_ids') x)
 OR NOT EXISTS(SELECT 1 FROM finance_forecastreview source_review WHERE source_review.run_id=r.id AND source_review.verdict='approve'
   AND source_review.id::text=b.snapshot->>'output_review' AND source_review.id=(SELECT max(id) FROM finance_forecastreview WHERE run_id=r.id))
 OR EXISTS(SELECT 1 FROM finance_forecastscenario s JOIN finance_forecastscenario n ON n.case_id=s.case_id AND n.reference=s.reference AND n.number>s.number WHERE s.id=r.scenario_id)
 OR r.result->>'as_of' IS DISTINCT FROM CURRENT_DATE::text
 THEN RAISE EXCEPTION 'PSL exact group disclosure source, review and destination required'; END IF;
 FOR item IN SELECT key,value FROM jsonb_each(NEW.policies) LOOP
   config_id=(item.value#>>'{}')::bigint;
   SELECT * INTO cfg FROM policy_configuration WHERE id=config_id AND case_id=pc AND component=item.key;
   SELECT ps.state INTO state FROM policy_policystate ps WHERE ps.configuration_id=cfg.id ORDER BY ps.id DESC LIMIT 1;
   IF cfg.id IS NULL OR state IS DISTINCT FROM 'active'
   OR (cfg.envelope->>'effective_from')::timestamptz>clock_timestamp()
   OR (cfg.envelope->>'effective_until')::timestamptz<=clock_timestamp()
   OR EXISTS(SELECT 1 FROM policy_configuration newer WHERE newer.case_id=pc AND newer.component=item.key AND newer.revision>cfg.revision
      AND (SELECT ps.state FROM policy_policystate ps WHERE ps.configuration_id=newer.id ORDER BY ps.id DESC LIMIT 1) IN ('active','revoked','superseded'))
   THEN RAISE EXCEPTION 'PSL current group publication policy required'; END IF;
 END LOOP;
 IF NOT EXISTS(SELECT 1 FROM policy_configuration c JOIN policy_registeredreference rr
  ON rr.case_id=c.case_id AND rr.ref=c.envelope->'value'->>'artifact_ref'
  AND rr.version::text=c.envelope->'value'->>'artifact_version'
  WHERE c.id::text=b.snapshot->>'projection_config' AND c.id::text=NEW.policies->>'D10.audience_projection_rules'
  AND rr.content->'group'=p)
 THEN RAISE EXCEPTION 'PSL exact owner group disclosure configuration required'; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements_text(NEW.recipient_ids) uid WHERE NOT EXISTS(
   SELECT 1 FROM identity_grant g JOIN auth_user u ON u.id=g.user_id
   WHERE g.case_id=pc AND g.user_id::text=uid AND g.action='document.receive:group' AND g.active AND u.is_active))
 OR NOT EXISTS(SELECT 1 FROM identity_grant g JOIN auth_user u ON u.id=g.user_id WHERE g.case_id=pc AND g.user_id=rv.actor_id AND g.action='document.review_controlled' AND g.active AND u.is_active)
 OR NOT EXISTS(SELECT 1 FROM identity_grant g JOIN auth_user u ON u.id=g.user_id WHERE g.case_id=pc AND g.user_id=rv.actor_id AND g.action='finance.read' AND g.active AND u.is_active)
 OR NOT EXISTS(SELECT 1 FROM identity_grant g JOIN auth_user u ON u.id=g.user_id WHERE g.case_id=pc AND g.user_id=NEW.actor_id AND g.action='document.publish' AND g.active AND u.is_active)
 THEN RAISE EXCEPTION 'PSL current group publication grants required'; END IF;
 SELECT * INTO fr FROM finance_forecastreview WHERE id=(b.snapshot->>'output_review')::bigint;
 IF NOT psl_group_role_assigned((NEW.policies->>'D05.role_principal_assignments')::bigint,rv.actor_id,rv.authority->>'role',pc)
 OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p->'publisher_roles') role_name WHERE psl_group_role_assigned((NEW.policies->>'D05.role_principal_assignments')::bigint,NEW.actor_id,role_name,pc))
 OR NOT psl_group_role_assigned((NEW.policies->>'D05.role_principal_assignments')::bigint,fr.actor_id,fr.role,pc)
 OR rv.authority->'authority'->>'D05.role_principal_assignments' IS DISTINCT FROM NEW.policies->>'D05.role_principal_assignments'
 OR fr.authority IS DISTINCT FROM b.snapshot->'forecast_authority'
 OR fr.authority->>'D05.role_principal_assignments' IS DISTINCT FROM NEW.policies->>'D05.role_principal_assignments'
 OR b.snapshot->>'method_config' IS DISTINCT FROM NEW.policies->>'D10.forecast_inclusion_rule_id'
 OR fr.snapshot->>'method' IS DISTINCT FROM NEW.policies->>'D10.forecast_inclusion_rule_id'
 OR NOT EXISTS(SELECT 1 FROM identity_grant g JOIN auth_user u ON u.id=g.user_id WHERE g.case_id=pc AND g.user_id=fr.actor_id AND g.action='finance.forecast.review' AND g.active AND u.is_active)
 OR NOT EXISTS(SELECT 1 FROM identity_grant g JOIN auth_user u ON u.id=g.user_id WHERE g.case_id=pc AND g.user_id=NEW.actor_id AND g.action='finance.publish' AND g.active AND u.is_active)
 OR NOT EXISTS(SELECT 1 FROM identity_grant g JOIN auth_user u ON u.id=g.user_id WHERE g.case_id=pc AND g.user_id=NEW.actor_id AND g.action='finance.read' AND g.active AND u.is_active)
 OR NOT EXISTS(SELECT 1 FROM policy_configuration c JOIN policy_registeredreference rr
   ON rr.case_id=c.case_id AND rr.ref=c.envelope->'value'->>'artifact_ref' AND rr.version::text=c.envelope->'value'->>'artifact_version'
   CROSS JOIN LATERAL jsonb_array_elements(rr.content->'finance') rule
   WHERE c.id::text=NEW.policies->>'D05.decision_action_matrix' AND rule=fr.authority->'finance_review_rule')
 THEN RAISE EXCEPTION 'PSL current exact group and native forecast role authority required'; END IF;
 IF NOT p->'fields' <@ '["kind","amount","expected_on","original_due","commitment","residual","matched"]'::jsonb
 OR NOT p->'metadata' <@ '["entity","currency","basis","as_of"]'::jsonb
 OR jsonb_array_length(p->'fields')=0 OR jsonb_array_length(p->'rows')=0
 THEN RAISE EXCEPTION 'PSL group selected fields required'; END IF;
 SELECT jsonb_object_agg(key,value) INTO meta FROM jsonb_each(r.result) WHERE p->'metadata' ? key;
 selected='[]'::jsonb;
 FOR rowkey IN SELECT jsonb_array_elements_text(p->'rows') LOOP
   SELECT value INTO rowvalue FROM jsonb_array_elements(r.result->'items') WHERE value->>'key'=rowkey;
   IF rowvalue IS NULL THEN RAISE EXCEPTION 'PSL group row absent'; END IF;
   selected=selected||jsonb_build_array((SELECT jsonb_object_agg(key,value) FROM jsonb_each(rowvalue) WHERE p->'fields' ? key));
 END LOOP;
 projected=jsonb_build_object('implementation','forecast-group/selected-items-v1','metadata',meta,'rows',selected,'scope','selected_assumptions_only_no_group_balances','execution_authorized',false);
 SELECT * INTO oracle FROM core_evidence WHERE id=(p->>'oracle_evidence_id')::bigint AND case_id=pc AND kind='forecast_group_oracle';
 IF oracle.id IS NULL OR oracle.body::jsonb IS DISTINCT FROM projected OR oracle.sha256 IS DISTINCT FROM b.snapshot->>'oracle_hash'
 THEN RAISE EXCEPTION 'PSL exact supplied group disclosure oracle required'; END IF;
 SELECT * INTO source FROM core_evidence WHERE id=(v.fields->'financial_metrics'->'evidence_ids'->>0)::bigint AND case_id=pc AND kind='finance_group_snapshot';
 IF source.id IS NULL OR source.body::jsonb IS DISTINCT FROM projected
 OR (v.fields->'financial_metrics'->>'text')::jsonb IS DISTINCT FROM projected
 OR v.fields-ARRAY['executive_summary','financial_metrics','bu_totals']<>'{}'::jsonb
 OR v.fields->'executive_summary'->>'text' IS DISTINCT FROM 'Owner-selected cash assumptions only. No group opening, closing or aggregate balance is calculated. No payment authority is granted.'
 OR v.fields->'bu_totals'->>'text' IS DISTINCT FROM 'No BU allocation, entity consolidation or full-business accounting oracle is inferred.'
 OR EXISTS(SELECT 1 FROM jsonb_each(v.fields) f WHERE f.value-ARRAY['text','evidence_ids']<>'{}'::jsonb OR f.value->'evidence_ids'<>jsonb_build_array(source.id))
 OR v.baseline_manifest IS DISTINCT FROM '{}'::jsonb
 OR v.source_manifest IS DISTINCT FROM jsonb_build_array(jsonb_build_object('id',source.id,'version',source.version,'sha256',source.sha256))
 OR v.payload IS DISTINCT FROM jsonb_build_object('title','Selected group cash forecast','type','finance_group_report','sections',
 jsonb_build_array(jsonb_build_object('heading','executive_summary','text',v.fields->'executive_summary'->>'text'),jsonb_build_object('heading','financial_metrics','text',v.fields->'financial_metrics'->>'text'),jsonb_build_object('heading','bu_totals','text',v.fields->'bu_totals'->>'text')))
 THEN RAISE EXCEPTION 'PSL group payload contains unapproved content'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER psl_group_forecast BEFORE INSERT ON documents_publication FOR EACH ROW EXECUTE FUNCTION psl_group_forecast_publication();
"""

class Migration(migrations.Migration):
    dependencies=[('documents','0023_factory_forecast')]
    operations=[migrations.RunSQL(SQL,'DROP TRIGGER psl_group_forecast ON documents_publication; DROP FUNCTION psl_group_forecast_publication(); DROP FUNCTION psl_group_role_assigned(bigint,bigint,text,uuid);')]
