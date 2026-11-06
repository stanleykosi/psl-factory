from django.db import migrations
class Migration(migrations.Migration):
 dependencies=[('pmo','0034_approvalcontractreview_approvalobservation_and_more')]
 operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON pmo_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON pmo_{name}') for name in ['approvalrequest','approvalcontractreview','approvalroutereceipt','approvalsourcereceipt','approvalobservation','approvalgatebinding']]+[migrations.RunSQL("""
 CREATE FUNCTION psl_approval_route_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='DELETE' OR (NEW.request_id,NEW.actor_id,NEW.generation,NEW.purpose,NEW.operation_key,NEW.intent,NEW.created_at) IS DISTINCT FROM (OLD.request_id,OLD.actor_id,OLD.generation,OLD.purpose,OLD.operation_key,OLD.intent,OLD.created_at) THEN RAISE EXCEPTION 'Immutable prerequisite routing intent'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_intent BEFORE UPDATE OR DELETE ON pmo_approvalroutejob FOR EACH ROW EXECUTE FUNCTION psl_approval_route_guard();
 ""","DROP TRIGGER psl_intent ON pmo_approvalroutejob; DROP FUNCTION psl_approval_route_guard();")]
