"""Apply the leadership reporting rule to current department leads."""

import re
from importlib import import_module

from django.db import migrations


PRIOR = import_module('apps.workflows.migrations.0092_leadership_project_scope')
REGISTER = 'psl:leadership-project-register/v1'
SOURCE_GRANTS = (
    "psl_reporting_grants(w.case_id,e.created_by_id,ARRAY['evidence.add'])",
    "psl_reporting_grants(w.case_id,e.created_by_id,ARRAY['factory.start'])",
    "psl_reporting_grants(w.case_id,e.created_by_id,ARRAY['factory.manage'])",
)
HELPERS = """
CREATE FUNCTION psl_leadership_lead(cid uuid,uid bigint) RETURNS text LANGUAGE sql STABLE AS $$
 SELECT membership.role FROM core_case home
 JOIN core_case assigned ON assigned.tenant=home.tenant AND assigned.synthetic=home.synthetic AND assigned.kind='project'
 JOIN identity_staffmembership membership ON membership.case_id=assigned.id
 JOIN auth_user staff ON staff.id=membership.user_id AND staff.is_active
 WHERE home.id=cid AND home.kind='project' AND membership.user_id=uid AND membership.active
   AND membership.mode='lead' AND membership.role IN ('pmo-lead','finance-lead')
 ORDER BY CASE membership.role WHEN 'pmo-lead' THEN 0 ELSE 1 END,membership.id LIMIT 1;
$$;

CREATE FUNCTION psl_leadership_role_grants(cid uuid,uid bigint,actions text[]) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT psl_reporting_grants(cid,uid,actions) OR COALESCE((
   SELECT actions <@ ARRAY['case.read','report.read','factory.start','evidence.add']::text[]
          OR lead_role='pmo-lead'
          AND actions <@ ARRAY['case.read','report.read','factory.start','evidence.add','meeting.read','issue.read','change.read']::text[]
   FROM psl_leadership_lead(cid,uid) lead_role WHERE lead_role IS NOT NULL),false);
$$;

CREATE FUNCTION psl_leadership_register(p jsonb) RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
 SELECT jsonb_build_object('project_count',jsonb_array_length(p),'sha256',encode(sha256(convert_to(
     (SELECT jsonb_agg(jsonb_build_array(item->'case',item->'name') ORDER BY item->>'case')
       FROM jsonb_array_elements(p) item)::text,'UTF8')),'hex'));
$$;
"""


def original(name):
    return re.search(rf'CREATE FUNCTION {name}\(.*?\$\$;',
                     PRIOR.SCOPE_SQL, re.S)[0].replace('CREATE FUNCTION', 'CREATE OR REPLACE FUNCTION', 1)


def replace_once(sql, before, after):
    if sql.count(before) != 1:
        raise ValueError(f'Unexpected leadership SQL definition for {before!r}')
    return sql.replace(before, after)


def definitions():
    inputs = original('psl_leadership_inputs')
    base = """s ?& ARRAY['mode','actor','configuration','domains']
    AND s-ARRAY['mode','actor','configuration','domains']='{}'::jsonb
    AND s->>'mode'='all_authorised_projects'
    AND s->'actor'=to_jsonb((s->>'actor')::bigint) AND (s->>'actor')::bigint>0
    AND s->'configuration'=to_jsonb((s->>'configuration')::bigint) AND (s->>'configuration')::bigint>0"""
    inputs = replace_once(inputs, base, """s ?& ARRAY['mode','actor','domains']
    AND s->'actor'=to_jsonb((s->>'actor')::bigint) AND (s->>'actor')::bigint>0
    AND CASE s->>'mode' WHEN 'all_authorised_projects' THEN
      s-ARRAY['mode','actor','configuration','domains']='{}'::jsonb
      AND (s->>'configuration')::bigint>0 AND s->'configuration'=to_jsonb((s->>'configuration')::bigint)
    WHEN 'all_psl_projects' THEN
      s-ARRAY['mode','actor','register_id','domains']='{}'::jsonb
      AND s->'domains'='["actions","changes","escalations","issues","meetings","milestones"]'::jsonb
      AND (s->'register_id'='null'::jsonb OR (s->>'register_id')::bigint>0
           AND s->'register_id'=to_jsonb((s->>'register_id')::bigint))
    ELSE false END""")
    scope = original('psl_leadership_project_scope')
    scope = replace_once(scope, 'claims jsonb; selections jsonb; anchors jsonb; reported jsonb;',
                         """claims jsonb; selections jsonb; anchors jsonb; reported jsonb;
        lead_scope boolean:=s->>'mode'='all_psl_projects';""")
    scope = replace_once(scope, ' IF s IS NULL OR NOT psl_leadership_inputs(i) OR', """ IF s IS NULL OR NOT psl_leadership_inputs(i) THEN RETURN NULL; END IF;
 IF lead_scope THEN
  IF psl_leadership_lead(cid,owner_id) IS NULL THEN RETURN NULL; END IF;
  SELECT ARRAY(SELECT project.id FROM core_case home JOIN core_case project
      ON project.tenant=home.tenant AND project.synthetic=home.synthetic AND project.kind='project'
      WHERE home.id=cid AND home.kind='project' ORDER BY project.id) INTO project_ids;
 ELSE
 IF""")
    scope = replace_once(scope, 'IF cardinality(project_ids) NOT BETWEEN 1 AND 16 THEN RETURN NULL; END IF;',
                         'IF cardinality(project_ids) NOT BETWEEN 1 AND 16 THEN RETURN NULL; END IF;\n END IF;')
    scope = replace_once(scope, 'SELECT domain,psl_reporting_grants(project_id,owner_id,ARRAY[CASE domain',
                         'SELECT domain,psl_leadership_role_grants(project_id,owner_id,ARRAY[CASE domain')
    scope = replace_once(scope, """IF considered>200 THEN RETURN NULL; END IF;
  picked:='[]'::jsonb; excluded:=0;""", """IF NOT lead_scope AND considered>200 THEN RETURN NULL; END IF;
  picked:='[]'::jsonb; excluded:=0;
  IF lead_scope AND jsonb_array_length(matches)>200 THEN
   matches:=matches-200;
   excluded:=1;
  END IF;""")
    scope = replace_once(scope, "'unavailable_domains',unavailable,'excluded_sources',excluded));",
                         """'unavailable_domains',unavailable,'excluded_sources',excluded)
      ||CASE WHEN lead_scope THEN jsonb_build_object('name',(SELECT title FROM core_case WHERE id=project_id))
             ELSE '{}'::jsonb END);""")
    scope = replace_once(scope, " RETURN s||jsonb_build_object('projects',projects,'record_counts',reported);", f"""
 IF lead_scope AND s->'register_id'<>'null'::jsonb AND NOT EXISTS(
   SELECT 1 FROM core_evidence e WHERE e.id=(s->>'register_id')::bigint AND e.case_id=cid
    AND e.created_by_id=owner_id AND e.kind='agent_private_leadership_project_register'
    AND e.source='{REGISTER}' AND psl_escalation_json(e.body)=psl_leadership_register(projects))
 THEN RETURN NULL; END IF;
 RETURN s||jsonb_build_object('projects',projects,'record_counts',reported);""")
    access = original('psl_leadership_access')
    access = replace_once(access, 'DECLARE p jsonb; project_id uuid;', """DECLARE p jsonb; project_id uuid;
 lead_scope boolean:=COALESCE(m->'project_scope'->>'mode'='all_psl_projects',false);""")
    access = replace_once(access, "OR jsonb_array_length(m->'project_scope'->'projects') NOT BETWEEN 1 AND 16",
                         "OR (NOT lead_scope AND jsonb_array_length(m->'project_scope'->'projects') NOT BETWEEN 1 AND 16)")
    access = replace_once(access, "OR NOT psl_reporting_grants(project_id,uid,ARRAY['case.read','report.read'])",
                         """OR NOT (psl_reporting_grants(project_id,uid,ARRAY['case.read','report.read'])
             OR lead_scope AND psl_leadership_lead(project_id,uid) IS NOT NULL)""")
    citations = replace_once(original('psl_leadership_project_citations'),
                             "OR EXISTS(SELECT 1", """OR COALESCE(
         m->'project_scope'->>'mode'='all_psl_projects' AND m->'project_scope'->'register_id'=citation,false)
    OR EXISTS(SELECT 1""")
    summary = replace_once(original('psl_leadership_project_summary'), "' same-entity projects with current access. '",
                           """' same-entity projects with current access. '
   ||CASE WHEN s->>'mode'='all_psl_projects' THEN
       'Projects: '||COALESCE((SELECT string_agg(p->>'name',', ' ORDER BY p->>'name',p->>'case')
       FROM jsonb_array_elements(s->'projects') p),'')||'. ' ELSE '' END""")
    return inputs, scope, access, citations, summary


def update(schema_editor, signature, edit):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('SELECT pg_get_functiondef(%s::regprocedure)', [signature])
        sql = cursor.fetchone()[0]
    schema_editor.execute(edit(sql), params=None)


def source_checks(sql, *, reverse=False):
    for expression in SOURCE_GRANTS:
        if expression not in sql and not reverse:
            continue
        fallback = (" OR w.actor_id=e.created_by_id AND psl_leadership_lead(w.case_id,e.created_by_id) IS NOT NULL"
                    if "'factory.manage'" in expression else ' OR ' +
                    expression.replace('psl_reporting_grants', 'psl_leadership_role_grants'))
        alternative = '(' + expression + fallback + ')'
        sql = sql.replace(alternative, expression) if reverse else sql.replace(expression, alternative)
    return sql


def forwards(apps, schema_editor):
    schema_editor.execute(HELPERS, params=None)
    for sql in definitions():
        schema_editor.execute(sql, params=None)
    update(schema_editor, 'psl_leadership_access_selected(uuid,bigint,jsonb)',
           lambda sql: sql.replace('psl_reporting_grants(', 'psl_leadership_role_grants('))
    update(schema_editor, 'psl_leadership_document(bigint,bigint,bigint)', source_checks)
    update(schema_editor, 'psl_factory_leadership_guard()', lambda sql: replace_once(sql,
           "NOT psl_reporting_grants(NEW.case_id,e.created_by_id,ARRAY['evidence.add'])",
           """NOT psl_leadership_role_grants(NEW.case_id,e.created_by_id,ARRAY['evidence.add'])
             OR (body->'inputs'->'scope'->>'mode'='all_psl_projects'
                 AND body->'inputs'->'scope'->'register_id'='null'::jsonb)"""))


def backwards(apps, schema_editor):
    for name in ('inputs', 'project_scope', 'access', 'project_citations', 'project_summary'):
        schema_editor.execute(original('psl_leadership_' + name), params=None)
    update(schema_editor, 'psl_leadership_access_selected(uuid,bigint,jsonb)',
           lambda sql: sql.replace('psl_leadership_role_grants(', 'psl_reporting_grants('))
    update(schema_editor, 'psl_leadership_document(bigint,bigint,bigint)', lambda sql: source_checks(sql, reverse=True))
    update(schema_editor, 'psl_factory_leadership_guard()', lambda sql: replace_once(sql,
           """NOT psl_leadership_role_grants(NEW.case_id,e.created_by_id,ARRAY['evidence.add'])
             OR (body->'inputs'->'scope'->>'mode'='all_psl_projects'
                 AND body->'inputs'->'scope'->'register_id'='null'::jsonb)""",
           "NOT psl_reporting_grants(NEW.case_id,e.created_by_id,ARRAY['evidence.add'])"))
    schema_editor.execute("""DROP FUNCTION psl_leadership_role_grants(uuid,bigint,text[]);
        DROP FUNCTION psl_leadership_lead(uuid,bigint); DROP FUNCTION psl_leadership_register(jsonb);""", params=None)


class Migration(migrations.Migration):
    dependencies = [('workflows', '0102_work_status_timestamp')]
    operations = [migrations.RunPython(forwards, backwards)]
