from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('identity', '0019_team_invitation_authority')]
    operations = [migrations.RunSQL("""
        LOCK TABLE identity_staffmembership IN SHARE ROW EXCLUSIVE MODE;
        DO $$ BEGIN
            IF EXISTS (SELECT c.tenant FROM identity_staffmembership m JOIN core_case c ON m.case_id=c.id
                       WHERE m.active AND m.role='pmo-lead' AND m.mode='lead'
                       GROUP BY c.tenant HAVING COUNT(DISTINCT m.user_id)>1) THEN
                RAISE EXCEPTION 'An administrator must reconcile existing PMO heads before this update';
            END IF;
        END $$;
        CREATE FUNCTION psl_one_pmo_head() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE org text;
        BEGIN
            IF NEW.active AND NEW.role='pmo-lead' AND NEW.mode='lead' THEN
                SELECT tenant INTO STRICT org FROM core_case WHERE id=NEW.case_id FOR SHARE;
                PERFORM pg_advisory_xact_lock(hashtextextended('psl-pmo-head:' || org, 0));
                IF EXISTS (SELECT 1 FROM identity_staffmembership m JOIN core_case c ON c.id=m.case_id
                           WHERE c.tenant=org AND m.active AND m.role='pmo-lead' AND m.mode='lead'
                           AND m.user_id<>NEW.user_id AND m.id<>NEW.id) THEN
                    RAISE EXCEPTION 'This organisation already has a PMO head' USING ERRCODE='23505';
                END IF;
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER psl_single_pmo_head BEFORE INSERT OR UPDATE ON identity_staffmembership
            FOR EACH ROW EXECUTE FUNCTION psl_one_pmo_head();
        CREATE FUNCTION psl_pmo_head_tenant_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM identity_staffmembership WHERE case_id=OLD.id AND active
                       AND role='pmo-lead' AND mode='lead') THEN
                RAISE EXCEPTION 'Reassign the PMO head before changing this workspace organisation';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER psl_pmo_head_tenant BEFORE UPDATE OF tenant ON core_case
            FOR EACH ROW WHEN (OLD.tenant IS DISTINCT FROM NEW.tenant) EXECUTE FUNCTION psl_pmo_head_tenant_guard();
    """, """
        DROP TRIGGER psl_pmo_head_tenant ON core_case;
        DROP FUNCTION psl_pmo_head_tenant_guard();
        DROP TRIGGER psl_single_pmo_head ON identity_staffmembership;
        DROP FUNCTION psl_one_pmo_head();
    """)]
