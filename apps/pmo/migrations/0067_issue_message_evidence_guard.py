from django.db import migrations


SQL="""
CREATE FUNCTION psl_issue_message_evidence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE project uuid; started timestamptz;
BEGIN
 SELECT i.case_id INTO project FROM pmo_issuemessagedispatch x
 JOIN pmo_issuemessagereview r ON r.id=x.review_id JOIN pmo_issuemessagedraft d ON d.id=r.draft_id
 JOIN pmo_issue i ON i.id=d.issue_id WHERE x.id=NEW.dispatch_id;
 SELECT created_at INTO started FROM pmo_issuemessageattempt WHERE dispatch_id=NEW.dispatch_id;
 IF project IS NULL OR started IS NULL OR NEW.delivered_at<started OR NEW.delivered_at>statement_timestamp()
    OR NOT NEW.delivered AND NEW.delivered_at IS NOT NULL
 THEN RAISE EXCEPTION 'PSL message receipt outside its original controlled send'; END IF;
 IF TG_TABLE_NAME='pmo_syntheticissuemessage' THEN
  IF NEW.delivered AND NEW.delivered_at IS NULL OR NEW.observed_at>statement_timestamp()
  THEN RAISE EXCEPTION 'PSL invalid provider delivery or absence fence'; END IF;
 ELSE
  IF NEW.source_evidence_id IS NULL THEN
   IF NEW.source_sha256<>'' THEN RAISE EXCEPTION 'PSL incomplete message supporting source'; END IF;
  ELSIF NOT EXISTS (SELECT 1 FROM core_evidence WHERE id=NEW.source_evidence_id AND case_id=project
       AND sha256=NEW.source_sha256 AND kind IN ('document','support_message','project_artifact','issue_delivery_source'))
  THEN RAISE EXCEPTION 'PSL owner-message supporting source outside exact project evidence';
  END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER psl_issue_message_evidence BEFORE INSERT ON pmo_issuemessagereceipt
 FOR EACH ROW EXECUTE FUNCTION psl_issue_message_evidence_guard();
CREATE TRIGGER psl_issue_message_evidence BEFORE INSERT ON pmo_syntheticissuemessage
 FOR EACH ROW EXECUTE FUNCTION psl_issue_message_evidence_guard();
"""


class Migration(migrations.Migration):
    dependencies=[('pmo','0066_issue_message_recovery_evidence')]
    operations=[migrations.RunSQL(SQL,"""
        DROP TRIGGER psl_issue_message_evidence ON pmo_syntheticissuemessage;
        DROP TRIGGER psl_issue_message_evidence ON pmo_issuemessagereceipt;
        DROP FUNCTION psl_issue_message_evidence_guard();
    """)]
