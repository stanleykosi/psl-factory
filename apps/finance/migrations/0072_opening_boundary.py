"""Additive supplied opening boundary contract; no bank/date/approval policy."""
from django.db import migrations

SQL = r'''
CREATE FUNCTION psl_forecast_opening_boundary(pc uuid,p jsonb) RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE o jsonb; b jsonb; expected jsonb; declaration jsonb; proof core_evidence; support core_evidence;
 result jsonb='[]'::jsonb; eligible boolean; observed date; asof date; stamp text;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p->'openings') x WHERE x ? 'contract') THEN RETURN result; END IF;
 asof=(p->>'as_of')::date;
 IF to_char(asof,'YYYY-MM-DD') IS DISTINCT FROM p->>'as_of' THEN RETURN NULL; END IF;
 IF (SELECT count(*) FROM jsonb_array_elements(p->'openings'))<>(SELECT count(DISTINCT x->>'account') FROM jsonb_array_elements(p->'openings') x) THEN RETURN NULL; END IF;
 FOR o IN SELECT value FROM jsonb_array_elements(p->'openings') LOOP
  SELECT * INTO proof FROM core_evidence WHERE id=(o->>'evidence_id')::bigint AND case_id=pc AND kind='forecast_opening';
  IF proof.id IS NULL OR jsonb_typeof(o->'evidence_id') IS DISTINCT FROM 'number'
  OR o->>'account' !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'
  OR NOT p->'coverage'->'accounts' ? (o->>'account')
  OR NOT (o->'amount'='null'::jsonb OR (jsonb_typeof(o->'amount')='string' AND o->>'amount' ~ '^-?(0|[1-9][0-9]{0,23})(\.[0-9]{1,8})?$')) THEN RETURN NULL; END IF;
  observed=(o->>'observed_on')::date;
  IF to_char(observed,'YYYY-MM-DD') IS DISTINCT FROM o->>'observed_on' OR observed>asof THEN RETURN NULL; END IF;
  expected=o-'evidence_id';support=proof;
  IF o ? 'contract' THEN
   IF o->>'contract' IS DISTINCT FROM 'forecast-opening-boundary/v1' OR o->>'cutoff' IS DISTINCT FROM 'end_of_day'
   OR o->>'entity' IS DISTINCT FROM p->>'entity' OR o->>'currency' IS DISTINCT FROM p->>'currency' OR o->>'basis' IS DISTINCT FROM p->>'basis'
   OR NOT o ?& ARRAY['contract','entity','currency','basis','account','amount','observed_on','cutoff','source','source_version','boundary_at','evidence_id','boundary']
   OR o-ARRAY['contract','entity','currency','basis','account','amount','observed_on','cutoff','source','source_version','boundary_at','evidence_id','boundary']<>'{}'::jsonb
   OR jsonb_typeof(o->'source') IS DISTINCT FROM 'string' OR o->>'source' !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'
   OR jsonb_typeof(o->'source_version') IS DISTINCT FROM 'string' OR o->>'source_version' !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$' THEN RETURN NULL; END IF;
   b=o->'boundary';
   IF jsonb_typeof(b) IS DISTINCT FROM 'object' OR NOT b ?& ARRAY['as_of','opening_at','status']
   OR b-ARRAY['as_of','opening_at','status','evidence_id']<>'{}'::jsonb
   OR b->>'status' IS NULL OR b->>'status' NOT IN ('reconciled','unreconciled')
   OR to_char((b->>'as_of')::date,'YYYY-MM-DD') IS DISTINCT FROM b->>'as_of' THEN RETURN NULL; END IF;
   FOREACH stamp IN ARRAY ARRAY[o->>'boundary_at',b->>'opening_at'] LOOP
    IF stamp IS NULL OR stamp !~ '^\d{4}-\d{2}-\d{2}T00:00:00[+-]\d{2}:\d{2}$'
    OR to_char(left(stamp,10)::date,'YYYY-MM-DD')<>left(stamp,10)
    OR substring(stamp,21,2)::integer>23 OR right(stamp,2)::integer>59 THEN RETURN NULL; END IF;
   END LOOP;
   IF b ? 'evidence_id' THEN
    expected=expected-ARRAY['contract','boundary'];
    SELECT * INTO support FROM core_evidence WHERE id=(b->>'evidence_id')::bigint AND case_id=pc AND kind='forecast_opening';
    declaration=(b-'evidence_id')||expected||jsonb_build_object('snapshot_evidence_id',proof.id,'snapshot_sha256',proof.sha256);
    IF support.id IS NULL OR jsonb_typeof(b->'evidence_id') IS DISTINCT FROM 'number' OR support.body::jsonb IS DISTINCT FROM declaration THEN RETURN NULL; END IF;
   END IF;
   eligible=(b->>'status'='reconciled' AND b->>'as_of'=p->>'as_of' AND observed+1=asof
      AND o->>'boundary_at'=b->>'opening_at' AND left(b->>'opening_at',10)=p->>'as_of');
  ELSE
   IF NOT o ?& ARRAY['account','amount','observed_on','cutoff','evidence_id']
   OR o-ARRAY['account','amount','observed_on','cutoff','evidence_id']<>'{}'::jsonb
   OR o->>'cutoff' IS DISTINCT FROM 'start_of_day' THEN RETURN NULL; END IF;
   eligible=observed=asof;
  END IF;
  IF proof.body::jsonb IS DISTINCT FROM expected THEN RETURN NULL; END IF;
  result=result||jsonb_build_array(o||jsonb_build_object('snapshot_sha256',proof.sha256,'boundary_sha256',support.sha256,
    'eligible',eligible IS TRUE,'verification','supplied_only_not_bank_authenticated'));
 END LOOP;
 RETURN result;
EXCEPTION WHEN OTHERS THEN RETURN NULL;
END $$;

CREATE FUNCTION psl_forecast_opening_boundary_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE s finance_forecastscenario; sources jsonb; amount numeric; unknown boolean; max_age integer;
BEGIN
 IF TG_TABLE_NAME='finance_forecastscenario' THEN
  sources=psl_forecast_opening_boundary(NEW.case_id,NEW.payload);
  IF sources IS NULL THEN RAISE EXCEPTION 'Exact supplied opening snapshot and boundary declaration required'; END IF;
  RETURN NEW;
 END IF;
 SELECT * INTO s FROM finance_forecastscenario WHERE id=NEW.scenario_id AND case_id=NEW.case_id;
 sources=psl_forecast_opening_boundary(s.case_id,s.payload);
 IF sources IS NULL THEN RAISE EXCEPTION 'Exact supplied opening snapshot and boundary declaration required'; END IF;
 IF sources='[]'::jsonb THEN RETURN NEW; END IF;
 IF NEW.manifest->>'opening_contract' IS DISTINCT FROM 'forecast-opening-boundary/v1'
 OR NEW.result->>'opening_contract' IS DISTINCT FROM 'forecast-opening-boundary/v1'
 OR NEW.manifest->'opening_provenance' IS DISTINCT FROM sources OR NEW.result->'opening_provenance' IS DISTINCT FROM sources
 THEN RAISE EXCEPTION 'Exact opening boundary provenance required'; END IF;
 SELECT coalesce(bool_or(x->'eligible'<>'true'::jsonb OR x->'amount'='null'::jsonb),true),sum((x->>'amount')::numeric)
 INTO unknown,amount FROM jsonb_array_elements(sources) x;
 unknown=unknown OR (SELECT count(*) FROM jsonb_array_elements(sources))<>jsonb_array_length(s.payload->'coverage'->'accounts');
 IF jsonb_array_length(NEW.result->'periods')<1 OR NEW.result#>'{periods,0,opening}' IS NULL
 OR (unknown AND (NEW.result#>'{periods,0,opening}' IS DISTINCT FROM 'null'::jsonb OR NEW.result->>'status'='ready'))
 OR (unknown AND EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.result->'periods') period WHERE period->'opening' IS DISTINCT FROM 'null'::jsonb OR period->'closing' IS DISTINCT FROM 'null'::jsonb))
 OR (NOT unknown AND ((NEW.result#>>'{periods,0,opening}')::numeric IS DISTINCT FROM amount))
 THEN RAISE EXCEPTION 'Unknown or unreconciled opening cannot become a known balance'; END IF;
 SELECT (value->>'opening_max_age_days')::integer INTO max_age FROM jsonb_array_elements(psl_schedules_values((NEW.manifest#>>'{method,id}')::bigint));
 IF NEW.result->>'status'='ready' AND EXISTS(SELECT 1 FROM jsonb_array_elements(sources) o WHERE (s.payload->>'as_of')::date-(o->>'observed_on')::date>max_age)
 THEN RAISE EXCEPTION 'Original opening source date exceeds configured freshness'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_forecast_opening_boundary BEFORE INSERT ON finance_forecastscenario FOR EACH ROW EXECUTE FUNCTION psl_forecast_opening_boundary_guard();
CREATE TRIGGER psl_forecast_opening_boundary BEFORE INSERT ON finance_forecastrun FOR EACH ROW EXECUTE FUNCTION psl_forecast_opening_boundary_guard();
'''
REVERSE = r'''
DROP TRIGGER psl_forecast_opening_boundary ON finance_forecastrun;
DROP TRIGGER psl_forecast_opening_boundary ON finance_forecastscenario;
DROP FUNCTION psl_forecast_opening_boundary_guard();
DROP FUNCTION psl_forecast_opening_boundary(uuid,jsonb);
'''
class Migration(migrations.Migration):
    dependencies=[('finance','0071_draft_generation')]
    operations=[migrations.RunSQL(SQL,REVERSE)]
