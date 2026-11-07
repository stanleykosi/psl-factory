"""F42 supplied support/history and v2 continuation boundary; no old row rewrite."""

from importlib import import_module
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

SQL = r'''
CREATE FUNCTION psl_forecast_support_authorized(v finance_forecastitemsupport) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT psl_schedules_grants(v.case_id,v.actor_id,ARRAY['finance.read','finance.forecast.capture','finance.forecast.review'])
 AND psl_schedules_policy_current(v.case_id,(v.authority->>'D05.role_principal_assignments')::bigint)
 AND psl_group_role_assigned((v.authority->>'D05.role_principal_assignments')::bigint,v.actor_id,v.role,v.case_id)
 AND EXISTS(SELECT 1 FROM policy_configuration c JOIN policy_registeredreference rr ON rr.case_id=c.case_id
  AND rr.ref=c.envelope->'value'->>'artifact_ref' AND rr.version::text=c.envelope->'value'->>'artifact_version'
  CROSS JOIN LATERAL jsonb_array_elements(rr.content->'finance') rule
  JOIN finance_forecastscenario s ON s.id=v.scenario_id
  WHERE c.case_id=v.case_id AND c.component='D05.decision_action_matrix' AND psl_schedules_policy_current(v.case_id,c.id)
   AND rule=v.authority->'finance_review_rule' AND rule->>'purpose'=CASE WHEN s.parent_id IS NULL THEN 'forecast' ELSE 'forecast_rollover' END
   AND rule->>'role'=v.role AND rule->'actions' ? 'approve'
   AND (s.actor_id<>v.actor_id OR rule->'allow_preparer_review'='true'::jsonb));
$$;

CREATE FUNCTION psl_forecast_support_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE s finance_forecastscenario; root finance_forecastscenario; prev finance_forecastitemsupport;
 e core_evidence; orig core_evidence; prior core_evidence; item jsonb; prior_state text; prior_day date;
BEGIN
 PERFORM 1 FROM core_case WHERE id=NEW.case_id FOR UPDATE;
 SELECT * INTO s FROM finance_forecastscenario WHERE id=NEW.scenario_id AND case_id=NEW.case_id;
 SELECT * INTO root FROM finance_forecastscenario WHERE id=coalesce(s.root_id,s.id) AND case_id=NEW.case_id;
 SELECT value INTO item FROM jsonb_array_elements(root.payload->'items') WHERE value->>'key'=NEW.item_key;
 SELECT * INTO orig FROM core_evidence WHERE id=(item->>'evidence_id')::bigint AND case_id=NEW.case_id;
 SELECT * INTO prev FROM finance_forecastitemsupport WHERE root_id=root.id AND item_key=NEW.item_key ORDER BY id DESC LIMIT 1;
 SELECT * INTO prior FROM core_evidence WHERE id=coalesce(prev.evidence_id,orig.id);
 SELECT * INTO e FROM core_evidence WHERE id=NEW.evidence_id AND case_id=NEW.case_id;
 prior_state=coalesce(prev.uncertainty,item->>'uncertainty','unknown');prior_day=prev.observed_on;
 IF s.id IS NULL OR root.id IS NULL OR item IS NULL OR orig.id IS NULL OR prior.id IS NULL OR e.id IS NULL
 OR NEW.root_id IS DISTINCT FROM root.id OR NEW.previous_id IS DISTINCT FROM prev.id
 OR (prev.id IS NOT NULL AND NOT EXISTS(WITH RECURSIVE ancestors AS (SELECT s.id,s.parent_id UNION SELECT ps.id,ps.parent_id FROM ancestors a JOIN finance_forecastrun pr ON pr.id=a.parent_id JOIN finance_forecastscenario ps ON ps.id=pr.scenario_id) SELECT 1 FROM ancestors WHERE id=prev.scenario_id))
 OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(s.payload->'items') i WHERE i->>'key'=NEW.item_key)
 OR EXISTS(SELECT 1 FROM finance_forecastscenario n WHERE n.case_id=s.case_id AND n.reference=s.reference AND n.number>s.number)
 OR NEW.uncertainty NOT IN ('unknown','disputed','uncertain','no_known_uncertainty')
 OR NEW.mode NOT IN ('renewed_support','reaffirmation') OR length(trim(NEW.reason)) NOT BETWEEN 1 AND 4000
 OR NEW.observed_on>psl_group_forecast_business_date(clock_timestamp())
 OR NEW.snapshot IS DISTINCT FROM jsonb_build_object('original_evidence_id',orig.id,'original_evidence_sha256',orig.sha256,'original_due',item->'original_due',
   'previous_evidence_id',prior.id,'previous_evidence_sha256',prior.sha256,'evidence_sha256',e.sha256)
 OR (NEW.mode='renewed_support' AND (e.kind<>'forecast_support' OR (e.sha256=orig.sha256 OR EXISTS(SELECT 1 FROM finance_forecastitemsupport x JOIN core_evidence y ON y.id=x.evidence_id WHERE x.root_id=root.id AND x.item_key=NEW.item_key AND y.sha256=e.sha256))))
 OR (NEW.mode='reaffirmation' AND (e.id<>prior.id OR NEW.uncertainty<>prior_state OR NEW.observed_on IS DISTINCT FROM prior_day))
 OR psl_forecast_support_authorized(NEW) IS DISTINCT FROM true
 THEN RAISE EXCEPTION 'Exact current authorized forecast support predecessor, evidence and uncertainty required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_forecast_support BEFORE INSERT ON finance_forecastitemsupport FOR EACH ROW EXECUTE FUNCTION psl_forecast_support_guard();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_forecastitemsupport FOR EACH ROW EXECUTE FUNCTION psl_append_only();

CREATE FUNCTION psl_forecast_item_provenance(sid bigint) RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE s finance_forecastscenario; n finance_forecastscenario; root finance_forecastscenario; nodes bigint[]; history jsonb;
 item jsonb; original jsonb; previous_item jsonb; proof core_evidence; supports jsonb; v finance_forecastitemsupport;
 output jsonb:='{}'::jsonb; state text; active boolean; fresh boolean; continued boolean; key text;
BEGIN
 SELECT * INTO s FROM finance_forecastscenario WHERE id=sid;
 IF s.id IS NULL THEN RETURN NULL; END IF;
 n=s;nodes=ARRAY[]::bigint[];
 WHILE n.id IS NOT NULL LOOP
  IF n.id=ANY(nodes) OR n.case_id<>s.case_id THEN RETURN NULL; END IF;
  nodes=array_prepend(n.id,nodes);
  IF n.parent_id IS NULL THEN root=n;EXIT; END IF;
  SELECT ss.* INTO n FROM finance_forecastrun r JOIN finance_forecastscenario ss ON ss.id=r.scenario_id WHERE r.id=n.parent_id;
 END LOOP;
 IF root.id IS DISTINCT FROM coalesce(s.root_id,s.id) THEN RETURN NULL; END IF;
 FOR item IN SELECT value FROM jsonb_array_elements(s.payload->'items') LOOP
  key=item->>'key';history='[]'::jsonb;
  SELECT value INTO original FROM jsonb_array_elements(root.payload->'items') i WHERE i->>'key'=key;
  IF original IS NULL THEN RETURN NULL; END IF;
  FOREACH sid IN ARRAY nodes LOOP
   SELECT * INTO n FROM finance_forecastscenario WHERE id=sid;
   SELECT value INTO previous_item FROM jsonb_array_elements(n.payload->'items') i WHERE i->>'key'=key;
   IF previous_item IS NULL OR previous_item-'expected_on' IS DISTINCT FROM original-'expected_on' THEN RETURN NULL; END IF;
   history=history||jsonb_build_array(jsonb_build_object('scenario',n.id,'parent_run',n.parent_id,'as_of',n.payload->'as_of','expected_on',previous_item->'expected_on'));
  END LOOP;
  SELECT * INTO proof FROM core_evidence WHERE id=(original->>'evidence_id')::bigint AND case_id=s.case_id;
  IF proof.id IS NULL THEN RETURN NULL; END IF;
  SELECT * INTO v FROM finance_forecastitemsupport WHERE root_id=root.id AND item_key=key AND scenario_id=ANY(nodes) ORDER BY id DESC LIMIT 1;
  SELECT coalesce(jsonb_agg(jsonb_build_object('id',x.id,'scenario',x.scenario_id,'previous',x.previous_id,'evidence_id',x.evidence_id,'sha256',e.sha256,
   'mode',x.mode,'observed_on',x.observed_on,'uncertainty',x.uncertainty) ORDER BY x.id),'[]'::jsonb) INTO supports
   FROM finance_forecastitemsupport x JOIN core_evidence e ON e.id=x.evidence_id WHERE x.root_id=root.id AND x.item_key=key AND x.scenario_id=ANY(nodes);
  state=coalesce(v.uncertainty,original->>'uncertainty','unknown');
  IF state NOT IN ('unknown','disputed','uncertain','no_known_uncertainty') THEN RETURN NULL; END IF;
  active=CASE WHEN v.id IS NULL THEN true ELSE coalesce(psl_forecast_support_authorized(v),false) END;
  fresh=coalesce(v.id IS NOT NULL AND v.mode='renewed_support' AND v.scenario_id=s.id AND active,false);
  continued=(cardinality(nodes)>1 AND NOT (fresh AND state='no_known_uncertainty')) OR state IN ('disputed','uncertain') OR NOT active;
  output=output||jsonb_build_object(key,jsonb_build_object('original_scenario',root.id,'original_due',original->'original_due','first_captured_as_of',root.payload->'as_of',
   'original_evidence_id',proof.id,'original_evidence_sha256',proof.sha256,'carry_count',cardinality(nodes)-1,'history',history,'uncertainty',state,'reliability','unknown',
   'fresh_external_support',false,'renewed_supplied_support',fresh,'continued_review_required',continued,'support_authority_current',active,'support_id',v.id,'support_history',supports));
 END LOOP;
 RETURN output;
END $$;

CREATE FUNCTION psl_forecast_continuation_summary(items jsonb) RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
 SELECT CASE WHEN count(*)>0 THEN jsonb_build_object('label','continued_review_uncertainty','item_count',count(*),'reliability','unknown','review_is_fresh_support',false) ELSE 'null'::jsonb END
 FROM jsonb_array_elements(items) i WHERE i->'provenance'->'continued_review_required'='true'::jsonb;
$$;

CREATE FUNCTION psl_forecast_result_v2(sid bigint,m jsonb,r jsonb) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE p jsonb; expected_items jsonb; i jsonb; summary jsonb;
BEGIN
 p=psl_forecast_item_provenance(sid);
 SELECT payload->'items' INTO expected_items FROM finance_forecastscenario WHERE id=sid;
 IF p IS NULL OR m->>'implementation' IS DISTINCT FROM 'forecast/v2-continuation' OR r->>'implementation' IS DISTINCT FROM 'forecast/v2-continuation'
 OR m->'item_provenance' IS DISTINCT FROM p OR r->>'status' IS NULL OR r->>'status' NOT IN ('held','partial','ready')
 OR jsonb_typeof(r->'findings') IS DISTINCT FROM 'array' OR jsonb_typeof(r->'items') IS DISTINCT FROM 'array'
 OR jsonb_array_length(r->'items') IS DISTINCT FROM jsonb_array_length(expected_items)
 OR (SELECT count(DISTINCT value->>'key') FROM jsonb_array_elements(r->'items'))<>jsonb_array_length(expected_items)
 THEN RETURN false; END IF;
 FOR i IN SELECT value FROM jsonb_array_elements(r->'items') LOOP
  IF i->'provenance' IS DISTINCT FROM p->(i->>'key') OR (i-ARRAY['provenance','residual','matched']) IS DISTINCT FROM (SELECT value FROM jsonb_array_elements(expected_items) src WHERE src->>'key'=i->>'key') THEN RETURN false; END IF;
 END LOOP;
 summary=psl_forecast_continuation_summary(r->'items');
 IF r->'continuation' IS DISTINCT FROM summary OR (summary<>'null'::jsonb AND (r->>'status' NOT IN ('partial','held') OR jsonb_array_length(r->'findings')=0)) THEN RETURN false; END IF;
 RETURN true;
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;

CREATE FUNCTION psl_forecast_v2_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT coalesce(psl_forecast_result_v2(r.scenario_id,r.manifest,r.result)
 AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario n WHERE n.case_id=s.case_id AND n.reference=s.reference AND n.number>s.number)
 AND psl_schedules_grants(r.case_id,r.actor_id,ARRAY['finance.forecast.calculate'])
 AND psl_schedules_grants(r.case_id,s.actor_id,ARRAY['finance.forecast.capture']),false)
 FROM finance_forecastrun r JOIN finance_forecastscenario s ON s.id=r.scenario_id WHERE r.id=rid;
$$;

CREATE FUNCTION psl_forecast_review_authorized(r finance_forecastrun,rv finance_forecastreview) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT psl_schedules_grants(r.case_id,rv.actor_id,ARRAY['finance.read','finance.forecast.review'])
 AND psl_schedules_policy_current(r.case_id,(rv.authority->>'D05.role_principal_assignments')::bigint)
 AND psl_group_role_assigned((rv.authority->>'D05.role_principal_assignments')::bigint,rv.actor_id,rv.role,r.case_id)
 AND EXISTS(SELECT 1 FROM policy_configuration c JOIN policy_registeredreference rr ON rr.case_id=c.case_id
  AND rr.ref=c.envelope->'value'->>'artifact_ref' AND rr.version::text=c.envelope->'value'->>'artifact_version'
  CROSS JOIN LATERAL jsonb_array_elements(rr.content->'finance') rule JOIN finance_forecastscenario s ON s.id=r.scenario_id
  WHERE c.case_id=r.case_id AND c.component='D05.decision_action_matrix' AND psl_schedules_policy_current(r.case_id,c.id)
  AND rule=rv.authority->'finance_review_rule' AND rule->>'purpose'=CASE WHEN s.parent_id IS NULL THEN 'forecast' ELSE 'forecast_rollover' END
  AND rule->>'role'=rv.role AND rule->'actions' ? 'approve' AND (r.actor_id<>rv.actor_id OR rule->'allow_preparer_review'='true'::jsonb))
 AND EXISTS(SELECT 1 FROM policy_configuration c
  CROSS JOIN LATERAL jsonb_array_elements(psl_schedules_values(c.id)) method
  WHERE c.case_id=r.case_id AND c.component='D10.forecast_inclusion_rule_id' AND c.id::text=r.manifest->'method'->>'id'
  AND psl_schedules_policy_current(r.case_id,c.id) AND r.result->>'status'<>'held'
  AND (r.result->>'status'<>'partial' OR method->>'partial_publication'='label_partial'));
$$;

CREATE FUNCTION psl_forecast_v2_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE rid bigint; r finance_forecastrun; s finance_forecastscenario; rv finance_forecastreview; b finance_forecastbinding;
 expected_snapshot jsonb; method_id bigint;
BEGIN
 IF TG_TABLE_NAME='finance_forecastrun' THEN
  IF NOT EXISTS(SELECT 1 FROM finance_forecastscenario candidate WHERE candidate.id=NEW.scenario_id AND candidate.case_id=NEW.case_id) OR psl_forecast_result_v2(NEW.scenario_id,NEW.manifest,NEW.result) IS DISTINCT FROM true THEN RAISE EXCEPTION 'Exact forecast v2 item provenance and uncertainty required'; END IF;
  RETURN NEW;
 ELSIF TG_TABLE_NAME='finance_forecastreview' THEN
  IF NEW.verdict<>'approve' THEN RETURN NEW; END IF;rid=NEW.run_id;
 ELSIF TG_TABLE_NAME='finance_forecastbinding' THEN rid=NEW.run_id;
 ELSIF TG_TABLE_NAME='documents_publication' THEN
  SELECT * INTO b FROM finance_forecastbinding WHERE version_id=NEW.version_id;
  IF b.id IS NULL THEN RETURN NEW; END IF;rid=b.run_id;
 ELSIF TG_TABLE_NAME='workflows_factorywork' THEN
  IF NEW.definition<>'finance-forecast/v1' OR NEW.status<>'verified' THEN RETURN NEW; END IF;
  IF TG_OP='UPDATE' AND OLD.status='verified' THEN RETURN NEW; END IF;
  SELECT bb.* INTO b FROM finance_forecastbinding bb JOIN documents_publication pp ON pp.version_id=bb.version_id
   WHERE pp.factory_work_id=NEW.id AND pp.factory_source_id=NEW.source_head_id ORDER BY pp.id DESC LIMIT 1;rid=b.run_id;
 END IF;
 SELECT * INTO r FROM finance_forecastrun WHERE id=rid;
 SELECT * INTO s FROM finance_forecastscenario WHERE id=r.scenario_id;
 IF rid IS NULL OR psl_forecast_v2_current(rid) IS DISTINCT FROM true THEN RAISE EXCEPTION 'Recalculate legacy or stale forecast before new review, publication or verification'; END IF;
 method_id=(r.manifest->'method'->>'id')::bigint;
 expected_snapshot=jsonb_build_object('run_hash',r.sha256,'method',method_id,'implementation','forecast/v2-continuation',
  'review_kind',CASE WHEN r.result->'continuation'<>'null'::jsonb THEN 'continuation_of_uncertain_expectation' ELSE 'forecast_expectation' END,
  'item_provenance',r.manifest->'item_provenance','review_is_fresh_support',false);
 IF TG_TABLE_NAME='finance_forecastreview' THEN
  IF NEW.snapshot IS DISTINCT FROM expected_snapshot
  OR psl_forecast_review_authorized(r,NEW) IS DISTINCT FROM true
  OR psl_schedules_policy_current(r.case_id,method_id) IS DISTINCT FROM true
  OR EXISTS(SELECT 1 FROM jsonb_each(r.manifest->'item_provenance') x WHERE x.value->'support_authority_current'<>'true'::jsonb)
  THEN RAISE EXCEPTION 'Exact current forecast continuation review required'; END IF;
 ELSE
  SELECT * INTO rv FROM finance_forecastreview WHERE run_id=rid ORDER BY id DESC LIMIT 1;
  IF rv.id IS NULL OR rv.verdict<>'approve' OR rv.snapshot IS DISTINCT FROM expected_snapshot
  OR psl_forecast_review_authorized(r,rv) IS DISTINCT FROM true
  OR psl_schedules_policy_current(r.case_id,method_id) IS DISTINCT FROM true
  THEN RAISE EXCEPTION 'Exact current reviewed forecast continuation required'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_forecast_v2 BEFORE INSERT ON finance_forecastrun FOR EACH ROW EXECUTE FUNCTION psl_forecast_v2_guard();
CREATE TRIGGER psl_forecast_v2 BEFORE INSERT ON finance_forecastreview FOR EACH ROW EXECUTE FUNCTION psl_forecast_v2_guard();
CREATE TRIGGER psl_forecast_v2 BEFORE INSERT ON finance_forecastbinding FOR EACH ROW EXECUTE FUNCTION psl_forecast_v2_guard();
CREATE TRIGGER psl_forecast_v2 BEFORE INSERT ON documents_publication FOR EACH ROW EXECUTE FUNCTION psl_forecast_v2_guard();
CREATE TRIGGER psl_forecast_v2 BEFORE INSERT OR UPDATE ON workflows_factorywork FOR EACH ROW EXECUTE FUNCTION psl_forecast_v2_guard();
'''

GROUP_PREVIOUS = import_module('apps.documents.migrations.0026_group_forecast_business_date').PUBLICATION
GROUP_MARKER = " SELECT * INTO oracle FROM core_evidence WHERE id=(p->>'oracle_evidence_id')::bigint AND case_id=pc AND kind='forecast_group_oracle';"
GROUP_ADDITION = r'''
 SELECT projected || CASE WHEN summary='null'::jsonb THEN '{}'::jsonb ELSE jsonb_build_object('continuation',summary) END INTO projected
 FROM (SELECT psl_forecast_continuation_summary((SELECT jsonb_agg(value) FROM jsonb_array_elements(r.result->'items') i WHERE p->'rows' ? (i->>'key'))) AS summary) selected_uncertainty;
'''
assert GROUP_PREVIOUS.count(GROUP_MARKER)==1
GROUP_SQL = GROUP_PREVIOUS.replace(GROUP_MARKER,GROUP_ADDITION+GROUP_MARKER)
assert GROUP_SQL.replace(GROUP_ADDITION,'',1)==GROUP_PREVIOUS

REVERSE = GROUP_PREVIOUS + r'''
DROP TRIGGER psl_forecast_v2 ON finance_forecastrun;
DROP TRIGGER psl_forecast_v2 ON finance_forecastreview;
DROP TRIGGER psl_forecast_v2 ON finance_forecastbinding;
DROP TRIGGER psl_forecast_v2 ON documents_publication;
DROP TRIGGER psl_forecast_v2 ON workflows_factorywork;
DROP FUNCTION psl_forecast_v2_guard();
DROP FUNCTION psl_forecast_review_authorized(finance_forecastrun,finance_forecastreview);
DROP FUNCTION psl_forecast_v2_current(bigint);
DROP FUNCTION psl_forecast_result_v2(bigint,jsonb,jsonb);
DROP FUNCTION psl_forecast_continuation_summary(jsonb);
DROP FUNCTION psl_forecast_item_provenance(bigint);
DROP TRIGGER psl_forecast_support ON finance_forecastitemsupport;
DROP TRIGGER psl_immutable ON finance_forecastitemsupport;
DROP FUNCTION psl_forecast_support_guard();
DROP FUNCTION psl_forecast_support_authorized(finance_forecastitemsupport);
'''


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_append_only_history'),
        ('finance', '0069_collective_usage_intake'),
        ('documents','0031_template_current_claims'),
        ('workflows','0083_planning_source_correlation'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ForecastItemSupport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('item_key', models.CharField(max_length=100)),
                ('mode', models.CharField(max_length=30)),
                ('uncertainty', models.CharField(max_length=30)),
                ('observed_on', models.DateField(null=True)),
                ('role', models.CharField(max_length=50)),
                ('snapshot', models.JSONField()),
                ('authority', models.JSONField()),
                ('reason', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('case', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.case')),
                ('evidence', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.evidence')),
                ('previous', models.OneToOneField(null=True, on_delete=django.db.models.deletion.PROTECT, to='finance.forecastitemsupport')),
                ('root', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='item_support_history', to='finance.forecastscenario')),
                ('scenario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='item_support_declarations', to='finance.forecastscenario')),
            ],
            options={
                'constraints': [models.UniqueConstraint(condition=models.Q(('previous__isnull', True)), fields=('root', 'item_key'), name='forecast_item_support_origin')],
            },
        ),
        migrations.RunSQL(SQL+GROUP_SQL,REVERSE),
    ]
