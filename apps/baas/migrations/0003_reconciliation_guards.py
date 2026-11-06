from django.db import migrations

class Migration(migrations.Migration):
    dependencies=[('baas','0002_correctiverequest_correctivejob_correctivedelivery_and_more')]
    operations=[migrations.RunSQL(
        f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON baas_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',
        f'DROP TRIGGER psl_immutable ON baas_{name}') for name in ['reconciliationbatch','reconciliationattestation','reconciliationrun','correctiverequest','correctivedecision','correctivedelivery','engineeringoutcome','outcomeverification']]+[
        migrations.RunSQL('''CREATE FUNCTION psl_corrective_job_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Corrective history is append-only'; END IF;
          IF (NEW.request_id,NEW.generation,NEW.intent,NEW.actor_id,NEW.tenant,NEW.operation_key,NEW.subject_key)
             IS DISTINCT FROM (OLD.request_id,OLD.generation,OLD.intent,OLD.actor_id,OLD.tenant,OLD.operation_key,OLD.subject_key)
          THEN RAISE EXCEPTION 'Corrective job intent is immutable'; END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER psl_corrective_job BEFORE UPDATE OR DELETE ON baas_correctivejob FOR EACH ROW EXECUTE FUNCTION psl_corrective_job_guard();''',
        'DROP TRIGGER psl_corrective_job ON baas_correctivejob; DROP FUNCTION psl_corrective_job_guard();')]
