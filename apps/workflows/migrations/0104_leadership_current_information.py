"""Generate a leadership report from current records on demand."""

from importlib import import_module

from django.db import migrations


PRIOR = import_module('apps.workflows.migrations.0103_leadership_department_scope')
HELPER = """
CREATE FUNCTION psl_leadership_base_inputs(i jsonb) RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
 SELECT i-'scope' || CASE WHEN i->'scope'->>'mode'='all_psl_projects'
  AND i->'scope'->>'basis'='current_information'
  THEN '{"_current_snapshot":true}'::jsonb ELSE '{}'::jsonb END;
$$;
"""
UPDATES = {
    'psl_leadership_inputs_selected(jsonb)': [
        ("i-ARRAY['template_id','content_id','start_at','end_at','kind','audience','selections']",
         "i-ARRAY['template_id','content_id','start_at','end_at','kind','audience','selections','_current_snapshot']"),
        ("OR (i->>'end_at')::timestamptz-(i->>'start_at')::timestamptz>interval '366 days'",
         """OR ((i->>'end_at')::timestamptz-(i->>'start_at')::timestamptz>interval '366 days'
               AND i->'_current_snapshot' IS DISTINCT FROM 'true'::jsonb)"""),
    ],
    'psl_leadership_inputs(jsonb)': [
        ("psl_leadership_inputs_selected(i-'scope')", "psl_leadership_inputs_selected(psl_leadership_base_inputs(i))"),
        ("s-ARRAY['mode','actor','register_id','domains']='{}'::jsonb",
         """s-ARRAY['mode','actor','register_id','domains','basis']='{}'::jsonb
      AND (NOT s?'basis' OR s->>'basis'='current_information')"""),
    ],
    'psl_leadership_manifest_selected(uuid,jsonb)': [
        ("s.occurred_at>=(i->>'start_at')::timestamptz",
         "(i->'_current_snapshot'='true'::jsonb OR s.occurred_at>=(i->>'start_at')::timestamptz)"),
        ("n.completed_at>=(i->>'start_at')::timestamptz",
         "(i->'_current_snapshot'='true'::jsonb OR n.completed_at>=(i->>'start_at')::timestamptz)"),
    ],
    'psl_leadership_manifest(uuid,jsonb)': [
        ("psl_leadership_manifest_selected(cid,i-'scope')",
         "psl_leadership_manifest_selected(cid,psl_leadership_base_inputs(i))"),
    ],
    'psl_leadership_project_scope(uuid,jsonb)': [
        ("base jsonb:=i-'scope'", "base jsonb:=psl_leadership_base_inputs(i)"),
        ("psl_leadership_scope_sources(project_id,(i->>'start_at')::timestamptz,",
         """psl_leadership_scope_sources(project_id,
        CASE WHEN s->>'basis'='current_information' THEN '-infinity'::timestamptz
             ELSE (i->>'start_at')::timestamptz END,"""),
    ],
    'psl_leadership_document(bigint,bigint,bigint)': [
        ("(w.request->>'start_at')||' / '||(w.request->>'end_at')",
         """CASE WHEN packet->'inputs'->'scope'->>'basis'='current_information'
         THEN 'As of '||(w.request->>'end_at')
         ELSE (w.request->>'start_at')||' / '||(w.request->>'end_at') END"""),
    ],
}


def edit(sql, changes):
    for before, after in changes:
        sql = PRIOR.replace_once(sql, before, after)
    return sql


def forwards(apps, schema_editor):
    schema_editor.execute(HELPER, params=None)
    for signature, changes in UPDATES.items():
        PRIOR.update(schema_editor, signature, lambda sql: edit(sql, changes))


def backwards(apps, schema_editor):
    for signature, changes in reversed(UPDATES.items()):
        PRIOR.update(schema_editor, signature, lambda sql: edit(sql, ((after, before) for before, after in reversed(changes))))
    schema_editor.execute('DROP FUNCTION psl_leadership_base_inputs(jsonb);', params=None)


class Migration(migrations.Migration):
    dependencies = [('workflows', '0103_leadership_department_scope')]
    operations = [migrations.RunPython(forwards, backwards)]
