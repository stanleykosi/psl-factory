"""Add exact planning correlation currentness without changing independent intake."""
import hashlib
from django.db import migrations

PARENT_SHA256 = '350df5edb6333db71e4edcf72bf8dd0b65ba1bc2d04c8a81b4af77ead58c63f3'
PARENT_BODY_SHA256 = '71d4d6d3e2a79b514763a2eff166748cf8cdd344e128e5f9dd476dd28bdb4df5'
PARENT_SQL = r'''CREATE OR REPLACE FUNCTION psl_engagement_planning_inputs_current(eid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM core_evidence e WHERE e.id=eid AND e.kind='planning_packet'
  AND encode(sha256(convert_to(e.body,'UTF8')),'hex')=e.sha256
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(e.body::jsonb->'payload'->'stakeholders') s
    WHERE (s->'contact_id'<>'null'::jsonb AND NOT psl_schedules_grants(e.case_id,(s->>'contact_id')::bigint,ARRAY['planning.participate']))
     OR (s->'evidence_id'<>'null'::jsonb AND NOT psl_engagement_public_source(e.case_id,(s->>'evidence_id')::bigint)))
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(e.body::jsonb->'payload'->'questions') q
    WHERE (q->'evidence_id'<>'null'::jsonb AND NOT psl_engagement_public_source(e.case_id,(q->>'evidence_id')::bigint))
     OR (q->'action_id'<>'null'::jsonb AND NOT EXISTS(SELECT 1 FROM pmo_actionitem a WHERE a.id::text=q->>'action_id' AND a.case_id=e.case_id
      AND a.current_id::text=e.body::jsonb->'action_heads'->>(q->>'action_id'))))
  AND NOT EXISTS(SELECT 1 FROM jsonb_each(e.body::jsonb->'action_heads') h
    WHERE NOT EXISTS(SELECT 1 FROM pmo_actionitem a WHERE a.id::text=h.key AND a.case_id=e.case_id AND to_jsonb(a.current_id)=h.value))
  AND NOT EXISTS(SELECT 1 FROM unnest(ARRAY['prd_id','scope_id','engineering_estimate_id','security_estimate_id']) k
    WHERE e.body::jsonb->'payload'->k<>'null'::jsonb AND NOT psl_engagement_public_source(e.case_id,(e.body::jsonb->'payload'->>k)::bigint)));
$$;'''
SQL = r'''CREATE FUNCTION psl_planning_correlation_current(eid bigint, completeness boolean DEFAULT true) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE e record; p jsonb; r jsonb; pins jsonb; x record; z record; a record; n integer; k text;
BEGIN
 SELECT * INTO e FROM core_evidence WHERE id=eid AND kind='planning_packet';
 IF NOT FOUND OR (e.body::jsonb->>'protocol' IN ('planning-packet/v1','planning-packet/v2')) IS NOT TRUE
 OR encode(sha256(convert_to(e.body,'UTF8')),'hex') IS DISTINCT FROM e.sha256
 OR e.id IS DISTINCT FROM (SELECT id FROM core_evidence WHERE case_id=e.case_id AND kind='planning_packet' ORDER BY version DESC LIMIT 1)
 OR psl_schedules_grants(e.case_id,e.created_by_id,ARRAY['case.read','planning.read','planning.coordinate']) IS NOT TRUE
 OR NOT EXISTS(SELECT 1 FROM core_audit WHERE case_id=e.case_id AND actor_id=e.created_by_id AND action='planning.recorded'
   AND data=jsonb_build_object('kind','packet','evidence_id',e.id,'sha256',e.sha256)) THEN RETURN false; END IF;
 IF e.body::jsonb->>'protocol'='planning-packet/v1' THEN RETURN NOT completeness; END IF;
 p:=e.body::jsonb->'payload';
 IF NOT(p ? 'source_correlations') THEN p:=p||jsonb_build_object('source_correlations','[]'::jsonb); END IF;
 pins:=e.body::jsonb->'source_pins';
 IF jsonb_typeof(p->'source_correlations') IS DISTINCT FROM 'array' OR jsonb_typeof(pins) IS DISTINCT FROM 'object' THEN RETURN false; END IF;
 FOREACH k IN ARRAY ARRAY['prd_id','scope_id','engineering_estimate_id','security_estimate_id'] LOOP
  IF p->k='null'::jsonb AND NOT completeness THEN CONTINUE; END IF;
  IF jsonb_typeof(p->k) IS DISTINCT FROM 'number' OR psl_engagement_public_source(e.case_id,(p->>k)::bigint) IS NOT TRUE THEN RETURN false; END IF;
 END LOOP;
 n:=jsonb_array_length(p->'source_correlations');
 IF (completeness AND n<3) OR n>50 OR (SELECT count(DISTINCT v->>'key') FROM jsonb_array_elements(p->'source_correlations') v)<>n
 OR (SELECT count(DISTINCT (v->>'source_field',v->>'source_id')) FROM jsonb_array_elements(p->'source_correlations') v)<>n
 OR (SELECT count(*) FROM jsonb_object_keys(pins))<>n THEN RETURN false; END IF;
 FOREACH k IN ARRAY ARRAY['scope_id','engineering_estimate_id','security_estimate_id'] LOOP
  IF completeness AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p->'source_correlations') v WHERE v->>'source_field'=k AND v->'source_id'=p->k AND v->>'state'='current') THEN RETURN false; END IF;
 END LOOP;
 FOR r IN SELECT value FROM jsonb_array_elements(p->'source_correlations') LOOP
  IF jsonb_typeof(r) IS DISTINCT FROM 'object' OR NOT(r ?& ARRAY['key','source_field','source_id','document_version','target_prd_id','target_scope_id','evidence_id','state','detail','resolution_id'])
  OR r-ARRAY['key','source_field','source_id','document_version','target_prd_id','target_scope_id','evidence_id','state','detail','resolution_id']<>'{}'::jsonb
  OR (r->>'source_field' IN ('scope_id','engineering_estimate_id','security_estimate_id')) IS NOT TRUE THEN RETURN false; END IF;
  IF jsonb_typeof(pins->(r->>'key')) IS DISTINCT FROM 'object'
  OR NOT(pins->(r->>'key') ?& ARRAY['source','target_prd_id','target_scope_id','evidence_id'])
  OR (pins->(r->>'key'))-ARRAY['source','target_prd_id','target_scope_id','evidence_id','resolution']<>'{}'::jsonb
  OR (r->'resolution_id'='null'::jsonb AND pins->(r->>'key') ? 'resolution') THEN RETURN false; END IF;
  SELECT * INTO x FROM core_evidence WHERE id=(r->>'source_id')::bigint AND case_id=e.case_id;
  IF NOT FOUND OR encode(sha256(convert_to(x.body,'UTF8')),'hex') IS DISTINCT FROM x.sha256 OR psl_engagement_public_source(e.case_id,x.id) IS NOT TRUE
  OR NOT(CASE r->>'source_field' WHEN 'scope_id' THEN x.kind IN ('scope_baseline','requirements','plan')
      WHEN 'engineering_estimate_id' THEN x.kind='engineering_estimate' ELSE x.kind='security_estimate' END)
  OR pins->(r->>'key')->'source' IS DISTINCT FROM jsonb_build_object('id',x.id,'kind',x.kind,'version',x.version,'sha256',x.sha256) THEN RETURN false; END IF;
  FOREACH k IN ARRAY ARRAY['target_prd_id','target_scope_id','evidence_id'] LOOP
   IF r->k='null'::jsonb THEN
    IF pins->(r->>'key')->k IS DISTINCT FROM 'null'::jsonb THEN RETURN false; END IF;
   ELSE
    SELECT * INTO x FROM core_evidence WHERE id=(r->>k)::bigint AND case_id=e.case_id;
    IF NOT FOUND OR encode(sha256(convert_to(x.body,'UTF8')),'hex') IS DISTINCT FROM x.sha256 OR psl_engagement_public_source(e.case_id,x.id) IS NOT TRUE
    OR (k='target_prd_id' AND x.kind NOT IN ('prd','requirements')) OR (k='target_scope_id' AND x.kind NOT IN ('scope_baseline','requirements','plan'))
    OR pins->(r->>'key')->k IS DISTINCT FROM jsonb_build_object('id',x.id,'kind',x.kind,'version',x.version,'sha256',x.sha256) THEN RETURN false; END IF;
   END IF;
  END LOOP;
  -- A supplied disposition pointer is still immutable source provenance at intake.
  -- Current owner authority is deliberately checked only for completeness below.
  IF r->'resolution_id'<>'null'::jsonb THEN
   IF r->>'state' IS DISTINCT FROM 'excluded' THEN RETURN false; END IF;
   SELECT * INTO z FROM core_audit WHERE id=(r->>'resolution_id')::bigint AND case_id=e.case_id AND action='planning.source_resolved';
   IF NOT FOUND OR pins->(r->>'key')->'resolution' IS DISTINCT FROM jsonb_build_object('id',z.id,'sha256',
      (SELECT encode(sha256(convert_to('{'||string_agg(to_json(key)::text||':'||value::text,',' ORDER BY key COLLATE "C")||'}','UTF8')),'hex') FROM jsonb_each(z.data))) THEN RETURN false; END IF;
  END IF;
  IF NOT completeness THEN CONTINUE; END IF;
  IF r->>'state'='current' THEN
   IF r->'resolution_id' IS DISTINCT FROM 'null'::jsonb OR r->'source_id' IS DISTINCT FROM p->(r->>'source_field') OR r->'target_prd_id' IS DISTINCT FROM p->'prd_id'
   OR r->'target_scope_id' IS DISTINCT FROM p->'scope_id' OR jsonb_typeof(r->'document_version') IS DISTINCT FROM 'string'
   OR length(btrim(r->>'document_version'))=0 OR jsonb_typeof(r->'evidence_id') IS DISTINCT FROM 'number' THEN RETURN false; END IF;
  ELSIF r->>'state'='excluded' THEN
   SELECT * INTO z FROM core_audit WHERE id=(r->>'resolution_id')::bigint AND case_id=e.case_id AND action='planning.source_resolved';
   IF NOT FOUND OR z.data-ARRAY['packet_id','packet_sha256','key','action_id','source_field','source_id','source_sha256','disposition','evidence_id','replacement_source_id','target_prd_id','target_scope_id','approval_granted','action_state_id']<>'{}'::jsonb
   OR NOT(z.data ?& ARRAY['packet_id','packet_sha256','key','action_id','source_field','source_id','source_sha256','disposition','evidence_id','replacement_source_id','target_prd_id','target_scope_id','approval_granted','action_state_id'])
   OR pins->(r->>'key')->'resolution' IS DISTINCT FROM jsonb_build_object('id',z.id,'sha256',
      (SELECT encode(sha256(convert_to('{'||string_agg(to_json(key)::text||':'||value::text,',' ORDER BY key COLLATE "C")||'}','UTF8')),'hex') FROM jsonb_each(z.data)))
   OR z.data->>'disposition' IS DISTINCT FROM 'exclude_in_successor' OR z.data->'approval_granted' IS DISTINCT FROM 'false'::jsonb
   OR z.data->'source_id' IS DISTINCT FROM r->'source_id' OR z.data->'source_field' IS DISTINCT FROM r->'source_field'
   OR z.data->'replacement_source_id' IS DISTINCT FROM p->(r->>'source_field') OR z.data->'target_prd_id' IS DISTINCT FROM p->'prd_id'
   OR z.data->'target_scope_id' IS DISTINCT FROM p->'scope_id'
   OR z.data->>'source_sha256' IS DISTINCT FROM (SELECT sha256 FROM core_evidence WHERE id=(r->>'source_id')::bigint AND case_id=e.case_id)
   OR NOT EXISTS(SELECT 1 FROM core_audit marker JOIN core_evidence original ON original.id=(z.data->>'packet_id')::bigint
      WHERE marker.case_id=e.case_id AND marker.action='planning.source_clarification'
      AND marker.data->'packet_id'=z.data->'packet_id' AND marker.data->'packet_sha256'=z.data->'packet_sha256'
      AND marker.data->'key'=z.data->'key' AND marker.data->'action_id'=z.data->'action_id'
      AND original.case_id=e.case_id AND original.kind='planning_packet' AND original.sha256=z.data->>'packet_sha256'
      AND psl_schedules_grants(e.case_id,original.created_by_id,ARRAY['case.read','planning.read','planning.coordinate']) IS TRUE
      AND EXISTS(SELECT 1 FROM jsonb_array_elements(original.body::jsonb->'payload'->'source_correlations') old
        WHERE old->'key'=z.data->'key' AND old->'source_field'=z.data->'source_field' AND old->'source_id'=z.data->'source_id'))
   OR psl_schedules_grants(e.case_id,z.actor_id,ARRAY['case.read','planning.read','planning.participate','action.own','action.work']) IS NOT TRUE
   OR psl_engagement_public_source(e.case_id,(z.data->>'evidence_id')::bigint) IS NOT TRUE
   OR NOT EXISTS(SELECT 1 FROM pmo_actionitem ai JOIN pmo_actionstate s ON s.id=ai.current_id
    WHERE ai.id=(z.data->>'action_id')::bigint AND ai.case_id=e.case_id AND s.id=(z.data->>'action_state_id')::bigint
    AND s.owner_id=z.actor_id AND s.actor_id=z.actor_id AND s.status='completed' AND s.evidence_id=(z.data->>'evidence_id')::bigint)
   THEN RETURN false; END IF;
  ELSE RETURN false;
  END IF;
 END LOOP;
 RETURN true;
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR null_value_not_allowed THEN RETURN false;
END $$;
CREATE FUNCTION psl_planning_correlation_verified_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.definition='planning/v1' AND NEW.status='verified' AND psl_planning_correlation_current(NEW.source_head_id) IS NOT TRUE
 THEN RAISE EXCEPTION 'Current exact planning source correlation required; unknown, conflicted or legacy correlation cannot verify'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_planning_correlation_verified BEFORE INSERT OR UPDATE ON workflows_factorywork FOR EACH ROW EXECUTE FUNCTION psl_planning_correlation_verified_guard();

CREATE OR REPLACE FUNCTION psl_engagement_planning_inputs_current(eid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM core_evidence e WHERE e.id=eid AND e.kind='planning_packet'
  AND psl_planning_correlation_current(eid,false) IS TRUE
  AND encode(sha256(convert_to(e.body,'UTF8')),'hex')=e.sha256
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(e.body::jsonb->'payload'->'stakeholders') s
    WHERE (s->'contact_id'<>'null'::jsonb AND NOT psl_schedules_grants(e.case_id,(s->>'contact_id')::bigint,ARRAY['planning.participate']))
     OR (s->'evidence_id'<>'null'::jsonb AND NOT psl_engagement_public_source(e.case_id,(s->>'evidence_id')::bigint)))
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(e.body::jsonb->'payload'->'questions') q
    WHERE (q->'evidence_id'<>'null'::jsonb AND NOT psl_engagement_public_source(e.case_id,(q->>'evidence_id')::bigint))
     OR (q->'action_id'<>'null'::jsonb AND NOT EXISTS(SELECT 1 FROM pmo_actionitem a WHERE a.id::text=q->>'action_id' AND a.case_id=e.case_id
      AND a.current_id::text=e.body::jsonb->'action_heads'->>(q->>'action_id'))))
  AND NOT EXISTS(SELECT 1 FROM jsonb_each(e.body::jsonb->'action_heads') h
    WHERE NOT EXISTS(SELECT 1 FROM pmo_actionitem a WHERE a.id::text=h.key AND a.case_id=e.case_id AND to_jsonb(a.current_id)=h.value))
  AND NOT EXISTS(SELECT 1 FROM unnest(ARRAY['prd_id','scope_id','engineering_estimate_id','security_estimate_id']) k
    WHERE e.body::jsonb->'payload'->k<>'null'::jsonb AND NOT psl_engagement_public_source(e.case_id,(e.body::jsonb->'payload'->>k)::bigint)));
$$;
'''

REVERSE_SQL = PARENT_SQL + """
DROP TRIGGER psl_planning_correlation_verified ON workflows_factorywork;
DROP FUNCTION psl_planning_correlation_verified_guard();
DROP FUNCTION psl_planning_correlation_current(bigint,boolean);
"""

def require_exact_parent(apps, schema_editor):
    assert hashlib.sha256(PARENT_SQL.encode()).hexdigest() == PARENT_SHA256
    body = PARENT_SQL.split('AS $$', 1)[1].rsplit('$$;', 1)[0]
    assert hashlib.sha256(body.encode()).hexdigest() == PARENT_BODY_SHA256
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT prosrc FROM pg_proc WHERE oid='psl_engagement_planning_inputs_current(bigint)'::regprocedure")
        if cursor.fetchone()[0] != body:
            raise RuntimeError('Planning input predecessor differs from its frozen native body; reconcile before upgrading')

class Migration(migrations.Migration):
    dependencies = [('workflows', '0082_allocation_coverage')]
    operations = [migrations.RunPython(require_exact_parent, migrations.RunPython.noop), migrations.RunSQL(SQL, REVERSE_SQL)]
