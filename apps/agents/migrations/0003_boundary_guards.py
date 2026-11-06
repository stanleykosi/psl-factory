from django.db import migrations

class Migration(migrations.Migration):
 dependencies=[('agents','0002_evidenceextraction_evidenceextractionreceipt_and_more'),('workflows','0007_integration_guards')]
 operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON agents_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON agents_{name}') for name in ['evidenceprojection','evidenceprojectionreview','evidenceextractionreceipt','evidenceextractionreview']]+[migrations.RunSQL("""
 CREATE FUNCTION psl_agent_intent_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='DELETE' OR (NEW.projection_id,NEW.operation_key,NEW.intent_key,NEW.intent,NEW.actor_id,NEW.created_at) IS DISTINCT FROM (OLD.projection_id,OLD.operation_key,OLD.intent_key,OLD.intent,OLD.actor_id,OLD.created_at) THEN RAISE EXCEPTION 'Immutable private extraction intent'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_intent BEFORE UPDATE OR DELETE ON agents_evidenceextraction FOR EACH ROW EXECUTE FUNCTION psl_agent_intent_guard();
 ""","DROP TRIGGER psl_intent ON agents_evidenceextraction; DROP FUNCTION psl_agent_intent_guard();")]
