"""Bind team invitations to the actual lead and the lead's staff administration scope."""
from importlib import import_module

import django.db.models.deletion
from django.db import migrations, models


PREVIOUS = import_module('apps.identity.migrations.0016_reviewed_staff_scope_move').GUARDS.split(
    'CREATE TRIGGER psl_scope_move_immutable',1)[0]

LEAD_AUTHORITY = """
CREATE FUNCTION psl_staff_team_inviter(mid bigint, uid bigint, cid uuid, aid bigint, pin jsonb)
RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS (
    SELECT 1 FROM identity_staffmembership m JOIN identity_staffteam t ON t.id=m.team_id
    JOIN auth_user u ON u.id=m.user_id
    LEFT JOIN identity_staffinvitation origin ON origin.id=m.invitation_id
    LEFT JOIN identity_staffscopemove moved ON moved.id=m.scope_move_id
    JOIN identity_tenantauthority original ON original.id=COALESCE(origin.authority_id,moved.authority_id)
    JOIN identity_tenantauthority cfg ON cfg.id=aid AND cfg.user_id=original.user_id
    JOIN core_case c ON c.id=m.case_id
    WHERE m.id=mid AND m.user_id=uid AND m.case_id=cid AND m.active AND u.is_active AND m.mode='lead'
      AND t.case_id=cid AND t.role=m.role AND pin->>'format'='psl.staff-role-scope/v1'
      AND pin->>'mode'='member' AND pin->>'role'=m.role AND pin->>'team_id'=t.id::text AND pin->>'team_name'=t.name
      AND c.kind='project' AND c.tenant=cfg.tenant AND cfg.enabled AND cfg.expires_at>CURRENT_TIMESTAMP
      AND c.synthetic=(cfg.value->>'classification'='synthetic')
      AND cfg.value->'kinds' ? 'project' AND cfg.value->'manage_access'='true'::jsonb
      AND cfg.value->'allowed_actions' ? 'case.read'
      AND cfg.value->'staff_lifecycle' @> '{"allow_invite":true,"allow_profile_edit":true}'::jsonb
      AND NOT EXISTS(SELECT 1 FROM identity_tenantauthority newer WHERE newer.user_id=cfg.user_id
        AND newer.tenant=cfg.tenant AND newer.version>cfg.version)
      AND EXISTS(SELECT 1 FROM identity_grant g JOIN auth_user admin ON admin.id=g.user_id
        WHERE g.case_id=cid AND g.user_id=cfg.user_id AND admin.is_active AND g.active AND g.action='case.read')
 );
$$;
CREATE FUNCTION psl_staff_team_invitation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.inviting_membership_id IS NOT NULL AND (
      NEW.actions<>'[]'::jsonb OR NEW.workspace_profiles<>'[]'::jsonb OR NEW.profile_key<>''
      OR NOT psl_staff_team_inviter(NEW.inviting_membership_id,NEW.actor_id,NEW.case_id,NEW.authority_id,NEW.role_scope)
      OR NEW.expires_at>(SELECT expires_at FROM identity_tenantauthority WHERE id=NEW.authority_id)
 ) THEN RAISE EXCEPTION 'Current team lead and exact member scope required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_staff_team_invitation BEFORE INSERT ON identity_staffinvitation
 FOR EACH ROW EXECUTE FUNCTION psl_staff_team_invitation_guard();
"""

ORIGINAL_AUTHORITY = """AND EXISTS (SELECT 1 FROM identity_grant g JOIN auth_user u ON u.id=g.user_id
            WHERE g.case_id=c.id AND g.user_id=i.actor_id AND u.is_active AND g.action='case.read' AND g.active)"""
MEMBERSHIP = PREVIOUS.replace('AND cfg.user_id=i.actor_id AND cfg.tenant=c.tenant','AND cfg.tenant=c.tenant').replace(
    ORIGINAL_AUTHORITY,f"""AND (
        (i.inviting_membership_id IS NULL AND cfg.user_id=i.actor_id {ORIGINAL_AUTHORITY})
        OR (i.inviting_membership_id IS NOT NULL AND
            psl_staff_team_inviter(i.inviting_membership_id,i.actor_id,c.id,cfg.id,i.role_scope))
    )""")

REVERSE = PREVIOUS + """
DROP TRIGGER psl_staff_team_invitation ON identity_staffinvitation;
DROP FUNCTION psl_staff_team_invitation_guard();
DROP FUNCTION psl_staff_team_inviter(bigint,bigint,uuid,bigint,jsonb);
"""


class Migration(migrations.Migration):
    dependencies = [('identity','0018_reuse_scoped_factory_approvals')]
    operations = [
        migrations.AddField('staffinvitation','inviting_membership',
            models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,to='identity.staffmembership')),
        migrations.RunSQL(LEAD_AUTHORITY + MEMBERSHIP,REVERSE),
    ]
