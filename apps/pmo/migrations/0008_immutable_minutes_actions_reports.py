from django.db import migrations

TABLES=['pmo_meetingversion','pmo_actionstate','pmo_minutesreportbinding','pmo_reportoccurrence','pmo_meetingactionlink']
def protect(apps,schema_editor):
    for table in TABLES:
        schema_editor.execute(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION psl_append_only()')
    schema_editor.execute("""CREATE FUNCTION psl_meeting_root() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF NEW.case_id IS DISTINCT FROM OLD.case_id OR NEW.reference IS DISTINCT FROM OLD.reference THEN RAISE EXCEPTION 'Immutable meeting identity'; END IF;
      IF NEW.current_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM pmo_meetingversion WHERE id=NEW.current_id AND meeting_id=NEW.id) THEN RAISE EXCEPTION 'Meeting revision belongs to another record'; END IF;
      RETURN NEW; END; $$;
      CREATE TRIGGER psl_root_identity BEFORE UPDATE ON pmo_meeting FOR EACH ROW EXECUTE FUNCTION psl_meeting_root();
      CREATE FUNCTION psl_action_root() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF NEW.case_id IS DISTINCT FROM OLD.case_id OR NEW.reference IS DISTINCT FROM OLD.reference OR NEW.meeting_id IS DISTINCT FROM OLD.meeting_id THEN RAISE EXCEPTION 'Immutable commitment identity'; END IF;
      IF NEW.current_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM pmo_actionstate WHERE id=NEW.current_id AND item_id=NEW.id) THEN RAISE EXCEPTION 'Action revision belongs to another record'; END IF;
      RETURN NEW; END; $$;
      CREATE TRIGGER psl_root_identity BEFORE UPDATE ON pmo_actionitem FOR EACH ROW EXECUTE FUNCTION psl_action_root();
      CREATE FUNCTION psl_report_root() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF NEW.case_id IS DISTINCT FROM OLD.case_id OR NEW.kind IS DISTINCT FROM OLD.kind OR NEW.start_at IS DISTINCT FROM OLD.start_at OR NEW.end_at IS DISTINCT FROM OLD.end_at OR NEW.audience IS DISTINCT FROM OLD.audience OR (OLD.document_id IS NOT NULL AND NEW.document_id IS DISTINCT FROM OLD.document_id) THEN RAISE EXCEPTION 'Immutable report period identity'; END IF;
      RETURN NEW; END; $$;
      CREATE TRIGGER psl_root_identity BEFORE UPDATE ON pmo_periodreport FOR EACH ROW EXECUTE FUNCTION psl_report_root();""")
def unprotect(apps,schema_editor):
    for table in TABLES:schema_editor.execute(f'DROP TRIGGER psl_immutable ON {table}')
    for table,func in [('pmo_meeting','psl_meeting_root'),('pmo_actionitem','psl_action_root'),('pmo_periodreport','psl_report_root')]:
        schema_editor.execute(f'DROP TRIGGER psl_root_identity ON {table}; DROP FUNCTION {func}();')
class Migration(migrations.Migration):
    dependencies=[('pmo','0007_meetingactionlink_and_more'),('core','0002_append_only_history')]
    operations=[migrations.RunPython(protect,unprotect)]
