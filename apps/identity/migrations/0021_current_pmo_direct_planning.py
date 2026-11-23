from django.db import migrations


CHECK = "psl_staff_factory_review_current(d.case_id,p.actor_id,'planning',p.id,NULL)"
DIRECT = "psl_current_pmo_direct_planning(d.case_id,p.actor_id,p.id)"
EXPANDED_CHECK = f"({CHECK} OR {DIRECT})"


def rewrite(before, after):
    return f"""
DO $guard$
DECLARE definition text := pg_get_functiondef('psl_progress_plan(bigint)'::regprocedure);
BEGIN
 IF strpos(definition, $before${before}$before$)=0 THEN
   RAISE EXCEPTION 'Expected Planning approval guard missing';
 END IF;
 EXECUTE replace(definition, $before${before}$before$, $after${after}$after$);
END $guard$;
"""


FORWARD = """
CREATE FUNCTION psl_current_pmo_direct_planning(cid uuid, person bigint, decision bigint)
RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS (
   SELECT 1 FROM pmo_deliveryrecord p
   JOIN pmo_deliverydossier d ON d.id=p.dossier_id AND d.case_id=cid
   JOIN core_case target ON target.id=cid AND target.kind='project'
   JOIN core_evidence e ON e.id=p.evidence_id AND e.case_id=cid AND e.created_by_id=person
   JOIN identity_staffmembership m ON m.user_id=person AND m.active AND m.role='pmo-lead' AND m.mode='lead'
   JOIN core_case seat ON seat.id=m.case_id AND seat.kind='project'
                      AND seat.tenant=target.tenant AND seat.synthetic=target.synthetic
   JOIN auth_user u ON u.id=m.user_id AND u.is_active
   WHERE p.id=decision AND p.actor_id=person AND p.kind='planning_decision'
     AND p.data->>'verdict'='approve' AND p.data->'direct_pmo_approval'='true'::jsonb
     AND e.kind='agent_private_planning_approval'
     AND e.source='planning-approval/v1:' || d.id::text
 );
$$;
""" + rewrite(CHECK, EXPANDED_CHECK)

REVERSE = rewrite(EXPANDED_CHECK, CHECK) + 'DROP FUNCTION psl_current_pmo_direct_planning(uuid,bigint,bigint);'


class Migration(migrations.Migration):
    dependencies = [('identity', '0020_one_pmo_head')]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
