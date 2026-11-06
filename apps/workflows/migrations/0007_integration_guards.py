from django.db import migrations
class Migration(migrations.Migration):
 dependencies=[('workflows','0006_integrationcontract_integrationassessment_and_more')]
 operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON workflows_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON workflows_{name}') for name in ['integrationcontract','integrationobservation','integrationassessment','integrationreview','integrationselection']]+[migrations.RunSQL("""
 CREATE FUNCTION psl_integration_intent_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='DELETE' OR (NEW.contract_id,NEW.operation_key,NEW.intent_key,NEW.intent,NEW.actor_id,NEW.created_at) IS DISTINCT FROM (OLD.contract_id,OLD.operation_key,OLD.intent_key,OLD.intent,OLD.actor_id,OLD.created_at) THEN RAISE EXCEPTION 'Immutable integration probe intent'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_intent BEFORE UPDATE OR DELETE ON workflows_integrationprobe FOR EACH ROW EXECUTE FUNCTION psl_integration_intent_guard();
 ""","DROP TRIGGER psl_intent ON workflows_integrationprobe; DROP FUNCTION psl_integration_intent_guard();")]
