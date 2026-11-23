from django.db import migrations, models


GUARD = """
CREATE FUNCTION psl_file_agent_attempt_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'File agent history cannot be deleted';
  END IF;
  IF (NEW.upload_id, NEW.actor_id, NEW.role) IS DISTINCT FROM (OLD.upload_id, OLD.actor_id, OLD.role) THEN
    RAISE EXCEPTION 'File agent source and responsible actor are immutable';
  END IF;
  IF NEW.claim_token IS DISTINCT FROM OLD.claim_token THEN
    IF OLD.status <> 'queued' OR NEW.status <> 'running' OR NEW.claim_token IS NULL
       OR NEW.attempt <> OLD.attempt + 1 OR NEW.settled_token IS NOT NULL OR NEW.started_at IS NULL THEN
      RAISE EXCEPTION 'A fresh file agent claim must start the next queued attempt';
    END IF;
  ELSIF NEW.attempt <> OLD.attempt THEN
    RAISE EXCEPTION 'File agent attempt number changes only with a fresh claim';
  END IF;
  IF OLD.claim_token IS NOT NULL AND OLD.status = 'running' AND NEW.status <> 'running' THEN
    IF NEW.status NOT IN ('draft', 'held', 'interrupted') OR NEW.settled_token IS DISTINCT FROM OLD.claim_token THEN
      RAISE EXCEPTION 'File agent completion must settle its current claim';
    END IF;
  END IF;
  IF NEW.settled_token IS DISTINCT FROM OLD.settled_token
     AND NOT (OLD.status = 'queued' AND NEW.status = 'running' AND NEW.settled_token IS NULL)
     AND NOT (OLD.status = 'running' AND NEW.status IN ('draft', 'held', 'interrupted')
              AND NEW.settled_token IS NOT DISTINCT FROM OLD.claim_token) THEN
    RAISE EXCEPTION 'File agent settlement does not match its current attempt';
  END IF;
  IF OLD.status = 'reviewed' AND NEW.status <> 'reviewed' THEN
    RAISE EXCEPTION 'Reviewed file evidence must be retained';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER psl_file_agent_attempt BEFORE UPDATE OR DELETE ON agents_agentjob
FOR EACH ROW EXECUTE FUNCTION psl_file_agent_attempt_guard();
"""


class Migration(migrations.Migration):
    dependencies = [('agents', '0011_rfp_answer_review')]
    operations = [
        migrations.AddField(model_name='agentjob', name='attempt', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='agentjob', name='claim_token', field=models.UUIDField(null=True, unique=True)),
        migrations.AddField(model_name='agentjob', name='settled_token', field=models.UUIDField(null=True)),
        migrations.RunSQL(GUARD, 'DROP TRIGGER psl_file_agent_attempt ON agents_agentjob; DROP FUNCTION psl_file_agent_attempt_guard();'),
    ]
