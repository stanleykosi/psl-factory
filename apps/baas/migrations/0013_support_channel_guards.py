from django.db import migrations
class Migration(migrations.Migration):
 dependencies=[('baas','0012_supportchannelclaim_supportchannelcheck_and_more')]
 operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON baas_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON baas_{name}') for name in ['supportchannelclaim','supportchannelreceipt','supportchannelreview','supportclockattestation']]+[migrations.RunSQL("""
 CREATE FUNCTION psl_support_channel_intent_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='DELETE' OR (NEW.claim_id,NEW.actor_id,NEW.intent_key,NEW.operation_key,NEW.intent,NEW.created_at) IS DISTINCT FROM (OLD.claim_id,OLD.actor_id,OLD.intent_key,OLD.operation_key,OLD.intent,OLD.created_at) THEN RAISE EXCEPTION 'Immutable support channel check intent'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_intent BEFORE UPDATE OR DELETE ON baas_supportchannelcheck FOR EACH ROW EXECUTE FUNCTION psl_support_channel_intent_guard();
 ""","DROP TRIGGER psl_intent ON baas_supportchannelcheck; DROP FUNCTION psl_support_channel_intent_guard();")]
