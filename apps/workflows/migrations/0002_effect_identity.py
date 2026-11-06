from django.db import migrations

SQL = """
CREATE FUNCTION psl_effect_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.operation_key IS DISTINCT FROM OLD.operation_key OR NEW.payload IS DISTINCT FROM OLD.payload
       OR NEW.actor_id IS DISTINCT FROM OLD.actor_id OR NEW.case_id IS DISTINCT FROM OLD.case_id
       OR NEW.milestone_id IS DISTINCT FROM OLD.milestone_id THEN
       RAISE EXCEPTION 'PSL reserved effect identity is immutable';
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER psl_reserved_identity BEFORE UPDATE ON workflows_outbox FOR EACH ROW EXECUTE FUNCTION psl_effect_identity();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_handoff FOR EACH ROW EXECUTE FUNCTION psl_append_only();
"""
class Migration(migrations.Migration):
    dependencies = [('workflows','0001_initial'),('finance','0001_initial'),('core','0002_append_only_history')]
    operations = [migrations.RunSQL(SQL, 'DROP TRIGGER psl_reserved_identity ON workflows_outbox; DROP FUNCTION psl_effect_identity(); DROP TRIGGER psl_immutable ON finance_handoff;')]
