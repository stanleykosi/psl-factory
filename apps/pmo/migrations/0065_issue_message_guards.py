from django.db import migrations


SQL = """
CREATE FUNCTION psl_issue_message_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE project uuid; proof_project uuid; item pmo_issue%ROWTYPE;
        draft pmo_issuemessagedraft%ROWTYPE; review pmo_issuemessagereview%ROWTYPE;
        released pmo_issuemessagedispatch%ROWTYPE; prior_id bigint; prior_number integer;
BEGIN
 IF TG_TABLE_NAME='pmo_issuemessagedraft' THEN
  SELECT * INTO item FROM pmo_issue WHERE id=NEW.issue_id;
  project=item.case_id;
  SELECT id,number INTO prior_id,prior_number FROM pmo_issuemessagedraft
    WHERE issue_id=NEW.issue_id ORDER BY number DESC LIMIT 1;
  IF NEW.state_id IS DISTINCT FROM item.current_id
     OR NOT EXISTS (SELECT 1 FROM pmo_issuestate s JOIN pmo_issueteamassignment a ON a.issue_id=s.issue_id
       WHERE s.id=NEW.state_id AND a.id=NEW.assignment_id AND a.mode='team' AND a.team_key<>''
         AND s.owner_id=a.recorder_id AND s.status IN ('Open','In Progress')
         AND a.id=(SELECT id FROM pmo_issueteamassignment WHERE issue_id=NEW.issue_id ORDER BY number DESC LIMIT 1))
     OR NEW.previous_id IS DISTINCT FROM prior_id OR NEW.number<>COALESCE(prior_number,0)+1
     OR NEW.kind NOT IN ('request','reminder') OR length(trim(NEW.body))=0 OR length(NEW.body)>4000
     OR length(trim(NEW.reason))=0 OR NEW.sha256 !~ '^[a-f0-9]{64}$'
     OR NEW.intent_sha256 !~ '^[a-f0-9]{64}$'
     OR NEW.source->>'protocol' IS DISTINCT FROM 'issue-owner-message-source/v1'
     OR (NEW.source->>'issue_id')::bigint IS DISTINCT FROM NEW.issue_id
     OR (NEW.source->>'state_id')::bigint IS DISTINCT FROM NEW.state_id
     OR (NEW.source->>'assignment_id')::bigint IS DISTINCT FROM NEW.assignment_id
  THEN RAISE EXCEPTION 'PSL invalid current owner-message draft'; END IF;
  IF NEW.kind='request' AND NEW.previous_release_id IS NOT NULL
     OR NEW.kind='reminder' AND NOT EXISTS (
       SELECT 1 FROM pmo_issuemessagedispatch x JOIN pmo_issuemessagereview r ON r.id=x.review_id
       JOIN pmo_issuemessagedraft d ON d.id=r.draft_id JOIN pmo_issuemessagereceipt e ON e.dispatch_id=x.id
       WHERE x.id=NEW.previous_release_id AND d.issue_id=NEW.issue_id AND d.state_id=NEW.state_id
         AND d.assignment_id=NEW.assignment_id AND e.delivered)
  THEN RAISE EXCEPTION 'PSL reminder needs an exact delivered owner request'; END IF;
  IF NEW.run_id IS NOT NULL AND NOT EXISTS
    (SELECT 1 FROM agents_agentrun WHERE id=NEW.run_id AND case_id=project AND actor_id=NEW.actor_id)
  THEN RAISE EXCEPTION 'PSL message agent outside source project'; END IF;
 ELSIF TG_TABLE_NAME='pmo_issuemessagereview' THEN
  SELECT * INTO draft FROM pmo_issuemessagedraft WHERE id=NEW.draft_id;
  SELECT * INTO item FROM pmo_issue WHERE id=draft.issue_id;
  project=item.case_id;
  IF NEW.verdict NOT IN ('approve','return','reject') OR NEW.role='' OR length(trim(NEW.note))=0
     OR draft.state_id IS DISTINCT FROM item.current_id OR draft.id IS DISTINCT FROM
       (SELECT id FROM pmo_issuemessagedraft WHERE issue_id=item.id ORDER BY number DESC LIMIT 1)
     OR jsonb_typeof(NEW.authority) IS DISTINCT FROM 'object'
     OR NOT EXISTS (SELECT 1 FROM policy_configuration WHERE id=NEW.configuration_id AND case_id=project
                     AND component='OPS.issue_message_controls')
  THEN RAISE EXCEPTION 'PSL invalid owner-message review'; END IF;
 ELSIF TG_TABLE_NAME='pmo_issuemessagedispatch' THEN
  SELECT * INTO review FROM pmo_issuemessagereview WHERE id=NEW.review_id;
  SELECT * INTO draft FROM pmo_issuemessagedraft WHERE id=review.draft_id;
  SELECT * INTO item FROM pmo_issue WHERE id=draft.issue_id;
  project=item.case_id;
  IF review.verdict IS DISTINCT FROM 'approve' OR review.configuration_id IS DISTINCT FROM NEW.configuration_id
     OR draft.state_id IS DISTINCT FROM item.current_id OR draft.id IS DISTINCT FROM
       (SELECT id FROM pmo_issuemessagedraft WHERE issue_id=item.id ORDER BY number DESC LIMIT 1)
     OR NEW.role='' OR jsonb_typeof(NEW.authority) IS DISTINCT FROM 'object'
     OR COALESCE(NEW.route->>'mode','') NOT IN ('synthetic_mailbox','manual_evidence')
     OR COALESCE(NEW.route->>'channel','') NOT IN ('email','whatsapp','ticket')
     OR length(trim(COALESCE(NEW.route->>'destination','')))=0
     OR NEW.route->>'channel' IS DISTINCT FROM NEW.payload->>'channel'
     OR NEW.route->>'destination' IS DISTINCT FROM NEW.payload->>'recipient'
     OR NEW.payload->>'body' IS DISTINCT FROM draft.body
     OR NEW.payload->>'issue_reference' IS DISTINCT FROM item.reference
     OR NEW.sha256 !~ '^[a-f0-9]{64}$' OR NEW.intent_sha256 !~ '^[a-f0-9]{64}$'
  THEN RAISE EXCEPTION 'PSL message release needs exact reviewed content and destination'; END IF;
 ELSE
  SELECT * INTO released FROM pmo_issuemessagedispatch WHERE id=NEW.dispatch_id;
  SELECT * INTO review FROM pmo_issuemessagereview WHERE id=released.review_id;
  SELECT * INTO draft FROM pmo_issuemessagedraft WHERE id=review.draft_id;
  SELECT * INTO item FROM pmo_issue WHERE id=draft.issue_id;
  project=item.case_id;
  IF TG_TABLE_NAME='pmo_issuemessageattempt' THEN
   IF EXISTS (SELECT 1 FROM pmo_issuemessagecancellation WHERE dispatch_id=NEW.dispatch_id)
      OR released.not_before>statement_timestamp()
   THEN RAISE EXCEPTION 'PSL owner message is cancelled or not yet due'; END IF;
  ELSIF TG_TABLE_NAME='pmo_issuemessagecancellation' THEN
   IF EXISTS (SELECT 1 FROM pmo_issuemessageattempt WHERE dispatch_id=NEW.dispatch_id)
      OR EXISTS (SELECT 1 FROM pmo_issuemessagereceipt WHERE dispatch_id=NEW.dispatch_id)
      OR length(trim(NEW.reason))=0
   THEN RAISE EXCEPTION 'PSL reconcile a started message before cancellation'; END IF;
  ELSE
   IF NOT EXISTS (SELECT 1 FROM pmo_issuemessageattempt WHERE dispatch_id=NEW.dispatch_id)
      OR EXISTS (SELECT 1 FROM pmo_issuemessagecancellation WHERE dispatch_id=NEW.dispatch_id)
   THEN RAISE EXCEPTION 'PSL receipt needs the original started message'; END IF;
   IF TG_TABLE_NAME='pmo_syntheticissuemessage' THEN
    IF NOT (SELECT synthetic FROM core_case WHERE id=project)
       OR released.route->>'mode' IS DISTINCT FROM 'synthetic_mailbox'
       OR NEW.payload IS DISTINCT FROM released.payload OR NEW.sha256 IS DISTINCT FROM released.sha256
    THEN RAISE EXCEPTION 'PSL sample message outside its original payload'; END IF;
   ELSE
    IF NOT NEW.delivered AND NEW.delivered_at IS NOT NULL
       OR NEW.delivered_at>statement_timestamp() OR length(trim(NEW.reference))=0
       OR released.route->>'mode'='manual_evidence' AND
          (NEW.clock_source<>'human_attested' OR NOT EXISTS
            (SELECT 1 FROM core_evidence WHERE id=NEW.evidence_id AND case_id=project AND kind='issue_message_receipt'))
       OR released.route->>'mode'='synthetic_mailbox' AND
          (NEW.clock_source<>'synthetic_mailbox' OR NEW.evidence_id IS NOT NULL)
    THEN RAISE EXCEPTION 'PSL invalid exact owner-message receipt'; END IF;
   END IF;
  END IF;
 END IF;
 IF project IS NULL THEN RAISE EXCEPTION 'PSL owner message needs existing source records'; END IF;
 IF TG_TABLE_NAME IN ('pmo_issuemessagedraft','pmo_issuemessagereview','pmo_issuemessagereceipt') THEN
  IF NEW.evidence_id IS NOT NULL THEN
   SELECT case_id INTO proof_project FROM core_evidence WHERE id=NEW.evidence_id;
   IF proof_project IS DISTINCT FROM project THEN RAISE EXCEPTION 'PSL owner-message evidence outside project'; END IF;
  END IF;
 END IF;
 RETURN NEW;
END; $$;
"""

TABLES=['pmo_issuemessagedraft','pmo_issuemessagereview','pmo_issuemessagedispatch',
        'pmo_issuemessageattempt','pmo_issuemessagereceipt','pmo_issuemessagecancellation','pmo_syntheticissuemessage']

for table in TABLES:
    SQL+=f'CREATE TRIGGER psl_issue_message_scope BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION psl_issue_message_guard();\n'
    SQL+=f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION psl_append_only();\n'

REVERSE=''.join(f'DROP TRIGGER psl_issue_message_scope ON {table}; DROP TRIGGER psl_immutable ON {table};\n' for table in TABLES)
REVERSE+='DROP FUNCTION psl_issue_message_guard();'


class Migration(migrations.Migration):
    dependencies=[('pmo','0064_issue_messages')]
    operations=[migrations.RunSQL(SQL,REVERSE)]
