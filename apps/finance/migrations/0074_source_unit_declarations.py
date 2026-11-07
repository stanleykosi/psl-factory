"""New source declarations only. Historical NULL rows and results are not rewritten."""
from django.db import migrations, models

SQL = r'''
CREATE FUNCTION psl_source_units(cid uuid,bid bigint,v jsonb) RETURNS text LANGUAGE plpgsql STABLE AS $$
DECLARE b finance_financialimport; d jsonb; p jsonb; e core_evidence; identity text; units text[]='{}'; feeds text[]='{}';
BEGIN
 SELECT * INTO b FROM finance_financialimport WHERE id=bid AND case_id=cid;
 IF NOT FOUND OR v IS NULL OR jsonb_typeof(v)<>'object'
 OR NOT v ?& ARRAY['schema','batch','input_key','declarations']
 OR v-ARRAY['schema','batch','input_key','declarations']<>'{}'::jsonb
 OR v->>'schema' IS DISTINCT FROM 'finance-source-units/v1'
 OR v->'batch' IS DISTINCT FROM jsonb_build_object('id',b.id,'sha256',b.source_sha256)
 OR jsonb_typeof(v->'declarations')<>'array' THEN RETURN 'invalid'; END IF;
 IF jsonb_array_length(v->'declarations')>20 THEN RETURN 'invalid'; END IF;
 IF jsonb_array_length(v->'declarations')=0 THEN
   IF v->'input_key'='null'::jsonb THEN RETURN 'unknown'; ELSE RETURN 'invalid'; END IF;
 END IF;
 IF jsonb_typeof(v->'input_key')<>'string' OR v->>'input_key' !~ '^[A-Za-z0-9_.:-]{1,100}$' THEN RETURN 'invalid'; END IF;
 FOR d IN SELECT value FROM jsonb_array_elements(v->'declarations') LOOP
  IF jsonb_typeof(d)<>'object' OR NOT d ?& ARRAY['feed','unit','evidence']
  OR d-ARRAY['feed','unit','evidence']<>'{}'::jsonb
  OR jsonb_typeof(d->'feed')<>'string' OR d->>'feed' !~ '^[A-Za-z0-9_.:-]{1,100}$'
  OR d->>'feed'=ANY(feeds) OR coalesce(d->>'unit','') NOT IN ('major_currency','thousands_currency','unknown')
  THEN RETURN 'invalid'; END IF;
  feeds=array_append(feeds,d->>'feed');units=array_append(units,d->>'unit');p=d->'evidence';
  IF jsonb_typeof(p)<>'object' OR NOT p ?& ARRAY['id','version','sha256']
  OR p-ARRAY['id','version','sha256']<>'{}'::jsonb
  OR jsonb_typeof(p->'id')<>'number' OR p->>'id' !~ '^[1-9][0-9]*$'
  OR jsonb_typeof(p->'version')<>'number' OR p->>'version' !~ '^[1-9][0-9]*$'
  OR jsonb_typeof(p->'sha256')<>'string' OR p->>'sha256' !~ '^[a-f0-9]{64}$' THEN RETURN 'invalid'; END IF;
  SELECT * INTO e FROM core_evidence WHERE case_id=cid AND kind='finance_source_unit'
   AND id=(p->>'id')::bigint AND version=(p->>'version')::integer AND sha256=p->>'sha256';
  IF NOT FOUND THEN RETURN 'invalid'; END IF;
  identity='source-unit:'||jsonb_build_array(bid,v->>'input_key',d->>'feed')::text;
  IF e.source<>identity OR EXISTS(SELECT 1 FROM core_evidence WHERE case_id=cid AND kind='finance_source_unit' AND source=identity AND version>e.version)
  OR encode(sha256(convert_to(e.body,'UTF8')),'hex')<>e.sha256
  OR e.body::jsonb IS DISTINCT FROM jsonb_build_object('schema','finance-source-unit-assertion/v1','batch_id',bid,
    'source_sha256',b.source_sha256,'input_key',v->>'input_key','feed',d->>'feed','unit',d->>'unit') THEN RETURN 'invalid'; END IF;
 END LOOP;
 IF 'major_currency'=ANY(units) AND 'thousands_currency'=ANY(units) THEN RETURN 'conflict'; END IF;
 IF 'unknown'=ANY(units) THEN RETURN 'unknown'; END IF;
 IF 'thousands_currency'=ANY(units) THEN RETURN 'unsupported'; END IF;
 RETURN 'declared_major_currency';
EXCEPTION WHEN OTHERS THEN RETURN 'invalid';
END $$;
CREATE FUNCTION psl_source_units_insert() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 -- Serialize against concurrent source capture/evidence capture on the native case lock.
 PERFORM 1 FROM core_case WHERE id=NEW.case_id FOR UPDATE;
 IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'Source units require READ COMMITTED'; END IF;
 IF psl_source_units(NEW.case_id,NEW.batch_id,NEW.unit_declaration)='invalid' THEN
 RAISE EXCEPTION 'Exact immutable source-unit envelope/evidence required for new sources'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_source_units_insert BEFORE INSERT ON finance_financesource FOR EACH ROW EXECUTE FUNCTION psl_source_units_insert();
CREATE FUNCTION psl_source_units_run_insert() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE s finance_financesource; status text;
BEGIN
 PERFORM 1 FROM core_case WHERE id=NEW.case_id FOR UPDATE;
 IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'Source units require READ COMMITTED'; END IF;
 SELECT * INTO s FROM finance_financesource WHERE id=NEW.source_id AND case_id=NEW.case_id;
 IF NOT FOUND OR s.id<>(SELECT max(id) FROM finance_financesource WHERE batch_id=s.batch_id) THEN RAISE EXCEPTION 'Current exact source required'; END IF;
 IF s.unit_declaration IS NULL THEN
  IF NEW.snapshot ? 'source_units' THEN RAISE EXCEPTION 'Legacy source cannot claim an explicit unit declaration'; END IF;
  RETURN NEW;
 END IF;
 status=psl_source_units(s.case_id,s.batch_id,s.unit_declaration);
 IF status<>'declared_major_currency' OR (NEW.kind IN ('mapping','allocation','formula') AND NEW.snapshot->'source_units' IS DISTINCT FROM
 jsonb_build_object('status',status,'declaration',s.unit_declaration,'findings','[]'::jsonb))
 THEN RAISE EXCEPTION 'Source unit unknown/conflict/stale or exact declaration snapshot absent; no numeric preview'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_source_units_run_insert BEFORE INSERT ON finance_financerun FOR EACH ROW EXECUTE FUNCTION psl_source_units_run_insert();
'''

class Migration(migrations.Migration):
    dependencies=[('finance','0073_workbook_reference')]
    operations=[migrations.AddField(model_name='financesource',name='unit_declaration',field=models.JSONField(null=True,editable=False)),
                migrations.RunSQL(SQL)]
