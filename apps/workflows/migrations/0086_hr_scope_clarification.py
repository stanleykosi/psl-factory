"""Optional metadata-only F35 question guards; no changes to existing task contracts."""
from django.db import migrations

SQL = r"""
CREATE FUNCTION psl_hr_scope_current(t workflows_humantask) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE s record; d record; n record; a record; r record; rules jsonb; uid bigint; pins jsonb;
BEGIN
 SELECT * INTO s FROM finance_hrreadsnapshot WHERE id=(t.context->>'snapshot_id')::bigint;
 SELECT * INTO d FROM finance_hrdisclosure WHERE id=s.contract_id;
 SELECT * INTO n FROM finance_hrfinanceneed WHERE id=d.need_id;
 SELECT * INTO r FROM policy_configuration WHERE id=(t.context->>'route_id')::bigint;
 uid:=(t.context->>'owner_id')::bigint; pins:=t.context->'authority';
 rules:=psl_schedules_values(r.id)->0;
 IF NOT COALESCE(n.case_id=t.case_id AND s.status='rejected'
  AND s.manifest->'findings'='["out_of_contract_fields"]'::jsonb AND s.payload='{}'::jsonb
  AND s.retain_until>clock_timestamp()
  AND r.component='F35.scope_clarification_route' AND psl_schedules_policy_current(t.case_id,r.id)
  AND rules=jsonb_build_object('owner_id',uid,'action','confirm_minimum_scope','question_version',1,'disclosure','codes_and_source_identity_only')
  AND psl_schedules_grants(t.case_id,uid,ARRAY['case.read','hrfinance.read','hrfinance.respond'])
  AND psl_schedules_grants(t.case_id,t.created_by_id,ARRAY['case.read','hrfinance.read','agent.hrfinance'])
  AND psl_schedules_policy_current(t.case_id,(pins->>'F35.authority_rules')::bigint)
  AND psl_schedules_role_current(t.case_id,uid,pins,'HR')
  AND (psl_schedules_values((pins->>'F35.authority_rules')::bigint)->0->'assignments') @> jsonb_build_array(jsonb_build_object('user_id',uid,'purpose','respond','role','HR'))
  AND t.claimed_by_id=uid, false) THEN RETURN false; END IF;
 IF EXISTS(SELECT 1 FROM finance_hrreadsnapshot WHERE contract_id=d.id AND id>s.id)
 OR EXISTS(SELECT 1 FROM finance_hrdisclosure WHERE need_id=n.id AND id>d.id)
 OR EXISTS(SELECT 1 FROM finance_hrfinanceneed WHERE case_id=t.case_id AND reference=n.reference AND version>n.version)
 OR EXISTS(SELECT 1 FROM jsonb_each_text(d.policy_ids) p WHERE NOT psl_schedules_policy_current(t.case_id,p.value::bigint))
 OR EXISTS(SELECT 1 FROM core_evidence e JOIN core_evidence old ON old.id=d.evidence_id WHERE e.case_id=t.case_id AND e.kind=old.kind AND e.version>old.version)
 THEN RETURN false; END IF;
 SELECT * INTO a FROM finance_hrhandoffrecord WHERE contract_id=d.id AND kind IN ('approve','return','revoke') ORDER BY id DESC LIMIT 1;
 IF NOT COALESCE(a.kind='approve' AND a.id=(s.manifest->>'authorization_id')::bigint
  AND psl_schedules_grants(t.case_id,a.actor_id,ARRAY['hrfinance.authorize'])
  AND psl_schedules_policy_current(t.case_id,(a.authority->>'F35.authority_rules')::bigint)
  AND psl_schedules_role_current(t.case_id,a.actor_id,a.authority,'HR')
  AND (psl_schedules_values((a.authority->>'F35.authority_rules')::bigint)->0->'assignments') @> jsonb_build_array(jsonb_build_object('user_id',a.actor_id,'purpose','authorize','role','HR')),false)
 THEN RETURN false; END IF;
 RETURN t.context=jsonb_build_object('purpose','hr_scope_clarification_v1','snapshot_id',s.id,'snapshot_hash',s.sha256,
  'contract_id',d.id,'contract_hash',d.sha256,'need_id',n.id,'authorization_id',a.id,
  'route_id',r.id,'owner_id',uid,'authority',jsonb_build_object('F35.authority_rules',(pins->>'F35.authority_rules')::bigint,
   'D05.role_principal_assignments',(pins->>'D05.role_principal_assignments')::bigint),
  'code','out_of_contract_fields','question_version',1,'private_console','finance_hrfinance');
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;

CREATE FUNCTION psl_hr_scope_task_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (CASE WHEN TG_OP='DELETE' THEN OLD.context ELSE NEW.context END)->>'purpose' IS DISTINCT FROM 'hr_scope_clarification_v1'
 THEN IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF; END IF;
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'HR scope clarification history cannot be deleted'; END IF;
 IF NEW.kind<>'factory_information' OR NEW.version_id IS NOT NULL
  OR NEW.required_role IS DISTINCT FROM 'Configured HR scope owner' OR NEW.factory_key IS DISTINCT FROM 'hr-scope:'||encode(sha256(convert_to(psl_fixed_json(NEW.context),'UTF8')),'hex')
 THEN RAISE EXCEPTION 'Exact internal HR clarification task required'; END IF;
 IF TG_OP='INSERT' THEN
  -- The closed packet contains only ASCII constants, hex hashes and integer IDs.
  -- psl_fixed_json (Finance0067) matches Python compact sorted JSON for this domain.
  -- Serialize all route versions for the same case before looking for an open wait.
  IF current_setting('transaction_isolation')<>'read committed'
  THEN RAISE EXCEPTION 'HR scope question creation requires READ COMMITTED'; END IF;
  PERFORM 1 FROM core_case WHERE id=NEW.case_id FOR UPDATE;
  IF EXISTS(SELECT 1 FROM workflows_humantask t WHERE t.case_id=NEW.case_id
    AND t.context->>'purpose'='hr_scope_clarification_v1'
    AND t.context->'snapshot_id'=NEW.context->'snapshot_id' AND t.status='open')
  THEN RAISE EXCEPTION 'Cancel prior open HR scope question before reassignment'; END IF;
  IF NEW.status<>'open' OR NEW.revision<>1 OR NOT psl_hr_scope_current(NEW)
  THEN RAISE EXCEPTION 'Current exact rejected HR source and configured owner required'; END IF;
 ELSE
  IF (NEW.case_id,NEW.created_by_id,NEW.created_at,NEW.claimed_by_id,NEW.required_role,NEW.context,NEW.kind,NEW.factory_key)
   IS DISTINCT FROM (OLD.case_id,OLD.created_by_id,OLD.created_at,OLD.claimed_by_id,OLD.required_role,OLD.context,OLD.kind,OLD.factory_key)
   OR OLD.status<>'open' OR NEW.revision<>OLD.revision+1 OR NEW.status NOT IN ('completed','cancelled')
  THEN RAISE EXCEPTION 'Immutable HR question; only typed reply or cancellation may close it'; END IF;
  IF NOT EXISTS(SELECT 1 FROM workflows_taskevent WHERE task_id=NEW.id
    AND action=CASE NEW.status WHEN 'completed' THEN 'hr_scope.responded' ELSE 'hr_scope.cancelled' END)
  THEN RAISE EXCEPTION 'Terminal HR task requires its actual typed event'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_hr_scope_task_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_humantask
 FOR EACH ROW EXECUTE FUNCTION psl_hr_scope_task_guard();

CREATE FUNCTION psl_hr_scope_event_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE t workflows_humantask%ROWTYPE; old_private boolean;
BEGIN
 IF TG_OP<>'INSERT' THEN
  SELECT context->>'purpose'='hr_scope_clarification_v1' INTO old_private FROM workflows_humantask WHERE id=OLD.task_id;
  IF old_private THEN RAISE EXCEPTION 'HR scope response history is append-only'; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 SELECT * INTO t FROM workflows_humantask WHERE id=NEW.task_id FOR UPDATE;
 IF t.context->>'purpose' IS DISTINCT FROM 'hr_scope_clarification_v1' THEN RETURN NEW; END IF;
 IF current_setting('transaction_isolation')<>'read committed'
 THEN RAISE EXCEPTION 'HR scope events require READ COMMITTED'; END IF;
 IF TG_OP<>'INSERT' OR t.status<>'open' OR EXISTS(SELECT 1 FROM workflows_taskevent WHERE task_id=t.id AND (action=NEW.action OR action IN ('hr_scope.responded','hr_scope.cancelled')))
 THEN RAISE EXCEPTION 'One append-only event per open HR clarification action'; END IF;
 IF NEW.action IN ('hr_scope.requested','hr_scope.cancelled') THEN
  IF NEW.actor_id<>t.created_by_id OR NEW.data<>'{}'::jsonb
   OR NOT psl_schedules_grants(t.case_id,NEW.actor_id,ARRAY['case.read','hrfinance.read','agent.hrfinance'])
  THEN RAISE EXCEPTION 'Original authorized requester and empty metadata event required'; END IF;
 ELSIF NEW.action='hr_scope.responded' THEN
  IF NEW.actor_id IS DISTINCT FROM t.claimed_by_id OR NOT psl_hr_scope_current(t)
   OR NOT EXISTS(SELECT 1 FROM workflows_taskevent WHERE task_id=t.id AND action='hr_scope.requested' AND actor_id=t.created_by_id AND data='{}'::jsonb)
   OR NOT COALESCE(NEW.data->>'reply' IN ('minimum_scope_confirmed','current_contract_clarification_required'),false)
   OR NEW.data IS DISTINCT FROM jsonb_build_object('reply',NEW.data->>'reply','outcome','await_proper_minimal_resubmission')
  THEN RAISE EXCEPTION 'Exact current HR owner and closed metadata-only response required'; END IF;
 ELSE RAISE EXCEPTION 'Unknown HR scope event action'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_hr_scope_event_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_taskevent
 FOR EACH ROW EXECUTE FUNCTION psl_hr_scope_event_guard();
"""
REVERSE = """
DROP TRIGGER psl_hr_scope_event_guard ON workflows_taskevent;
DROP FUNCTION psl_hr_scope_event_guard();
DROP TRIGGER psl_hr_scope_task_guard ON workflows_humantask;
DROP FUNCTION psl_hr_scope_task_guard();
DROP FUNCTION psl_hr_scope_current(workflows_humantask);
"""

class Migration(migrations.Migration):
    dependencies = [('workflows','0085_incident_report_claims'),('finance','0073_workbook_reference')]
    operations = [migrations.RunSQL(SQL, REVERSE)]
