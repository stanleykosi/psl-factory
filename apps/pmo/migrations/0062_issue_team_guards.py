from django.db import migrations


SQL = """
CREATE FUNCTION psl_issue_team_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE source_state pmo_issuestate%ROWTYPE; owner_assignment pmo_issueteamassignment%ROWTYPE;
        project uuid; proof_case uuid;
BEGIN
 SELECT * INTO source_state FROM pmo_issuestate WHERE id=NEW.state_id;
 SELECT case_id INTO project FROM pmo_issue WHERE id=source_state.issue_id;
 SELECT case_id INTO proof_case FROM core_evidence WHERE id=NEW.evidence_id;
 IF project IS DISTINCT FROM proof_case THEN RAISE EXCEPTION 'PSL issue team proof outside project'; END IF;
 IF TG_TABLE_NAME='pmo_issueteamassignment' THEN
  IF NEW.issue_id IS DISTINCT FROM source_state.issue_id OR NEW.recorder_id IS DISTINCT FROM source_state.owner_id
     OR NEW.state_id IS DISTINCT FROM (SELECT current_id FROM pmo_issue WHERE id=NEW.issue_id)
     OR NEW.actor_id IS DISTINCT FROM source_state.actor_id OR NEW.evidence_id IS DISTINCT FROM source_state.evidence_id
     OR NEW.mode NOT IN ('team','internal') OR length(trim(NEW.reason))=0
     OR jsonb_typeof(NEW.authority) IS DISTINCT FROM 'object'
  THEN RAISE EXCEPTION 'PSL invalid issue team assignment'; END IF;
  IF NEW.mode='internal' OR NEW.team_key='' THEN
   IF NEW.team_key<>'' OR NEW.team_label<>'' OR NEW.recorder_role<>'' OR NEW.policy_id IS NOT NULL OR NEW.authority<>'{}'::jsonb
   THEN RAISE EXCEPTION 'PSL invalid unassigned issue team'; END IF;
  ELSIF NEW.policy_id IS NULL OR NEW.team_label='' OR NEW.recorder_role='' OR NOT EXISTS
    (SELECT 1 FROM policy_configuration WHERE id=NEW.policy_id AND case_id=project AND component='OPS.issue_team_controls')
   THEN RAISE EXCEPTION 'PSL issue team needs exact project controls';
  END IF;
  IF NEW.auto_work_id IS NULL THEN
   IF NEW.requested_source_id IS NOT NULL OR NEW.work_input<>'{}'::jsonb
   THEN RAISE EXCEPTION 'PSL incomplete issue source update'; END IF;
  ELSIF NEW.requested_source_id IS NULL OR NOT EXISTS (
    SELECT 1 FROM workflows_factorywork w JOIN core_evidence e ON e.id=NEW.requested_source_id
    WHERE w.id=NEW.auto_work_id AND w.case_id=project AND e.case_id=project
      AND w.definition='pmo-issues/v1' AND (w.request->>'issue_id')::bigint=NEW.issue_id
      AND w.source_head_id=NEW.requested_source_id
      AND NEW.work_input->>'protocol'='factory-issue-intake/v1'
      AND (NEW.work_input->>'issue_id')::bigint=NEW.issue_id
      AND (NEW.work_input->>'state_id')::bigint=NEW.state_id)
   THEN RAISE EXCEPTION 'PSL invalid issue source update';
  END IF;
 ELSE
  SELECT * INTO owner_assignment FROM pmo_issueteamassignment WHERE id=NEW.assignment_id;
  IF owner_assignment.issue_id IS DISTINCT FROM source_state.issue_id OR owner_assignment.mode<>'team'
     OR owner_assignment.team_key='' OR NEW.actor_id IS DISTINCT FROM owner_assignment.recorder_id
     OR NEW.actor_id IS DISTINCT FROM source_state.actor_id OR NEW.evidence_id IS DISTINCT FROM source_state.evidence_id
     OR NEW.operation NOT IN ('acknowledge','start','progress') OR length(trim(NEW.party))=0
     OR length(trim(NEW.source_ref))=0 OR NEW.responded_at>statement_timestamp()
     OR NEW.intent_sha256 !~ '^[a-f0-9]{64}$' OR NEW.proof_sha256 IS DISTINCT FROM
       (SELECT sha256 FROM core_evidence WHERE id=NEW.evidence_id)
  THEN RAISE EXCEPTION 'PSL invalid external issue reply'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER psl_issue_team_scope BEFORE INSERT ON pmo_issueteamassignment
 FOR EACH ROW EXECUTE FUNCTION psl_issue_team_guard();
CREATE TRIGGER psl_issue_team_scope BEFORE INSERT ON pmo_issueteamreply
 FOR EACH ROW EXECUTE FUNCTION psl_issue_team_guard();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON pmo_issueteamassignment
 FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON pmo_issueteamreply
 FOR EACH ROW EXECUTE FUNCTION psl_append_only();
"""


class Migration(migrations.Migration):
    dependencies = [('pmo', '0061_issue_team_ownership')]
    operations = [migrations.RunSQL(SQL, """
        DROP TRIGGER psl_immutable ON pmo_issueteamreply;
        DROP TRIGGER psl_immutable ON pmo_issueteamassignment;
        DROP TRIGGER psl_issue_team_scope ON pmo_issueteamreply;
        DROP TRIGGER psl_issue_team_scope ON pmo_issueteamassignment;
        DROP FUNCTION psl_issue_team_guard();
    """)]
