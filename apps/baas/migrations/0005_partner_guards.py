from django.db import migrations

class Migration(migrations.Migration):
    dependencies=[('baas','0004_partnerfinancejob_partnerfinancereceipt_and_more')]
    operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON baas_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON baas_{name}') for name in ['partnerrecord','partnerdecision','onboardingevent','partnerreport','partnerreportreview','partnerfollowup','partnerfinancereceipt','partnerbillingimport','partnermeterclaim']]+[
        migrations.RunSQL('''CREATE FUNCTION psl_partner_job_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Partner job history is append-only'; END IF;
          IF (NEW.report_id,NEW.generation,NEW.intent,NEW.actor_id) IS DISTINCT FROM (OLD.report_id,OLD.generation,OLD.intent,OLD.actor_id)
          THEN RAISE EXCEPTION 'Partner job intent is immutable'; END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER psl_partner_job BEFORE UPDATE OR DELETE ON baas_partnerfinancejob FOR EACH ROW EXECUTE FUNCTION psl_partner_job_guard();''','DROP TRIGGER psl_partner_job ON baas_partnerfinancejob; DROP FUNCTION psl_partner_job_guard();')]
