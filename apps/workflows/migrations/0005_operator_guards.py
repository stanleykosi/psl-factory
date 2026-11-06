from django.db import migrations
class Migration(migrations.Migration):
 dependencies=[('workflows','0004_recoveryjob_recoveryartifact_recoveryplan_and_more')]
 operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON workflows_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON workflows_{name}') for name in ['operatorinventory','recoveryplan','recoveryproof','recoveryartifact','recoveryassessment','recoveryreview']]+[migrations.RunSQL("""
 CREATE FUNCTION psl_protection_intent_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='DELETE' OR (NEW.plan_id,NEW.kind,NEW.generation,NEW.operation_key,NEW.intent,NEW.actor_id,NEW.created_at) IS DISTINCT FROM (OLD.plan_id,OLD.kind,OLD.generation,OLD.operation_key,OLD.intent,OLD.actor_id,OLD.created_at) THEN RAISE EXCEPTION 'Immutable protection intent'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_intent BEFORE UPDATE OR DELETE ON workflows_recoveryjob FOR EACH ROW EXECUTE FUNCTION psl_protection_intent_guard();
 ""","DROP TRIGGER psl_intent ON workflows_recoveryjob; DROP FUNCTION psl_protection_intent_guard();")]
