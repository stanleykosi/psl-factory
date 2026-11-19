"""Append-only, same-case, closed metadata and current participant database guards."""
from django.db import migrations

SQL=r"""
CREATE FUNCTION psl_payroll_question_route(cid uuid, d jsonb) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE uid bigint; pins jsonb; rid bigint;
BEGIN
 uid:=(d->>'owner_id')::bigint;rid:=(d->>'route_id')::bigint;pins:=d->'authority';
 RETURN COALESCE(d=jsonb_build_object('owner_id',uid,'route_id',rid,'authority',
  jsonb_build_object('F35.authority_rules',(pins->>'F35.authority_rules')::bigint,
                    'D05.role_principal_assignments',(pins->>'D05.role_principal_assignments')::bigint))
  AND EXISTS(SELECT 1 FROM policy_configuration WHERE id=rid AND case_id=cid AND component='F18.hr_question_route')
  AND psl_schedules_policy_current(cid,rid)
  AND psl_schedules_values(rid)->0=jsonb_build_object('owner_id',uid,'action','answer_aggregate_question',
   'disclosure','report_identity_and_topic_only','reply','closed_codes_only')
  AND psl_schedules_grants(cid,uid,ARRAY['case.read','hrfinance.read','hrfinance.respond'])
  AND psl_schedules_policy_current(cid,(pins->>'F35.authority_rules')::bigint)
  AND psl_schedules_role_current(cid,uid,pins,'HR')
  AND (psl_schedules_values((pins->>'F35.authority_rules')::bigint)->0->'assignments')
   @>jsonb_build_array(jsonb_build_object('user_id',uid,'purpose','respond','role','HR')),false);
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;

CREATE FUNCTION psl_payroll_question_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p record; r record; q record;
BEGIN
 PERFORM 1 FROM core_case WHERE id=NEW.case_id FOR UPDATE;
 SELECT * INTO p FROM finance_payrollpublication WHERE id=NEW.publication_id;
 SELECT * INTO r FROM finance_payrollrun WHERE id=p.run_id;
 SELECT * INTO q FROM finance_payrollrequest WHERE id=p.request_id;
 IF NOT COALESCE(q.case_id=NEW.case_id AND r.request_id=q.id
  AND NEW.packet=jsonb_build_object('format','psl.payroll-report-question/v1','publication_id',p.id,
   'report_version',p.version,'source_run_id',r.id,'source_sha256',r.sha256,
   'period',q.metadata->>'period','topic',NEW.packet->>'topic','private_payloads_read',false)
  AND NEW.packet->>'topic' IN ('report_coverage','business_unit_basis','staff_source_review')
  AND psl_schedules_grants(NEW.case_id,NEW.actor_id,ARRAY['case.read','payroll.report.read'])
  AND psl_schedules_policy_current(NEW.case_id,(p.policy_ids->>'F18.reporting_rules')::bigint)
  AND (psl_schedules_values((p.policy_ids->>'F18.reporting_rules')::bigint)->0->'recipient_ids') @>jsonb_build_array(NEW.actor_id)
  AND NOT EXISTS(SELECT 1 FROM finance_payrollpublication WHERE request_id=q.id AND version>p.version),false)
 THEN RAISE EXCEPTION 'Exact permitted payroll report identity and closed question required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_payroll_question_guard BEFORE INSERT ON finance_payrollreportquestion
 FOR EACH ROW EXECUTE FUNCTION psl_payroll_question_guard();

CREATE FUNCTION psl_payroll_question_event_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE q record; prior record; dispatch record;
BEGIN
 SELECT * INTO q FROM finance_payrollreportquestion WHERE id=NEW.question_id;
 PERFORM 1 FROM core_case WHERE id=q.case_id FOR UPDATE;
 SELECT * INTO prior FROM finance_payrollreportquestionevent WHERE question_id=q.id ORDER BY id DESC LIMIT 1;
 SELECT * INTO dispatch FROM finance_payrollreportquestionevent WHERE question_id=q.id AND kind='dispatched';
 IF NOT psl_schedules_grants(q.case_id,NEW.actor_id,ARRAY['case.read'])
  OR prior.kind IN ('cancelled','received') THEN RAISE EXCEPTION 'Current participant and open question required'; END IF;
 IF NEW.kind='cancelled' THEN
  IF NEW.actor_id<>q.actor_id OR NEW.data<>'{}'::jsonb THEN RAISE EXCEPTION 'Only requester may cancel'; END IF;
 ELSIF NEW.kind='dispatched' THEN
  IF prior.id IS NOT NULL OR NEW.actor_id<>q.actor_id OR NOT psl_payroll_question_route(q.case_id,NEW.data)
  THEN RAISE EXCEPTION 'Exact current HR question route required'; END IF;
 ELSIF NEW.kind='answered' THEN
  IF prior.kind IS DISTINCT FROM 'dispatched' OR NEW.actor_id IS DISTINCT FROM (dispatch.data->>'owner_id')::bigint
   OR NOT psl_payroll_question_route(q.case_id,dispatch.data)
   OR NOT COALESCE(NEW.data->>'reply' IN ('staff_basis_confirmed','source_review_needed','more_detail_needed'),false)
   OR NEW.data IS DISTINCT FROM jsonb_build_object('reply',NEW.data->>'reply')
  THEN RAISE EXCEPTION 'Assigned HR owner and closed metadata-only reply required'; END IF;
 ELSIF NEW.kind='received' THEN
  IF prior.kind IS DISTINCT FROM 'answered' OR NEW.actor_id<>q.actor_id OR NEW.data<>'{}'::jsonb
   OR NOT psl_payroll_question_route(q.case_id,dispatch.data)
  THEN RAISE EXCEPTION 'Original recipient and current HR reply required'; END IF;
 ELSE RAISE EXCEPTION 'Unknown report question action'; END IF;
 IF NEW.kind<>'cancelled' AND NOT psl_schedules_grants(q.case_id,q.actor_id,ARRAY['case.read','payroll.report.read'])
 THEN RAISE EXCEPTION 'Current original requester access required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_payroll_question_event_guard BEFORE INSERT ON finance_payrollreportquestionevent
 FOR EACH ROW EXECUTE FUNCTION psl_payroll_question_event_guard();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_payrollreportquestion
 FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_payrollreportquestionevent
 FOR EACH ROW EXECUTE FUNCTION psl_append_only();
"""
REVERSE="""
DROP TRIGGER psl_immutable ON finance_payrollreportquestionevent;
DROP TRIGGER psl_immutable ON finance_payrollreportquestion;
DROP TRIGGER psl_payroll_question_event_guard ON finance_payrollreportquestionevent;
DROP FUNCTION psl_payroll_question_event_guard();
DROP TRIGGER psl_payroll_question_guard ON finance_payrollreportquestion;
DROP FUNCTION psl_payroll_question_guard();
DROP FUNCTION psl_payroll_question_route(uuid,jsonb);
"""

class Migration(migrations.Migration):
    dependencies=[('finance','0080_payroll_report_questions'),('workflows','0086_hr_scope_clarification')]
    operations=[migrations.RunSQL(SQL,REVERSE)]
