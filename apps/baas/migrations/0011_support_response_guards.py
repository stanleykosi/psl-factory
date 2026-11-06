from django.db import migrations
class Migration(migrations.Migration):
 dependencies=[('baas','0010_supportresponsedecision_supportresponsepacket_and_more')]
 operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON baas_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON baas_{name}') for name in ['supportresponsepacket','supportresponsedecision','supportresponsereceipt']]+[migrations.RunSQL("""
 CREATE FUNCTION psl_support_response_intent_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='DELETE' OR (NEW.packet_id,NEW.decision_id) IS DISTINCT FROM (OLD.packet_id,OLD.decision_id) THEN RAISE EXCEPTION 'Immutable response delivery intent'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_intent BEFORE UPDATE OR DELETE ON baas_supportresponsejob FOR EACH ROW EXECUTE FUNCTION psl_support_response_intent_guard();
 ""","DROP TRIGGER psl_intent ON baas_supportresponsejob; DROP FUNCTION psl_support_response_intent_guard();")]
