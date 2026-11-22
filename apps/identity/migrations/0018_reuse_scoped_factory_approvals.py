"""Teach native completion guards about exact scoped review receipts."""
from django.db import migrations


RECEIPT = """
CREATE FUNCTION psl_staff_factory_review_current(
    cid uuid, reviewer bigint, kind text, decision bigint, wid bigint,
    purpose text DEFAULT NULL, subject_type text DEFAULT NULL
) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS (
    SELECT 1 FROM identity_stafffactoryreviewuse receipt
    JOIN identity_staffassignment a ON a.id=receipt.assignment_id
    JOIN identity_staffmembership m ON m.id=a.membership_id AND m.case_id=a.case_id
    JOIN auth_user u ON u.id=m.user_id
    JOIN workflows_factorywork w ON w.id=a.work_id AND w.case_id=a.case_id
    WHERE a.case_id=cid AND m.user_id=reviewer AND m.active AND u.is_active
      AND a.factory_kind=kind AND receipt.native_id=decision AND receipt.verdict='approve'
      AND (wid IS NULL OR w.id=wid) AND NOT w.cancel_requested AND w.status<>'cancelled'
      AND (kind<>'accounting' OR EXISTS (
         SELECT 1 FROM finance_financereview r WHERE r.id=decision AND r.purpose=$6
           AND a.factory_subject=COALESCE(r.source_id,r.configuration_id,r.adjustment_id,r.run_id)
      ))
      AND a.factory_pin=encode(sha256(convert_to(psl_progress_canonical(
          jsonb_build_object('work',w.id,'kind',kind,'subject',a.factory_subject,
                             'head',w.source_head_id,'intake',w.request_hash)
          || CASE WHEN kind='accounting' THEN jsonb_build_object('purpose',purpose,'subject_type',subject_type)
                  ELSE '{}'::jsonb END),'UTF8')),'hex')
 );
$$;
"""

ACCOUNTING_TARGET = """r.purpose,CASE WHEN r.source_id IS NOT NULL THEN 'source'
   WHEN r.configuration_id IS NOT NULL THEN 'configuration'
   WHEN r.adjustment_id IS NOT NULL THEN 'adjustment' ELSE 'run' END"""

# Replace individual decision-actor checks. Other native provenance, rules, recipients,
# publication actors and data ownership checks remain in their existing functions.
CHECKS = (
    ('psl_progress_plan(bigint)',
     "psl_schedules_grants(d.case_id,p.actor_id,ARRAY['delivery.planning_decide'])",
     "psl_staff_factory_review_current(d.case_id,p.actor_id,'planning',p.id,NULL)"),
    ('psl_reporting_review(uuid,bigint)',
     "psl_reporting_grants(cid,rv.actor_id,ARRAY['document.review_controlled'])",
     "psl_staff_factory_review_current(cid,rv.actor_id,'document',rv.id,NULL)"),
    ('psl_escalation_document(bigint,bigint,bigint,bigint,bigint,bigint,jsonb,jsonb)',
     "psl_escalation_grants(w.case_id,d.actor_id,ARRAY['issue.escalation_decide'])",
     "psl_staff_factory_review_current(w.case_id,d.actor_id,'escalation',d.id,w.id)"),
    ('psl_escalation_document(bigint,bigint,bigint,bigint,bigint,bigint,jsonb,jsonb)',
     "psl_escalation_grants(w.case_id,rv.actor_id,ARRAY['document.review_controlled'])",
     "psl_staff_factory_review_current(w.case_id,rv.actor_id,'document',rv.id,w.id)"),
    ('psl_factory_identity()',
     "psl_schedules_grants(NEW.case_id,r.actor_id,ARRAY['document.review_controlled'])",
     "psl_staff_factory_review_current(NEW.case_id,r.actor_id,'document',r.id,NEW.id)"),
    ('psl_schedules_finance_review_current(bigint)',
     "psl_schedules_grants(r.case_id,r.actor_id,ARRAY['finance.review'])",
     f"psl_staff_factory_review_current(r.case_id,r.actor_id,'accounting',r.id,NULL,{ACCOUNTING_TARGET})"),
    ('psl_ppe_finance_review_current(bigint)',
     "psl_ppe_grants(r.case_id,r.actor_id,ARRAY['finance.review'])",
     f"psl_staff_factory_review_current(r.case_id,r.actor_id,'accounting',r.id,NULL,{ACCOUNTING_TARGET})"),
)


def rewrite(signature, before, after):
    return f"""
DO $guard$
DECLARE old_definition text := pg_get_functiondef('{signature}'::regprocedure);
BEGIN
 IF strpos(old_definition,$before${before}$before$)=0 THEN
   RAISE EXCEPTION 'Expected decision guard missing from {signature}';
 END IF;
 EXECUTE replace(old_definition,$before${before}$before$,$after${after}$after$);
END $guard$;
"""


FORWARD = RECEIPT + ''.join(rewrite(signature,grants,f'({grants} OR {receipt})') for signature,grants,receipt in CHECKS)
REVERSE = ''.join(rewrite(signature,f'({grants} OR {receipt})',grants) for signature,grants,receipt in reversed(CHECKS))
REVERSE += 'DROP FUNCTION psl_staff_factory_review_current(uuid,bigint,text,bigint,bigint,text,text);'


class Migration(migrations.Migration):
    dependencies = [('identity', '0017_scoped_factory_approvals')]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
