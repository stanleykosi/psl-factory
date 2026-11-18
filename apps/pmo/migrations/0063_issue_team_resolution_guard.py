from django.db import migrations


SQL = """
CREATE FUNCTION psl_issue_team_reply_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE source_state pmo_issuestate%ROWTYPE; owner_assignment pmo_issueteamassignment%ROWTYPE;
        project uuid;
BEGIN
 SELECT * INTO source_state FROM pmo_issuestate WHERE id=NEW.state_id;
 SELECT case_id INTO project FROM pmo_issue WHERE id=source_state.issue_id;
 SELECT * INTO owner_assignment FROM pmo_issueteamassignment WHERE id=NEW.assignment_id;
 IF project IS DISTINCT FROM (SELECT case_id FROM core_evidence WHERE id=NEW.evidence_id)
    OR owner_assignment.issue_id IS DISTINCT FROM source_state.issue_id OR owner_assignment.mode<>'team'
    OR owner_assignment.team_key='' OR NEW.actor_id IS DISTINCT FROM owner_assignment.recorder_id
    OR NEW.actor_id IS DISTINCT FROM source_state.actor_id OR NEW.evidence_id IS DISTINCT FROM source_state.evidence_id
    OR source_state.owner_id IS DISTINCT FROM owner_assignment.recorder_id
    OR NEW.operation NOT IN ('acknowledge','start','progress','resolve') OR length(trim(NEW.party))=0
    OR length(trim(NEW.source_ref))=0 OR NEW.responded_at>statement_timestamp()
    OR NEW.intent_sha256 !~ '^[a-f0-9]{64}$' OR NEW.proof_sha256 IS DISTINCT FROM
      (SELECT sha256 FROM core_evidence WHERE id=NEW.evidence_id)
 THEN RAISE EXCEPTION 'PSL invalid external issue reply'; END IF;
 IF NEW.operation='resolve' THEN
  IF source_state.status<>'Resolved' OR source_state.resolved_at IS NULL OR source_state.acknowledged_at IS NULL
     OR source_state.severity IS NULL OR source_state.fix_id IS NULL
     OR NOT EXISTS (SELECT 1 FROM core_evidence WHERE id=source_state.fix_id AND case_id=project AND kind='resolution')
     OR (source_state.severity='Critical' AND source_state.root_cause_id IS NULL)
     OR (source_state.root_cause_id IS NOT NULL AND NOT EXISTS
       (SELECT 1 FROM core_evidence WHERE id=source_state.root_cause_id AND case_id=project AND kind='root_cause'))
     OR NEW.authority->>'protocol' IS DISTINCT FROM 'issue-team-resolution-authority/v1'
     OR jsonb_typeof(NEW.authority->'role') IS DISTINCT FROM 'string'
     OR jsonb_typeof(NEW.authority->'policies') IS DISTINCT FROM 'object'
  THEN RAISE EXCEPTION 'PSL external resolution needs exact fix and recorder authority'; END IF;
 ELSIF NEW.authority IS DISTINCT FROM owner_assignment.authority THEN
  RAISE EXCEPTION 'PSL external reply needs exact assignment authority';
 END IF;
 RETURN NEW;
END; $$;
DROP TRIGGER psl_issue_team_scope ON pmo_issueteamreply;
CREATE TRIGGER psl_issue_team_scope BEFORE INSERT ON pmo_issueteamreply
 FOR EACH ROW EXECUTE FUNCTION psl_issue_team_reply_guard();
"""


class Migration(migrations.Migration):
    dependencies = [('pmo', '0062_issue_team_guards')]
    operations = [migrations.RunSQL(SQL, """
        DROP TRIGGER psl_issue_team_scope ON pmo_issueteamreply;
        CREATE TRIGGER psl_issue_team_scope BEFORE INSERT ON pmo_issueteamreply
          FOR EACH ROW EXECUTE FUNCTION psl_issue_team_guard();
        DROP FUNCTION psl_issue_team_reply_guard();
    """)]
