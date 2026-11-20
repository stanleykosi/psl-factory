from django.db import migrations, models
from django.db.models import PROTECT


GUARD = """
CREATE FUNCTION psl_rfp_loss_provenance() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE project uuid;
BEGIN
 IF NEW.loss_reason='{}'::jsonb AND NEW.debrief_version_id IS NULL THEN RETURN NEW; END IF;
 SELECT r.case_id INTO project FROM pmo_rfpsubmission s
 JOIN pmo_rfpresponse v ON v.id=s.response_id JOIN pmo_rfpcase r ON r.id=v.rfp_id
 WHERE s.id=NEW.submission_id;
 IF NEW.result<>'lost' OR NOT EXISTS(SELECT 1 FROM core_evidence e
   WHERE e.id=NEW.evidence_id AND e.case_id=project AND e.kind='rfp_outcome')
   OR NOT EXISTS(SELECT 1 FROM auth_user u WHERE u.id=NEW.actor_id AND u.is_active)
   OR EXISTS(SELECT 1 FROM unnest(ARRAY['case.read','rfp.read','rfp.outcome']) AS needed(action)
    WHERE NOT EXISTS(SELECT 1 FROM identity_grant g WHERE g.user_id=NEW.actor_id AND g.case_id=project
     AND g.active AND g.action=needed.action)) THEN
  RAISE EXCEPTION 'Exact same-project customer loss evidence required';
 END IF;
 IF NEW.loss_reason<>'{}'::jsonb THEN
  IF jsonb_typeof(NEW.loss_reason) IS DISTINCT FROM 'object'
     OR NOT(NEW.loss_reason ?& ARRAY['configuration','key','label'])
     OR NEW.loss_reason-ARRAY['configuration','key','label']<>'{}'::jsonb
     OR jsonb_typeof(NEW.loss_reason->'configuration') IS DISTINCT FROM 'number'
     OR COALESCE(NEW.loss_reason->>'configuration','') !~ '^[1-9][0-9]{0,17}$'
     OR jsonb_typeof(NEW.loss_reason->'key') IS DISTINCT FROM 'string'
     OR jsonb_typeof(NEW.loss_reason->'label') IS DISTINCT FROM 'string' THEN
   RAISE EXCEPTION 'Closed exact loss reason provenance required';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM policy_configuration c
   JOIN policy_registeredreference rr ON rr.case_id=project
    AND rr.ref=(c.envelope->'value'->>'artifact_ref') AND rr.sha256=(c.envelope->'value'->>'sha256')
    AND rr.version::text=(c.envelope->'value'->>'artifact_version')
   WHERE c.id=(NEW.loss_reason->>'configuration')::bigint AND c.case_id=project AND c.component='OPS.rfp_loss_catalog'
    AND rr.schema_ref='schema:psl/rfp-loss-catalog/v1'
    AND (SELECT state FROM policy_policystate WHERE configuration_id=c.id ORDER BY id DESC LIMIT 1)='active'
    AND (c.envelope->>'effective_from')::timestamptz<=NEW.created_at
    AND (c.envelope->>'effective_until' IS NULL OR (c.envelope->>'effective_until')::timestamptz>NEW.created_at)
    AND NOT EXISTS(SELECT 1 FROM policy_scopeapplication a JOIN policy_scopeversion s ON s.id=a.source_id
     JOIN policy_configuration origin ON origin.id=s.configuration_id
     WHERE a.configuration_id=c.id AND (
      (SELECT state FROM policy_scopestate WHERE source_id=s.id ORDER BY id DESC LIMIT 1) IS DISTINCT FROM 'active'
      OR EXISTS(SELECT 1 FROM unnest(ARRAY['case.read','policy.read']) AS needed(action)
       WHERE NOT EXISTS(SELECT 1 FROM identity_grant g WHERE g.user_id=NEW.actor_id AND g.case_id=origin.case_id
        AND g.active AND g.action=needed.action))))
    AND (rr.content->'reasons') @> jsonb_build_array(NEW.loss_reason-'configuration')) THEN
   RAISE EXCEPTION 'The recorded loss reason must match the exact active reviewed catalog';
  END IF;
 END IF;
 IF NEW.debrief_version_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM pmo_meetingversion v
   JOIN pmo_meeting m ON m.id=v.meeting_id AND m.current_id=v.id
   JOIN core_evidence e ON e.id=v.evidence_id AND e.case_id=project
   WHERE v.id=NEW.debrief_version_id AND m.case_id=project AND v.kind='retrospective' AND v.occurred_at<=NEW.created_at
    AND EXISTS(SELECT 1 FROM identity_grant g WHERE g.user_id=NEW.actor_id AND g.case_id=project AND g.active
     AND g.action='meeting.read')) THEN
  RAISE EXCEPTION 'A recorded same-project debrief and current meeting access are required';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_rfp_loss_proof BEFORE INSERT ON pmo_rfpoutcome
 FOR EACH ROW EXECUTE FUNCTION psl_rfp_loss_provenance();
"""


class Migration(migrations.Migration):
    dependencies = [('pmo', '0076_rfp_exact_reminder_time'), ('policy', '0002_scopeversion_scopestate_scopeapplication')]

    operations = [
        migrations.AddField('rfpoutcome', 'loss_reason', models.JSONField(blank=True, default=dict)),
        migrations.AddField('rfpoutcome', 'debrief_version', models.ForeignKey(
            blank=True, null=True, on_delete=PROTECT, to='pmo.meetingversion')),
        migrations.RunSQL(GUARD, 'DROP TRIGGER psl_rfp_loss_proof ON pmo_rfpoutcome; DROP FUNCTION psl_rfp_loss_provenance();'),
    ]
