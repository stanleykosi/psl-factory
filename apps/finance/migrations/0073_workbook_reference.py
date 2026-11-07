"""Supplied workbook references only; no financial rule or native Excel execution."""
from django.db import migrations

SQL = r'''
CREATE FUNCTION psl_workbook_pin(p jsonb) RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
 SELECT coalesce(jsonb_typeof(p)='object' AND p ?& ARRAY['id','version','sha256']
 AND p-ARRAY['id','version','sha256']='{}'::jsonb
 AND jsonb_typeof(p->'id')='number' AND p->>'id' ~ '^[1-9][0-9]*$'
 AND jsonb_typeof(p->'version')='number' AND p->>'version' ~ '^[1-9][0-9]*$'
 AND jsonb_typeof(p->'sha256')='string' AND p->>'sha256' ~ '^[a-f0-9]{64}$',false);
$$;
CREATE FUNCTION psl_workbook_source(cid uuid,p jsonb,k text) RETURNS jsonb LANGUAGE sql STABLE AS $$
 SELECT e.body::jsonb FROM core_evidence e WHERE psl_workbook_pin(p) AND e.case_id=cid
 AND e.id=(p->>'id')::bigint AND e.version=(p->>'version')::integer AND e.sha256=p->>'sha256'
 AND e.kind='forecast_workbook_'||k;
$$;
CREATE FUNCTION psl_workbook_money(a jsonb,b jsonb) RETURNS boolean LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
 IF a='null'::jsonb AND b='null'::jsonb THEN RETURN true; END IF;
 IF jsonb_typeof(a) IS DISTINCT FROM 'string' OR jsonb_typeof(b) IS DISTINCT FROM 'string'
 OR a#>>'{}' !~ '^-?(0|[1-9][0-9]{0,23})(\.[0-9]{1,8})?$'
 OR b#>>'{}' !~ '^-?(0|[1-9][0-9]{0,23})(\.[0-9]{1,8})?$' THEN RETURN false; END IF;
 RETURN (a#>>'{}')::numeric=(b#>>'{}')::numeric;
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;
CREATE FUNCTION psl_workbook_native_inputs(sid bigint,periods jsonb) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE s finance_forecastscenario; o jsonb; item jsonb; p jsonb; sources jsonb; amount numeric=0; total numeric;
 unknown boolean=false; residual numeric; dir text; root bigint; invalid boolean; actual_row finance_forecastactual;
BEGIN
 SELECT * INTO s FROM finance_forecastscenario WHERE id=sid;root=coalesce(s.root_id,s.id);
 sources=psl_forecast_opening_boundary(s.case_id,s.payload);
 IF sources IS NULL THEN RETURN false; END IF;
 IF jsonb_array_length(s.payload->'openings')<>jsonb_array_length(s.payload->'coverage'->'accounts') THEN unknown=true; END IF;
 FOR o IN SELECT value FROM jsonb_array_elements(s.payload->'openings') LOOP
  IF o->'amount'='null'::jsonb OR (o ? 'contract' AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(sources) x WHERE x->'account'=o->'account' AND x->'eligible'='true'::jsonb))
  OR (NOT o ? 'contract' AND o->'observed_on' IS DISTINCT FROM s.payload->'as_of') THEN unknown=true; END IF;
  amount=amount+coalesce((o->>'amount')::numeric,0);
 END LOOP;
 IF psl_workbook_money(periods->0->'opening',CASE WHEN unknown THEN 'null'::jsonb ELSE to_jsonb(amount::text) END) IS DISTINCT FROM true THEN RETURN false; END IF;
 SELECT EXISTS(SELECT 1 FROM finance_forecastmatch m JOIN finance_forecastactual a ON a.id=m.actual_id
  WHERE m.case_id=s.case_id AND NOT EXISTS(SELECT 1 FROM finance_forecastmatchreversal r WHERE r.match_id=m.id)
  AND NOT ((a.lot_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_cashreversal cr WHERE cr.lot_id=a.lot_id))
   OR (a.lot_id IS NULL AND EXISTS(SELECT 1 FROM finance_forecastactualverification av WHERE av.actual_id=a.id)))) INTO invalid;
 FOR p IN SELECT value FROM jsonb_array_elements(periods) LOOP
  FOREACH dir IN ARRAY ARRAY['inflow','outflow'] LOOP
   total=0;unknown=invalid;
   FOR item IN SELECT value FROM jsonb_array_elements(s.payload->'items') LOOP
    IF (item->>'kind'='outflow')<>(dir='outflow') THEN CONTINUE; END IF;
    IF item->>'expected_on' IS NULL OR NOT s.payload->'months' ? left(item->>'expected_on',7) THEN unknown=true;CONTINUE; END IF;
    IF left(item->>'expected_on',7)<>p->>'month' THEN CONTINUE; END IF;
    IF item->'amount'='null'::jsonb THEN unknown=true;CONTINUE; END IF;
    SELECT (item->>'amount')::numeric-coalesce(sum(m.amount),0) INTO residual FROM finance_forecastmatch m
     WHERE m.root_id=root AND m.item_key=item->>'key' AND NOT EXISTS(SELECT 1 FROM finance_forecastmatchreversal mr WHERE mr.match_id=m.id);
    IF residual<0 THEN RETURN false; END IF;total=total+residual;
   END LOOP;
   FOR actual_row IN SELECT * FROM finance_forecastactual a WHERE a.case_id=s.case_id AND a.payload->>'direction'=dir
    AND a.payload->'entity'=s.payload->'entity' AND a.payload->'currency'=s.payload->'currency' AND a.payload->'basis'=s.payload->'basis'
    AND s.payload->'coverage'->'accounts' ? (a.payload->>'account') AND a.payload->>'occurred_on'>=s.payload->>'as_of'
    AND left(a.payload->>'occurred_on',7)=p->>'month'
    AND ((a.lot_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_cashreversal cr WHERE cr.lot_id=a.lot_id))
     OR (a.lot_id IS NULL AND EXISTS(SELECT 1 FROM finance_forecastactualverification av WHERE av.actual_id=a.id))) LOOP
    total=total+coalesce((actual_row.payload->>'amount')::numeric,0);
   END LOOP;
   IF psl_workbook_money(p->dir,CASE WHEN unknown THEN 'null'::jsonb ELSE to_jsonb(total::text) END) IS DISTINCT FROM true THEN RETURN false; END IF;
  END LOOP;
 END LOOP;
 RETURN true;
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;

CREATE FUNCTION psl_workbook_equivalent(sid bigint,m jsonb,r jsonb) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE s finance_forecastscenario; selected jsonb; snap jsonb; contract jsonb; oracle jsonb;
 policy jsonb; scope jsonb; expected jsonb; x jsonb; y jsonb; z jsonb; p jsonb; cell jsonb;
 role text; n integer; i integer; addresses text[]='{}'; identity text; prior jsonb;
BEGIN
 SELECT * INTO s FROM finance_forecastscenario WHERE id=sid;
 selected=s.payload->'workbook_chain';
 snap=psl_workbook_source(s.case_id,selected->'snapshot','snapshot');
 contract=psl_workbook_source(s.case_id,selected->'contract','contract');
 oracle=psl_workbook_source(s.case_id,selected->'oracle','oracle');
 SELECT value->'workbook_reference' INTO policy FROM jsonb_array_elements(psl_schedules_values((m#>>'{method,id}')::bigint));
 scope=contract->'scope'; n=jsonb_array_length(s.payload->'months');
 IF snap IS NULL OR contract IS NULL OR oracle IS NULL OR policy IS NULL
 OR psl_workbook_native_inputs(sid,r->'periods') IS DISTINCT FROM true
 OR psl_schedules_policy_current(s.case_id,(m#>>'{method,id}')::bigint) IS DISTINCT FROM true
 OR policy->'contract' IS DISTINCT FROM selected->'contract' OR policy->'oracle' IS DISTINCT FROM selected->'oracle'
 OR contract->'oracle' IS DISTINCT FROM selected->'oracle'
 OR snap->>'protocol' IS DISTINCT FROM 'forecast-workbook-chain-snapshot/v1'
 OR contract->>'protocol' IS DISTINCT FROM 'forecast-workbook-reference-contract/v1'
 OR contract->>'implementation' IS DISTINCT FROM 'monthly_cash_chain_v1'
 OR oracle->>'protocol' IS DISTINCT FROM 'forecast-workbook-oracle/v1'
 OR snap->'scope' IS DISTINCT FROM scope OR oracle->'scope' IS DISTINCT FROM scope
 OR scope->>'scenario' IS DISTINCT FROM s.reference OR scope->>'revision' IS DISTINCT FROM s.number::text
 OR scope->'unit' IS DISTINCT FROM selected->'unit'
 OR scope-ARRAY['workbook','workbook_version','scenario','revision','unit'] IS DISTINCT FROM
 jsonb_build_object('entity',s.payload->'entity','currency',s.payload->'currency','basis',s.payload->'basis','as_of',s.payload->'as_of','months',s.payload->'months')
 OR scope->>'workbook' IS NULL OR scope->>'workbook_version' IS NULL
 OR n NOT BETWEEN 1 AND 24 OR jsonb_array_length(snap->'months') IS DISTINCT FROM n
 OR jsonb_array_length(contract->'months') IS DISTINCT FROM n OR jsonb_array_length(oracle->'months') IS DISTINCT FROM n
 OR jsonb_array_length(r->'periods') IS DISTINCT FROM n
 OR jsonb_array_length(contract->'edges') IS DISTINCT FROM n-1 OR snap->'edges' IS DISTINCT FROM contract->'edges'
 OR (snap->>'observed_on')::date>(s.payload->>'as_of')::date
 OR (snap->>'extracted_on')::date<(snap->>'observed_on')::date
 OR (snap->>'extracted_on')::date>psl_group_forecast_business_date(clock_timestamp())
 OR (s.payload->>'as_of')::date-(snap->>'observed_on')::date>(policy->>'snapshot_max_age_days')::integer
 OR policy->>'snapshot_max_age_days' IS NULL
 THEN RETURN false; END IF;
 FOR i IN 0..n-1 LOOP
  x=snap->'months'->i;y=contract->'months'->i;z=oracle->'months'->i;p=r->'periods'->i;
  IF x->'month' IS DISTINCT FROM s.payload->'months'->i OR y->'month' IS DISTINCT FROM x->'month'
  OR z->'month' IS DISTINCT FROM x->'month' OR p->'month' IS DISTINCT FROM x->'month'
  OR x->'cells' IS DISTINCT FROM y->'cells'
  OR NOT x->'cells' ?& ARRAY['opening','inflow','outflow','closing']
  OR (x->'cells')-ARRAY['opening','inflow','outflow','closing']<>'{}'::jsonb
  THEN RETURN false; END IF;
  FOREACH role IN ARRAY ARRAY['opening','inflow','outflow','closing'] LOOP
   cell=x->'cells'->role;
   IF jsonb_typeof(cell) IS DISTINCT FROM 'object' OR NOT cell ?& ARRAY['sheet','address']
   OR cell-ARRAY['sheet','address']<>'{}'::jsonb OR jsonb_typeof(cell->'sheet') IS DISTINCT FROM 'string' OR jsonb_typeof(cell->'address') IS DISTINCT FROM 'string' OR length(cell->>'sheet') NOT BETWEEN 1 AND 80
   OR cell->>'address' !~ '^[A-Z]{1,3}[1-9][0-9]{0,6}$' THEN RETURN false; END IF;
   identity=cell::text;
   IF identity=ANY(addresses) THEN RETURN false; END IF;addresses=array_append(addresses,identity);
   IF psl_workbook_money(x->'literals'->role,z->'literals'->role) IS DISTINCT FROM true
   OR psl_workbook_money(x->'literals'->role,p->role) IS DISTINCT FROM true THEN RETURN false; END IF;
  END LOOP;
  IF i>0 THEN
   expected=jsonb_build_object('source',jsonb_build_object('month',s.payload->'months'->(i-1),'cell',contract->'months'->(i-1)->'cells'->'closing'),
    'target',jsonb_build_object('month',x->'month','cell',x->'cells'->'opening'));
   IF contract->'edges'->(i-1) IS DISTINCT FROM expected OR psl_workbook_money(prior,x->'literals'->'opening') IS DISTINCT FROM true THEN RETURN false; END IF;
  END IF;
  IF x->'literals'->'opening'='null'::jsonb OR x->'literals'->'inflow'='null'::jsonb OR x->'literals'->'outflow'='null'::jsonb THEN
   IF x->'literals'->'closing' IS DISTINCT FROM 'null'::jsonb THEN RETURN false; END IF;
  ELSIF (x#>>'{literals,closing}')::numeric IS DISTINCT FROM
   (x#>>'{literals,opening}')::numeric+(x#>>'{literals,inflow}')::numeric-(x#>>'{literals,outflow}')::numeric THEN RETURN false; END IF;
  prior=x->'literals'->'closing';
 END LOOP;
 RETURN true;
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;

CREATE FUNCTION psl_workbook_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE s finance_forecastscenario; p jsonb; pin jsonb; k text; comparison jsonb; rid bigint; r finance_forecastrun;
BEGIN
 IF TG_TABLE_NAME='finance_forecastscenario' THEN
  IF NOT NEW.payload ? 'workbook_chain' THEN RETURN NEW; END IF;
  p=NEW.payload->'workbook_chain';
  IF jsonb_typeof(p) IS DISTINCT FROM 'object' OR NOT p ?& ARRAY['snapshot','contract','oracle','unit']
  OR p-ARRAY['snapshot','contract','oracle','unit']<>'{}'::jsonb
  OR jsonb_typeof(p->'unit') IS DISTINCT FROM 'string' OR p->>'unit' !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'
  OR NOT EXISTS(SELECT 1 FROM core_evidence e WHERE e.id=NEW.evidence_id AND e.case_id=NEW.case_id AND e.kind='forecast_input' AND e.body::jsonb=NEW.payload)
  OR psl_schedules_grants(NEW.case_id,NEW.actor_id,ARRAY['finance.read','finance.forecast.capture']) IS DISTINCT FROM true
  THEN RAISE EXCEPTION 'Exact authorized workbook selection required'; END IF;
  FOREACH k IN ARRAY ARRAY['snapshot','contract','oracle'] LOOP
   pin=p->k;
   IF pin<>'null'::jsonb AND NOT psl_workbook_pin(pin) THEN RAISE EXCEPTION 'Exact nullable workbook source pin required'; END IF;
  END LOOP;
  RETURN NEW;
 END IF;
 IF TG_TABLE_NAME='finance_forecastrun' THEN
  SELECT * INTO s FROM finance_forecastscenario WHERE id=NEW.scenario_id AND case_id=NEW.case_id;
  IF NOT s.payload ? 'workbook_chain' THEN
   IF NEW.result ? 'workbook_comparison' OR NEW.manifest ? 'workbook_comparison' THEN RAISE EXCEPTION 'Unbound legacy forecast cannot claim workbook equivalence'; END IF;
   RETURN NEW;
  END IF;
  comparison=NEW.result->'workbook_comparison';
  IF comparison IS NULL OR comparison IS DISTINCT FROM NEW.manifest->'workbook_comparison'
  OR comparison->'selection' IS DISTINCT FROM s.payload->'workbook_chain'
  OR comparison->>'protocol' IS DISTINCT FROM 'forecast-workbook-comparison/v1'
  OR comparison->>'verification' IS DISTINCT FROM 'supplied_snapshot_only_not_native_workbook_authenticated'
  OR psl_schedules_grants(NEW.case_id,NEW.actor_id,ARRAY['finance.read','finance.forecast.calculate']) IS DISTINCT FROM true
  THEN RAISE EXCEPTION 'Exact supplied workbook comparison manifest required'; END IF;
  IF comparison->>'status'='equivalent' THEN
   IF (NEW.result->>'status'='ready' AND EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.result->'periods') period WHERE period->'closing'='null'::jsonb))
   OR comparison->'findings' IS DISTINCT FROM '[]'::jsonb
   OR psl_workbook_equivalent(s.id,NEW.manifest,NEW.result) IS DISTINCT FROM true
   OR comparison->'sources' IS DISTINCT FROM ((s.payload->'workbook_chain')-'unit')
   THEN RAISE EXCEPTION 'Exact supplied cell roles, carry references and numerical oracle required'; END IF;
  ELSIF comparison->>'status'='held' THEN
   IF NEW.result->>'status' IS DISTINCT FROM 'held' OR jsonb_array_length(comparison->'findings')<1
   OR EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.result->'periods') WITH ORDINALITY q(v,n)
     WHERE v->'closing' IS DISTINCT FROM 'null'::jsonb OR (n>1 AND v->'opening' IS DISTINCT FROM 'null'::jsonb))
   THEN RAISE EXCEPTION 'Held workbook chain cannot publish generated fallback balances'; END IF;
  ELSE RAISE EXCEPTION 'Explicit workbook equivalence or held status required'; END IF;
  RETURN NEW;
 END IF;
 IF TG_TABLE_NAME='finance_forecastreview' THEN
  IF NEW.verdict<>'approve' THEN RETURN NEW; END IF;rid=NEW.run_id;
 ELSIF TG_TABLE_NAME='finance_forecastbinding' THEN rid=NEW.run_id;
 ELSIF TG_TABLE_NAME='documents_publication' THEN
  SELECT run_id INTO rid FROM finance_forecastbinding WHERE version_id=NEW.version_id;
 ELSIF TG_TABLE_NAME='workflows_factorywork' THEN
  IF NEW.definition<>'finance-forecast/v1' OR NEW.status<>'verified' THEN RETURN NEW; END IF;
  IF TG_OP='UPDATE' AND OLD.status='verified' THEN RETURN NEW; END IF;
  SELECT b.run_id INTO rid FROM finance_forecastbinding b JOIN documents_publication pub ON pub.version_id=b.version_id
   WHERE pub.factory_work_id=NEW.id AND pub.factory_source_id=NEW.source_head_id ORDER BY pub.id DESC LIMIT 1;
 END IF;
 SELECT * INTO r FROM finance_forecastrun WHERE id=rid;
 SELECT * INTO s FROM finance_forecastscenario WHERE id=r.scenario_id;
 IF s.payload ? 'workbook_chain' AND (r.result#>>'{workbook_comparison,status}' IS DISTINCT FROM 'equivalent'
 OR psl_workbook_equivalent(s.id,r.manifest,r.result) IS DISTINCT FROM true
 OR s.payload->>'as_of' IS DISTINCT FROM psl_group_forecast_business_date(clock_timestamp())::text)
 THEN RAISE EXCEPTION 'Current exact supplied workbook equivalence required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_workbook BEFORE INSERT ON finance_forecastscenario FOR EACH ROW EXECUTE FUNCTION psl_workbook_guard();
CREATE TRIGGER psl_workbook BEFORE INSERT ON finance_forecastrun FOR EACH ROW EXECUTE FUNCTION psl_workbook_guard();
CREATE TRIGGER psl_workbook BEFORE INSERT ON finance_forecastreview FOR EACH ROW EXECUTE FUNCTION psl_workbook_guard();
CREATE TRIGGER psl_workbook BEFORE INSERT ON finance_forecastbinding FOR EACH ROW EXECUTE FUNCTION psl_workbook_guard();
CREATE TRIGGER psl_workbook BEFORE INSERT ON documents_publication FOR EACH ROW EXECUTE FUNCTION psl_workbook_guard();
CREATE TRIGGER psl_workbook BEFORE INSERT OR UPDATE ON workflows_factorywork FOR EACH ROW EXECUTE FUNCTION psl_workbook_guard();
'''

# Change only the two exact forecast inventory subqueries in the installed current
# guard. Never import/reconstruct historical shared SQL (which has other owners).
OLD = "UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'items') item) exact_sources"
NEW = "UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'items') item UNION SELECT (pin.value->>'id')::bigint FROM jsonb_each(coalesce(s.payload->'workbook_chain','{}'::jsonb)-'unit') pin WHERE pin.value<>'null'::jsonb) exact_sources"

def replace_inventory(schema_editor, old, new):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT pg_get_functiondef('psl_factory_identity()'::regprocedure)")
        definition = cursor.fetchone()[0]
        if definition.count(old) != 2 or new in definition:
            raise RuntimeError('Exact two predecessor forecast source inventory clauses required')
        cursor.execute(definition.replace(old, new))

def forwards(apps, schema_editor): replace_inventory(schema_editor, OLD, NEW)
def backwards(apps, schema_editor): replace_inventory(schema_editor, NEW, OLD)

REVERSE = '\n'.join('DROP TRIGGER psl_workbook ON '+table+';' for table in [
    'finance_forecastscenario','finance_forecastrun','finance_forecastreview','finance_forecastbinding','documents_publication','workflows_factorywork']) + '''
DROP FUNCTION psl_workbook_guard();
DROP FUNCTION psl_workbook_equivalent(bigint,jsonb,jsonb);
DROP FUNCTION psl_workbook_native_inputs(bigint,jsonb);
DROP FUNCTION psl_workbook_money(jsonb,jsonb);
DROP FUNCTION psl_workbook_source(uuid,jsonb,text);
DROP FUNCTION psl_workbook_pin(jsonb);
'''
class Migration(migrations.Migration):
    dependencies = [('finance', '0072_opening_boundary'), ('workflows', '0085_incident_report_claims'), ('pmo', '0049_change_closure_signature_binding')]
    operations = [migrations.RunSQL(SQL, REVERSE), migrations.RunPython(forwards, backwards)]
