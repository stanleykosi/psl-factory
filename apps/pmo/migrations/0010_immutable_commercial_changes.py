from django.db import migrations

TABLES=['pmo_commercialrevision','pmo_commercialdecision','pmo_commercialdocumentbinding','pmo_clientresponse','pmo_baselineadoption',
        'pmo_changeversion','pmo_changeassessment','pmo_changedecision','pmo_changeauthorization']

def protect(apps,schema_editor):
    for table in TABLES:
        schema_editor.execute(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION psl_append_only()')
    schema_editor.execute("""
    CREATE FUNCTION psl_commercial_root() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF NEW.case_id IS DISTINCT FROM OLD.case_id THEN RAISE EXCEPTION 'Immutable commercial case'; END IF;
      IF NEW.current_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM pmo_commercialrevision WHERE id=NEW.current_id AND dossier_id=NEW.id) THEN RAISE EXCEPTION 'Commercial revision belongs to another dossier'; END IF;
      RETURN NEW; END; $$;
    CREATE TRIGGER psl_root_identity BEFORE UPDATE ON pmo_commercialcase FOR EACH ROW EXECUTE FUNCTION psl_commercial_root();
    CREATE FUNCTION psl_change_root() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF NEW.case_id IS DISTINCT FROM OLD.case_id OR NEW.reference IS DISTINCT FROM OLD.reference THEN RAISE EXCEPTION 'Immutable change identity'; END IF;
      IF NEW.current_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM pmo_changeversion WHERE id=NEW.current_id AND change_id=NEW.id) THEN RAISE EXCEPTION 'Change revision belongs to another request'; END IF;
      RETURN NEW; END; $$;
    CREATE TRIGGER psl_root_identity BEFORE UPDATE ON pmo_changerequest FOR EACH ROW EXECUTE FUNCTION psl_change_root();
    CREATE FUNCTION psl_commercial_baseline() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF NEW.case_id IS DISTINCT FROM OLD.case_id THEN RAISE EXCEPTION 'Immutable baseline identity'; END IF;
      IF EXISTS (SELECT 1 FROM pmo_commercialcase WHERE case_id=OLD.case_id)
      AND (NEW.plan_id IS DISTINCT FROM OLD.plan_id OR NEW.costing_id IS DISTINCT FROM OLD.costing_id OR NEW.sow_id IS DISTINCT FROM OLD.sow_id OR NEW.signed_id IS DISTINCT FROM OLD.signed_id)
      AND NOT EXISTS (SELECT 1 FROM pmo_baselineadoption a JOIN pmo_commercialrevision r ON a.revision_id=r.id JOIN pmo_commercialcase c ON r.dossier_id=c.id
        WHERE c.case_id=OLD.case_id AND a.before=jsonb_build_object('plan_id',OLD.plan_id,'costing_id',OLD.costing_id,'sow_id',OLD.sow_id,'signed_id',OLD.signed_id)
        AND a.after=jsonb_build_object('plan_id',NEW.plan_id,'costing_id',NEW.costing_id,'sow_id',NEW.sow_id,'signed_id',NEW.signed_id)) THEN RAISE EXCEPTION 'Versioned baseline adoption required'; END IF;
      RETURN NEW; END; $$;
    CREATE TRIGGER psl_baseline_adoption BEFORE UPDATE ON pmo_baseline FOR EACH ROW EXECUTE FUNCTION psl_commercial_baseline();
    """)

def unprotect(apps,schema_editor):
    for table in TABLES:schema_editor.execute(f'DROP TRIGGER psl_immutable ON {table}')
    schema_editor.execute('DROP TRIGGER psl_root_identity ON pmo_commercialcase; DROP TRIGGER psl_root_identity ON pmo_changerequest; DROP TRIGGER psl_baseline_adoption ON pmo_baseline; DROP FUNCTION psl_commercial_root(); DROP FUNCTION psl_change_root(); DROP FUNCTION psl_commercial_baseline();')

class Migration(migrations.Migration):
    dependencies=[('pmo','0009_changerequest_changeversion_changerequest_current_and_more')]
    operations=[migrations.RunPython(protect,unprotect)]
