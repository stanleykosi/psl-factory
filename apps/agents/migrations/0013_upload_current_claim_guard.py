from django.db import migrations


GUARD = """
CREATE FUNCTION psl_file_agent_current_claim_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'queued' AND NEW.status = 'running'
     AND (NEW.claim_token IS NULL OR NEW.claim_token IS NOT DISTINCT FROM OLD.claim_token) THEN
    RAISE EXCEPTION 'File review requires a fresh worker claim; upgrade the worker';
  END IF;
  IF OLD.status = 'running' AND OLD.claim_token IS NULL AND NEW.status IN ('draft', 'held') THEN
    RAISE EXCEPTION 'A legacy running review needs explicit recovery before accepting a result';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER psl_file_agent_current_claim BEFORE UPDATE ON agents_agentjob
FOR EACH ROW EXECUTE FUNCTION psl_file_agent_current_claim_guard();
"""


class Migration(migrations.Migration):
    dependencies = [('agents', '0012_upload_attempt_fencing')]
    operations = [migrations.RunSQL(GUARD,
        'DROP TRIGGER psl_file_agent_current_claim ON agents_agentjob; DROP FUNCTION psl_file_agent_current_claim_guard();')]
