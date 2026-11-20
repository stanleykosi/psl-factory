"""Add an exact, bounded same-entity scope to existing leadership report guards."""

from django.db import migrations


LEGACY_FUNCTIONS = (
    ('psl_leadership_inputs', 'jsonb'),
    ('psl_leadership_manifest', 'uuid,jsonb'),
    ('psl_leadership_access', 'uuid,bigint,jsonb'),
    ('psl_incident_report_summary', 'jsonb'),
)

SCOPE_SQL = """
CREATE FUNCTION psl_leadership_inputs(i jsonb) RETURNS boolean LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE s jsonb:=i->'scope';
BEGIN
 IF psl_leadership_inputs_selected(i-'scope') IS DISTINCT FROM true THEN RETURN false; END IF;
 IF s IS NULL THEN RETURN true; END IF;
 RETURN COALESCE(jsonb_typeof(s)='object' AND s ?& ARRAY['mode','actor','configuration','domains']
    AND s-ARRAY['mode','actor','configuration','domains']='{}'::jsonb
    AND s->>'mode'='all_authorised_projects'
    AND s->'actor'=to_jsonb((s->>'actor')::bigint) AND (s->>'actor')::bigint>0
    AND s->'configuration'=to_jsonb((s->>'configuration')::bigint) AND (s->>'configuration')::bigint>0
    AND jsonb_typeof(s->'domains')='array'
    AND jsonb_array_length(s->'domains') BETWEEN 1 AND 6
    AND '["actions","changes","escalations","issues","meetings","milestones"]'::jsonb @> (s->'domains')
    AND s->'domains'=(SELECT jsonb_agg(DISTINCT value ORDER BY value) FROM jsonb_array_elements(s->'domains'))
    AND NOT EXISTS(SELECT 1 FROM jsonb_each(i->'selections') d WHERE d.value<>'[]'::jsonb),false);
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;

CREATE FUNCTION psl_leadership_scope_policy(cid uuid,pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration p, LATERAL psl_reporting_refs(p.id) settings
  WHERE p.id=pid AND p.case_id=cid AND p.component='OPS.leadership_project_scope'
    AND settings='{"enabled":true}'::jsonb AND psl_reporting_policy(cid,p.id));
$$;

CREATE FUNCTION psl_leadership_scope_sources(cid uuid,starts timestamptz,ends timestamptz,domains jsonb)
RETURNS TABLE(domain text, subject_id bigint, revision_id bigint, evidence_id bigint) LANGUAGE sql STABLE AS $$
 SELECT 'meetings', n.id, s.id, s.evidence_id FROM pmo_meeting n JOIN pmo_meetingversion s ON s.id=n.current_id
 WHERE domains?'meetings' AND n.case_id=cid AND s.occurred_at>=starts AND s.occurred_at<ends
 UNION ALL
 SELECT 'actions', n.id, s.id, s.evidence_id FROM pmo_actionitem n JOIN pmo_actionstate s ON s.id=n.current_id
 WHERE domains?'actions' AND n.case_id=cid AND s.created_at>=starts AND s.created_at<ends
 UNION ALL
 SELECT 'milestones', n.id, n.id, n.evidence_id FROM pmo_milestone n
 WHERE domains?'milestones' AND n.case_id=cid AND n.completed_at>=starts AND n.completed_at<ends
 UNION ALL
 SELECT 'issues', n.id, s.id, s.evidence_id FROM pmo_issue n JOIN pmo_issuestate s ON s.id=n.current_id
 WHERE domains?'issues' AND n.case_id=cid AND s.created_at>=starts AND s.created_at<ends
 UNION ALL
 SELECT 'changes', n.id, s.id, s.evidence_id FROM pmo_changerequest n JOIN pmo_changeversion s ON s.id=n.current_id
 WHERE domains?'changes' AND n.case_id=cid AND s.created_at>=starts AND s.created_at<ends
 UNION ALL
 SELECT 'escalations', n.id, n.id, n.evidence_id FROM pmo_escalationrequest n
 JOIN pmo_escalationprofile p ON p.id=n.profile_id JOIN pmo_issuestate s ON s.id=p.state_id
 JOIN pmo_issue issue ON issue.id=s.issue_id AND issue.current_id=s.id
 WHERE domains?'escalations' AND issue.case_id=cid AND n.created_at>=starts AND n.created_at<ends
 AND p.id=(SELECT max(pp.id) FROM pmo_escalationprofile pp JOIN pmo_issuestate ss ON ss.id=pp.state_id
           WHERE ss.issue_id=issue.id);
$$;

CREATE FUNCTION psl_leadership_project_scope(cid uuid,i jsonb) RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE s jsonb:=i->'scope'; base jsonb:=i-'scope'; owner_id bigint:=(s->>'actor')::bigint;
        project_id uuid; project_ids uuid[]; checked jsonb; unavailable jsonb; matches jsonb; picked jsonb; source_row jsonb;
        per_project jsonb; projects jsonb:='[]'::jsonb; considered integer:=0; excluded integer; section jsonb;
        claims jsonb; selections jsonb; anchors jsonb; reported jsonb;
BEGIN
 IF s IS NULL OR NOT psl_leadership_inputs(i) OR NOT psl_leadership_scope_policy(cid,(s->>'configuration')::bigint)
    OR NOT psl_reporting_grants(cid,owner_id,ARRAY['case.read','report.read']) THEN RETURN NULL; END IF;
 SELECT ARRAY(SELECT project.id FROM core_case home JOIN core_case project
              ON project.tenant=home.tenant AND project.synthetic=home.synthetic AND project.kind='project'
              JOIN identity_grant visible ON visible.case_id=project.id AND visible.user_id=owner_id
               AND visible.action='case.read' AND visible.active
              JOIN identity_grant report ON report.case_id=project.id AND report.user_id=owner_id
               AND report.action='report.read' AND report.active
              WHERE home.id=cid AND home.kind='project'
              ORDER BY project.id LIMIT 17) INTO project_ids;
 IF cardinality(project_ids) NOT BETWEEN 1 AND 16 THEN RETURN NULL; END IF;
 IF i->'content_id'<>'null'::jsonb THEN
  SELECT psl_escalation_json(e.body)->'sections' INTO section FROM core_evidence e
  WHERE e.id=(i->>'content_id')::bigint AND e.case_id=cid AND e.kind='agent_private_leadership_report_content';
  IF jsonb_typeof(section) IS DISTINCT FROM 'object' THEN RETURN NULL; END IF;
 END IF;
 FOREACH project_id IN ARRAY project_ids LOOP
  SELECT COALESCE(jsonb_agg(domain ORDER BY domain) FILTER (WHERE allowed),'[]'::jsonb),
         COALESCE(jsonb_agg(domain ORDER BY domain) FILTER (WHERE NOT allowed),'[]'::jsonb)
   INTO checked,unavailable FROM (
    SELECT domain,psl_reporting_grants(project_id,owner_id,ARRAY[CASE domain
    WHEN 'meetings' THEN 'meeting.read' WHEN 'actions' THEN 'meeting.read' WHEN 'milestones' THEN 'meeting.read'
    WHEN 'changes' THEN 'change.read' ELSE 'issue.read' END]) AS allowed
    FROM jsonb_array_elements_text(s->'domains') AS included(domain)
   ) permission;
  SELECT COALESCE(jsonb_agg(jsonb_build_array(f.domain,f.subject_id,f.revision_id,f.evidence_id)
           ORDER BY f.domain,f.subject_id),'[]'::jsonb) INTO matches
  FROM (SELECT * FROM psl_leadership_scope_sources(project_id,(i->>'start_at')::timestamptz,
        (i->>'end_at')::timestamptz,checked) ORDER BY domain,subject_id LIMIT 201) f;
  considered:=considered+jsonb_array_length(matches);
  IF considered>200 THEN RETURN NULL; END IF;
  picked:='[]'::jsonb; excluded:=0;
  FOR source_row IN SELECT value FROM jsonb_array_elements(matches) LOOP
   anchors:=CASE WHEN source_row->>0='changes' THEN jsonb_build_array(source_row-0) ELSE '[]'::jsonb END;
   IF NOT psl_leadership_access_selected(project_id,owner_id,jsonb_build_object('changes',anchors,
       'source_actions','[]'::jsonb,'sources',jsonb_build_array(jsonb_build_object('id',(source_row->>3)::bigint)))) THEN
    excluded:=excluded+1;
    CONTINUE;
   END IF;
   picked:=picked||jsonb_build_array(source_row);
  END LOOP;
  SELECT jsonb_object_agg(domain, COALESCE((SELECT jsonb_agg((r->>1)::bigint ORDER BY (r->>1)::bigint)
           FROM jsonb_array_elements(picked) r WHERE r->>0=domain),'[]'::jsonb)) INTO selections
  FROM jsonb_object_keys(i->'selections') AS category(domain);
  per_project:=psl_leadership_manifest_selected(project_id,base||jsonb_build_object(
      'selections',selections,'content_id',NULL));
  IF per_project IS NULL OR NOT psl_leadership_access_selected(project_id,owner_id,per_project) THEN RETURN NULL; END IF;
  IF section IS NOT NULL THEN
   claims:=psl_incident_report_claims(project_id,selections,section);
   IF claims IS NULL OR NOT psl_incident_report_access(project_id,owner_id,claims) THEN RETURN NULL; END IF;
   IF jsonb_array_length(claims)>0 THEN per_project:=per_project||jsonb_build_object('incident_claims',claims); END IF;
  END IF;
  projects:=projects||jsonb_build_array(jsonb_build_object('case',project_id,'inventory',per_project,
      'unavailable_domains',unavailable,'excluded_sources',excluded));
 END LOOP;
 SELECT jsonb_object_agg(domain,COALESCE((SELECT sum(jsonb_array_length(p->'inventory'->domain))
         FROM jsonb_array_elements(projects) p),0)) INTO reported
 FROM jsonb_array_elements_text(s->'domains') AS category(domain);
 RETURN s||jsonb_build_object('projects',projects,'record_counts',reported);
EXCEPTION WHEN OTHERS THEN RETURN NULL;
END $$;

CREATE FUNCTION psl_leadership_manifest(cid uuid,i jsonb) RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE base jsonb:=psl_leadership_manifest_selected(cid,i-'scope'); scoped jsonb;
BEGIN
 IF NOT (i?'scope') THEN RETURN base; END IF;
 scoped:=psl_leadership_project_scope(cid,i);
 IF base IS NULL OR scoped IS NULL THEN RETURN NULL; END IF;
 RETURN base||jsonb_build_object('project_scope',scoped);
END $$;

CREATE FUNCTION psl_leadership_access(cid uuid,uid bigint,m jsonb) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE p jsonb; project_id uuid;
BEGIN
 IF NOT psl_leadership_access_selected(cid,uid,m) THEN RETURN false; END IF;
 IF NOT m?'project_scope' THEN RETURN true; END IF;
 IF jsonb_typeof(m->'project_scope'->'projects') IS DISTINCT FROM 'array'
    OR jsonb_array_length(m->'project_scope'->'projects') NOT BETWEEN 1 AND 16 THEN RETURN false; END IF;
 FOR p IN SELECT value FROM jsonb_array_elements(m->'project_scope'->'projects') LOOP
  project_id:=(p->>'case')::uuid;
  IF NOT EXISTS(SELECT 1 FROM core_case home JOIN core_case project ON project.id=project_id
    AND project.tenant=home.tenant AND project.synthetic=home.synthetic AND project.kind='project' WHERE home.id=cid)
    OR NOT psl_reporting_grants(project_id,uid,ARRAY['case.read','report.read'])
    OR NOT psl_leadership_access_selected(project_id,uid,p->'inventory') THEN RETURN false; END IF;
 END LOOP;
 RETURN true;
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;

CREATE FUNCTION psl_leadership_project_citations(m jsonb,citation jsonb) RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
 SELECT m->'sources' @> jsonb_build_array(jsonb_build_object('id',citation))
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(m->'project_scope'->'projects') p
              WHERE p->'inventory'->'sources' @> jsonb_build_array(jsonb_build_object('id',citation)));
$$;

CREATE FUNCTION psl_leadership_project_summary(s jsonb) RETURNS text LANGUAGE sql IMMUTABLE AS $$
 SELECT CASE WHEN s IS NULL THEN '' ELSE
   ' Project coverage: '||jsonb_array_length(s->'projects')::text||' same-entity projects with current access. '
   ||COALESCE((SELECT string_agg(domain.key||': '||domain.value,', ' ORDER BY domain.key)
       FROM jsonb_each_text(s->'record_counts') domain),'No recorded sources')||'. '
   ||'Counts include only accessible current records in the selected period. Omitted records and unavailable areas remain unknown.' END;
$$;

CREATE FUNCTION psl_incident_report_summary(m jsonb) RETURNS text LANGUAGE sql STABLE AS $$
 SELECT psl_incident_report_summary_selected(m)||psl_leadership_project_summary(m->'project_scope');
$$;

CREATE FUNCTION psl_leadership_scope_origin_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE packet jsonb; author_id bigint;
BEGIN
 IF NEW.definition<>'pmo-leadership-report/v1' OR (TG_OP='UPDATE' AND NEW.source_head_id=OLD.source_head_id) THEN RETURN NEW; END IF;
 SELECT psl_escalation_json(e.body),e.created_by_id INTO packet,author_id FROM core_evidence e WHERE e.id=NEW.source_head_id;
 IF packet->'inputs'?'scope' AND (packet->'inputs'->'scope'->>'actor')::bigint IS DISTINCT FROM author_id THEN
  RAISE EXCEPTION 'Project coverage must belong to the exact current leadership instruction author';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER factory_leadership_scope_origin BEFORE INSERT OR UPDATE ON workflows_factorywork
FOR EACH ROW EXECUTE FUNCTION psl_leadership_scope_origin_guard();

CREATE FUNCTION psl_leadership_scope_publication_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE home_id uuid;
BEGIN
 SELECT report.case_id INTO home_id FROM pmo_minutesreportbinding binding
 JOIN pmo_periodreport report ON report.id=binding.report_id
 WHERE binding.version_id=NEW.version_id AND binding.manifest?'project_scope';
 IF NOT FOUND THEN RETURN NEW; END IF;
 IF NEW.factory_work_id IS NULL OR NOT psl_leadership_document(NEW.factory_work_id,NEW.factory_source_id,NEW.version_id)
   OR NOT psl_leadership_principals(NEW.factory_work_id,NEW.version_id,NEW.actor_id)
   OR NOT psl_leadership_review(home_id,NEW.version_id,NEW.review_id)
   OR NOT psl_leadership_distribution(home_id,NEW.version_id,NEW.policies,NEW.recipient_ids,NEW.retention_days) THEN
  RAISE EXCEPTION 'Exact current project coverage, native approval and scoped recipients are required';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER leadership_scope_publication BEFORE INSERT ON documents_publication
FOR EACH ROW EXECUTE FUNCTION psl_leadership_scope_publication_guard();
"""

ORIGINAL_CITATION = "NOT b.manifest->'sources' @> jsonb_build_array(jsonb_build_object('id',citation))"
SCOPED_CITATION = 'NOT psl_leadership_project_citations(b.manifest,citation)'


def replace_citation(schema_editor, old, new):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT pg_get_functiondef('psl_leadership_document(bigint,bigint,bigint)'::regprocedure)")
        definition = cursor.fetchone()[0]
    if definition.count(old) != 1 or 'psl_leadership_manifest' not in definition:
        raise RuntimeError('Unexpected predecessor for leadership document citations')
    schema_editor.execute(definition.replace(old, new), params=None)


def forwards(apps, schema_editor):
    for name, signature in LEGACY_FUNCTIONS:
        schema_editor.execute(f'ALTER FUNCTION {name}({signature}) RENAME TO {name}_selected', params=None)
    schema_editor.execute(SCOPE_SQL, params=None)
    replace_citation(schema_editor, ORIGINAL_CITATION, SCOPED_CITATION)


def backwards(apps, schema_editor):
    replace_citation(schema_editor, SCOPED_CITATION, ORIGINAL_CITATION)
    schema_editor.execute('DROP TRIGGER leadership_scope_publication ON documents_publication', params=None)
    schema_editor.execute('DROP FUNCTION psl_leadership_scope_publication_guard()', params=None)
    schema_editor.execute('DROP TRIGGER factory_leadership_scope_origin ON workflows_factorywork', params=None)
    schema_editor.execute('DROP FUNCTION psl_leadership_scope_origin_guard()', params=None)
    for name, signature in reversed(LEGACY_FUNCTIONS):
        schema_editor.execute(f'DROP FUNCTION {name}({signature})', params=None)
        schema_editor.execute(f'ALTER FUNCTION {name}_selected({signature}) RENAME TO {name}', params=None)
    for signature in ('psl_leadership_project_scope(uuid,jsonb)', 'psl_leadership_scope_policy(uuid,bigint)',
                      'psl_leadership_scope_sources(uuid,timestamptz,timestamptz,jsonb)',
                      'psl_leadership_project_citations(jsonb,jsonb)', 'psl_leadership_project_summary(jsonb)'):
        schema_editor.execute(f'DROP FUNCTION {signature}', params=None)


class Migration(migrations.Migration):
    dependencies = [('workflows', '0091_ppe_opening_owner')]
    operations = [migrations.RunPython(forwards, backwards)]
