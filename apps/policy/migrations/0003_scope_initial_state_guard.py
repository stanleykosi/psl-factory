"""Forward-only repair: SQL three-valued logic must reject an invalid initial state."""
from django.db import migrations

SQL="""
CREATE FUNCTION psl_policy_scope_initial_state_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE previous text;
BEGIN
 PERFORM 1 FROM policy_scopeversion WHERE id=NEW.source_id FOR UPDATE;
 SELECT state INTO previous FROM policy_scopestate WHERE source_id=NEW.source_id ORDER BY id DESC LIMIT 1;
 IF NOT coalesce((previous IS NULL AND NEW.state='draft') OR (previous='draft' AND NEW.state='validated')
  OR (previous='validated' AND NEW.state='active') OR (previous='active' AND NEW.state IN ('revoked','superseded')),false)
 THEN RAISE EXCEPTION 'PSL invalid initial or successor scope state'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER psl_scope_initial_state BEFORE INSERT ON policy_scopestate FOR EACH ROW EXECUTE FUNCTION psl_policy_scope_initial_state_guard();
"""
class Migration(migrations.Migration):
    dependencies=[('policy','0002_scopeversion_scopestate_scopeapplication')]
    operations=[migrations.RunSQL(SQL,'DROP TRIGGER psl_scope_initial_state ON policy_scopestate; DROP FUNCTION psl_policy_scope_initial_state_guard();')]
