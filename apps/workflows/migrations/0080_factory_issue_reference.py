"""Exact issue coordination extension; preserve native lifecycle and historical guards."""
from django.db import migrations

PREVIOUS_IDENTITY = r"""CREATE OR REPLACE FUNCTION psl_factory_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Factory history cannot be deleted'; END IF;
 IF TG_OP='UPDATE' THEN
  IF (NEW.case_id,NEW.actor_id,NEW.key,NEW.definition,NEW.request,NEW.request_hash,NEW.created_at)
    IS DISTINCT FROM (OLD.case_id,OLD.actor_id,OLD.key,OLD.definition,OLD.request,OLD.request_hash,OLD.created_at)
    OR NEW.budget_used<OLD.budget_used OR NEW.fence<OLD.fence OR NEW.revision<OLD.revision
    OR (OLD.budget_used>0 AND NEW.budget_limit<>OLD.budget_limit)
  THEN RAISE EXCEPTION 'Immutable factory identity and monotonic shared budget required'; END IF;
  IF OLD.source_head_id IS NOT NULL AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id
   AND (NEW.source_head_id IS NULL OR NOT EXISTS(SELECT 1 FROM core_evidence n JOIN core_evidence o ON o.id=OLD.source_head_id WHERE n.id=NEW.source_head_id AND n.version>o.version))
  THEN RAISE EXCEPTION 'Forward native source successor required'; END IF;
 END IF;
 IF NEW.definition NOT IN ('finance-ledger/v1','engagement/v1','pmo-minutes/v1','pmo-finance/v1','planning/v1','commercial/v1','delivery-release/v1','delivery-hypercare/v1','delivery-archive/v1','delivery-handover/v1','delivery-closure/v1','delivery-go-live/v1','finance-accounts/v1','rfp-response/v1','finance-schedules/v1','finance-ppe/v1','pmo-change/v1','finance-forecast/v1','finance-payroll/v1','pmo-emergency/v1','finance-bu/v1','pmo-weekly-report/v1','pmo-leadership-report/v1','pmo-escalation/v1') THEN RAISE EXCEPTION 'Closed factory definition required'; END IF;
 IF (NEW.invoice_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_invoice i WHERE i.id=NEW.invoice_id AND i.case_id=NEW.case_id))
  OR (NEW.preparation_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_billingpreparation p WHERE p.id=NEW.preparation_id AND p.case_id=NEW.case_id))
  OR (NEW.policy_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM policy_configuration p WHERE p.id=NEW.policy_id AND p.case_id=NEW.case_id
    AND p.component=CASE NEW.definition WHEN 'finance-ledger/v1' THEN 'OPS.factory_ledger_execution' WHEN 'engagement/v1' THEN 'OPS.factory_engagement_execution' WHEN 'pmo-minutes/v1' THEN 'OPS.factory_minutes_execution' WHEN 'planning/v1' THEN 'OPS.factory_planning_execution' WHEN 'commercial/v1' THEN 'OPS.factory_commercial_execution' WHEN 'delivery-release/v1' THEN 'OPS.factory_delivery_execution' WHEN 'delivery-hypercare/v1' THEN 'OPS.factory_hypercare_execution' WHEN 'delivery-archive/v1' THEN 'OPS.factory_archive_execution' WHEN 'delivery-handover/v1' THEN 'OPS.factory_handover_execution' WHEN 'delivery-closure/v1' THEN 'OPS.factory_closure_execution' WHEN 'delivery-go-live/v1' THEN 'OPS.factory_go_live_execution' WHEN 'finance-schedules/v1' THEN 'OPS.factory_schedules_execution' WHEN 'pmo-escalation/v1' THEN 'OPS.factory_escalation_execution' WHEN 'finance-ppe/v1' THEN 'OPS.factory_ppe_execution' WHEN 'pmo-change/v1' THEN 'OPS.factory_change_execution' WHEN 'finance-bu/v1' THEN 'OPS.factory_bu_execution' WHEN 'finance-forecast/v1' THEN 'OPS.factory_forecast_execution' WHEN 'finance-payroll/v1' THEN 'OPS.factory_payroll_execution' WHEN 'pmo-emergency/v1' THEN 'OPS.factory_emergency_execution' WHEN 'pmo-weekly-report/v1' THEN 'OPS.factory_reporting_execution' WHEN 'pmo-leadership-report/v1' THEN 'OPS.factory_leadership_execution' WHEN 'finance-accounts/v1' THEN 'OPS.factory_accounting_execution' WHEN 'rfp-response/v1' THEN 'OPS.factory_rfp_execution' ELSE 'OPS.factory_execution' END))
 THEN RAISE EXCEPTION 'Same-case native factory references required'; END IF;
 IF NEW.definition='pmo-finance/v1' AND NEW.source_head_id IS NOT NULL THEN RAISE EXCEPTION 'Invoice work cannot carry a domain source head'; END IF;
 IF NEW.definition='planning/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
    SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='planning_packet' AND a.action='planning.recorded'
    AND a.data=jsonb_build_object('kind','packet','evidence_id',e.id,'sha256',e.sha256) AND e.body::jsonb->'engagement_id'=NEW.request->'engagement')
  THEN RAISE EXCEPTION 'Native same-engagement planning packet required'; END IF;
 END IF;
 IF NEW.definition='commercial/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
    SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_commercial_intake'
    AND e.body::jsonb->>'protocol'='factory-commercial-intake/v1' AND a.action='factory.commercial_intake'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native private commercial intake required'; END IF;
 END IF;

 IF NEW.definition='delivery-release/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_delivery_intake'
    AND d.case_id=NEW.case_id AND e.body::jsonb->>'protocol'='factory-delivery-intake/v1'
    AND e.body::jsonb->>'dossier_id'=d.id::text AND a.action='factory.delivery_intake'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case delivery intake and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-hypercare/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_delivery_intake'
    AND d.case_id=NEW.case_id AND e.body::jsonb->>'protocol'='factory-delivery-intake/v1'
    AND e.body::jsonb->>'dossier_id'=d.id::text AND a.action='factory.delivery_intake'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case delivery intake and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-archive/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_archive_intake'
    AND e.body::jsonb->>'protocol'='factory-archive-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inventory']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inventory')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.archive_intake','factory.archive_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case declared archive intake and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-handover/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_handover_intake'
    AND e.body::jsonb->>'protocol'='factory-handover-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.handover_intake','factory.handover_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case handover input provenance and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-closure/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_closure_intake'
    AND e.body::jsonb->>'protocol'='factory-closure-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.closure_intake','factory.closure_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case closure input provenance and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-go-live/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_go_live_intake'
    AND e.body::jsonb->>'protocol'='factory-go-live-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.go_live_intake','factory.go_live_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case go_live input provenance and dossier required'; END IF;
 END IF;

 IF NEW.definition='finance-accounts/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN finance_financesource s ON s.id=(e.body::jsonb->>'source')::bigint
   JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_accounting_intake'
    AND e.body::jsonb->>'schema'='factory-accounting-intake/v1' AND s.case_id=NEW.case_id
    AND s.batch_id=(NEW.request->>'batch')::bigint AND s.entity=NEW.request->>'entity'
    AND e.body::jsonb->'batch'=NEW.request->'batch' AND e.body::jsonb->'entity'=NEW.request->'entity'
    AND e.body::jsonb->'reference'=NEW.request->'reference'
    AND a.action='factory.accounting_inputs_recorded'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native exact accounting intake/source references required'; END IF;
 END IF;

 IF NEW.definition='pmo-change/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_changeversion v ON v.id=(e.body::jsonb->>'change_version_id')::bigint
   JOIN pmo_changerequest c ON c.id=v.change_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_change_intake'
    AND c.case_id=NEW.case_id AND c.id=(NEW.request->>'change')::bigint
    AND e.body::jsonb->>'protocol'='factory-change-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','change_version_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object'
    AND a.action IN ('factory.change_intake','factory.change_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-project native change intake provenance required'; END IF;
 END IF;

 IF NEW.definition='pmo-emergency/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_emergencyprofile ep ON ep.id=(e.body::jsonb->>'profile_id')::bigint
   JOIN pmo_changeversion cv ON cv.id=ep.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_emergency_intake'
    AND cr.case_id=NEW.case_id AND cr.id=(NEW.request->>'change')::bigint AND cv.category='Emergency' AND cv.incident_id IS NOT NULL
    AND e.body::jsonb->>'protocol'='factory-emergency-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','profile_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object'
    AND a.action IN ('factory.emergency_intake','factory.emergency_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-project incident-linked native Emergency source required'; END IF;
 END IF;

 IF NEW.definition='finance-payroll/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN finance_payrollrequest q ON q.id=(e.body::jsonb->>'request_id')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_payroll_intake'
    AND q.case_id=NEW.case_id AND q.reference=NEW.request->>'payroll_reference'
    AND e.body::jsonb->>'protocol'='factory-payroll-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','request_id','inputs']='{}'::jsonb
    AND (e.body::jsonb->'inputs')-ARRAY['input_ids','hr_snapshot_id']='{}'::jsonb
    AND jsonb_array_length(e.body::jsonb->'inputs'->'input_ids')=2
    AND (SELECT count(DISTINCT i.provider) FROM finance_payrollinput i
      WHERE i.id IN (SELECT value::bigint FROM jsonb_array_elements_text(e.body::jsonb->'inputs'->'input_ids'))
       AND i.request_id=q.id AND i.metadata->'accepted'='true'::jsonb)=2
    AND a.action IN ('factory.payroll_intake','factory.payroll_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-workspace restricted payroll provenance required'; END IF;
 END IF;

 IF NEW.definition='finance-ppe/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN finance_schedulework r ON r.id=(e.body::jsonb->>'register_id')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_ppe_intake'
    AND r.case_id=NEW.case_id AND r.kind='ppe_register' AND r.reference=NEW.request->>'register_reference'
    AND e.body::jsonb->>'protocol'='factory-ppe-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','register_id','prior_id','ledger_id']='{}'::jsonb
    AND a.action IN ('factory.ppe_intake','factory.ppe_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-case native PPE register provenance required'; END IF;
 END IF;

 IF NEW.definition='finance-schedules/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN core_evidence supplied ON supplied.id=(e.body::jsonb->>'evidence_id')::bigint AND supplied.case_id=e.case_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_schedules_intake'
    AND e.body::jsonb->>'protocol'='factory-schedules-intake/v1' AND e.body::jsonb->>'kind'=NEW.request->>'kind'
    AND e.body::jsonb-ARRAY['protocol','kind','parent_id','evidence_id','payload']='{}'::jsonb
    AND ((NEW.request->>'kind'='inventory' AND supplied.kind='schedule_inventory' AND e.body::jsonb->'payload'='null'::jsonb AND e.body::jsonb->'parent_id'='null'::jsonb)
     OR (NEW.request->>'kind'='income' AND supplied.kind='income_detail' AND EXISTS(SELECT 1 FROM finance_financerun n WHERE n.id=(e.body::jsonb->>'parent_id')::bigint AND n.case_id=NEW.case_id AND n.kind='mapping')))
    AND a.action IN ('factory.schedules_intake','factory.schedules_source') AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact native schedule source provenance required'; END IF;
 END IF;

 IF NEW.definition='pmo-weekly-report/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_reporting_intake'
    AND e.body::jsonb->>'protocol'='factory-weekly-report-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','inputs','manifest','captured_at']='{}'::jsonb
    AND (e.body::jsonb->'inputs')-ARRAY['template_id','content_id','start_at','end_at']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'manifest')='object'
    AND e.body::jsonb->'inputs'->>'start_at'=NEW.request->>'start_at' AND e.body::jsonb->'inputs'->>'end_at'=NEW.request->>'end_at'
    AND NEW.request->>'kind'='weekly_client' AND NEW.request->>'audience'='client'
    AND a.action IN ('factory.reporting_intake','factory.reporting_source') AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact private selected-period weekly report source required'; END IF;
 END IF;

 IF NEW.definition='pmo-escalation/v1' AND (NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
 SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
 JOIN pmo_escalationrequest r ON r.id=(psl_escalation_intake(e.id)->>'request_id')::bigint JOIN pmo_escalationprofile ep ON ep.id=r.profile_id
 JOIN pmo_issuestate s ON s.id=ep.state_id JOIN pmo_issue i ON i.id=s.issue_id
 WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND i.case_id=NEW.case_id AND i.id=(NEW.request->>'issue')::bigint
 AND e.kind='agent_private_escalation_intake' AND psl_escalation_intake(e.id)->>'protocol'='factory-escalation-intake/v1'
 AND (psl_escalation_intake(e.id)-ARRAY['protocol','request_id','profile_id','template_id'])='{}'::jsonb AND psl_escalation_intake(e.id)->>'profile_id'=ep.id::text
 AND r.direction=NEW.request->>'direction' AND r.target=NEW.request->>'target'
 AND a.action IN ('factory.escalation_intake','factory.escalation_source') AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)))
 THEN RAISE EXCEPTION 'Exact same-case source-bound escalation request required'; END IF;

 IF NEW.definition='finance-bu/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_bu_intake'
    AND e.sha256=encode(sha256(convert_to(e.body,'UTF8')),'hex')
    AND e.body::jsonb->>'protocol'='factory-bu-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','inputs']='{}'::jsonb
    AND (e.body::jsonb->'inputs')-ARRAY['mode','payroll_id','source_id','rule_ids','comparison']='{}'::jsonb
    AND e.body::jsonb->'inputs'->>'mode'=NEW.request->>'mode'
    AND jsonb_array_length(e.body::jsonb->'inputs'->'rule_ids')<=100
    AND a.action IN ('factory.bu_intake','factory.bu_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((NEW.request->>'mode'='staff' AND EXISTS(SELECT 1 FROM finance_payrollrun r JOIN finance_payrollrequest q ON q.id=r.request_id
      WHERE r.id=(e.body::jsonb->'inputs'->>'payroll_id')::bigint AND r.kind='match' AND q.case_id=NEW.case_id
       AND q.reference=NEW.request->>'source_reference' AND NEW.request->'scope'=jsonb_build_object('entity',q.metadata->'entity','period',q.metadata->'period','currency',q.metadata->'currency')
       AND e.body::jsonb->'inputs'->'source_id'='null'::jsonb AND e.body::jsonb->'inputs'->'comparison'='null'::jsonb
       AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(e.body::jsonb->'inputs'->'rule_ids') ri WHERE NOT EXISTS(
        SELECT 1 FROM finance_buwork rule WHERE rule.id=ri::bigint AND rule.case_id=NEW.case_id AND rule.kind='rule' AND rule.payroll_id=r.id))))
     OR (NEW.request->>'mode'='event' AND EXISTS(SELECT 1 FROM finance_buwork s
      WHERE s.id=(e.body::jsonb->'inputs'->>'source_id')::bigint AND s.case_id=NEW.case_id AND s.kind='source'
       AND s.reference=NEW.request->>'source_reference' AND s.metadata->'accepted'='true'::jsonb AND s.metadata->'scope'=NEW.request->'scope'
       AND e.body::jsonb->'inputs'->'payroll_id'='null'::jsonb AND e.body::jsonb->'inputs'->'rule_ids'='[]'::jsonb
       AND (e.body::jsonb->'inputs'->'comparison'='null'::jsonb OR EXISTS(SELECT 1 FROM finance_financerun fr
        WHERE fr.id=(e.body::jsonb->'inputs'->'comparison'->>'run_id')::bigint AND fr.case_id=NEW.case_id AND fr.kind='allocation'))))))
  THEN RAISE EXCEPTION 'Exact scoped native BU intake required'; END IF;
 END IF;
 IF NEW.status='verified' THEN
  IF NEW.definition='pmo-finance/v1' AND NOT EXISTS(
    SELECT 1 FROM finance_invoiceissue i JOIN finance_invoicedelivery d ON d.invoice_id=i.invoice_id JOIN finance_invoice n ON n.id=i.invoice_id
    WHERE n.id=NEW.invoice_id AND n.case_id=NEW.case_id AND i.sha256=n.sha256 AND i.payload=n.payload)
  THEN RAISE EXCEPTION 'Native invoice receipts required; agent completion is not verification'; END IF;
  IF NEW.definition='planning/v1' AND NOT EXISTS(
    SELECT 1 FROM pmo_deliverysource s JOIN pmo_deliverydossier d ON d.id=s.dossier_id JOIN core_evidence e ON e.id=s.evidence_id
    JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE d.case_id=NEW.case_id AND e.case_id=NEW.case_id AND e.kind='planning_readiness' AND s.kind='scope_baseline'
    AND e.body::jsonb->>'packet_id'=NEW.source_head_id::text AND e.body::jsonb->'inputs'->>'candidate_id'=d.candidate_id::text
    AND s.external_ref='psl:planning-readiness:'||e.id::text AND a.action='planning.recorded'
    AND a.data=jsonb_build_object('kind','ready','evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native planning readiness and delivery source required'; END IF;
  IF NEW.definition='commercial/v1' AND NOT EXISTS(
    SELECT 1 FROM pmo_commercialdocumentbinding b JOIN documents_version v ON v.id=b.version_id JOIN documents_document doc ON doc.id=v.document_id
    JOIN documents_publication p ON p.version_id=v.id JOIN pmo_commercialrevision r ON r.id=b.revision_id
    JOIN pmo_commercialcase c ON c.id=r.dossier_id JOIN pmo_costingbinding cb ON cb.costing_id=(r.sources->>'costing')::bigint
    JOIN pmo_costingrun cr ON cr.id=cb.run_id JOIN core_evidence e ON e.id=NEW.source_head_id
    WHERE c.case_id=NEW.case_id AND doc.case_id=NEW.case_id AND cr.case_id=NEW.case_id AND c.current_id=r.id AND cr.result->>'status'='known'
    AND r.sources->'requirements'=e.body::jsonb->'sources'->'requirements' AND r.sources->'plan'=e.body::jsonb->'sources'->'plan'
    AND r.sources->'engineering_estimate'=e.body::jsonb->'sources'->'engineering_estimate' AND r.sources->'security_estimate'=e.body::jsonb->'sources'->'security_estimate'
    AND r.sources->'sow'=e.body::jsonb->'sources'->'sow' AND cr.evidence_id::text=e.body::jsonb->'sources'->>'inputs'
    AND jsonb_array_length(p.recipient_ids)>0 AND NOT EXISTS(
      SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) AS destinations(recipient) WHERE NOT EXISTS(
       SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id::text=destinations.recipient
       AND pr.payload_sha256=v.payload_sha256 AND pr.payload=v.payload)))
  THEN RAISE EXCEPTION 'Exact native costing, commercial document and all recipient receipts required'; END IF;
 END IF;

 IF NEW.definition='delivery-release/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='release_ready'
   AND r.snapshot->'deployment_authorized'='false'::jsonb AND r.snapshot->>'financial_controls'='independent'
   AND a.phase='observed' AND a.result->>'release_ready'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Native source-bound release evidence required; no deployment authority is granted'; END IF;

 IF NEW.definition='delivery-hypercare/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='hypercare'
   AND r.snapshot->'qualified'='true'::jsonb
   AND a.phase='observed' AND a.result->>'hypercare'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Native source-bound qualified hypercare required; no closure or release authority is granted'; END IF;

 IF NEW.definition='delivery-archive/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN core_evidence e ON e.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='archive'
   AND r.data->'inventory'=e.body::jsonb->'inventory'
   AND r.snapshot->'physical_purge_performed'='false'::jsonb
   AND r.snapshot->>'repository'='internal-versioned'
   AND a.phase='observed' AND a.result->>'archive'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Exact observed native archive index required; no physical purge or closure authority'; END IF;

 IF NEW.definition='delivery-handover/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p JOIN documents_publicationreceipt r ON r.publication_id=p.id
  JOIN pmo_deliverydocumentbinding b ON b.version_id=p.version_id
  JOIN pmo_deliveryrecord h ON h.dossier_id=b.dossier_id AND h.kind='handover'
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND b.purpose='handover'
   AND b.dossier_id=(NEW.request->>'dossier')::bigint AND h.data->>'receipt_id'=r.id::text
   AND h.data->>'status'='received' AND h.actor_id=r.recipient_id
   AND a.phase='observed' AND fa.kind='ACT13' AND a.result->'verified'='true'::jsonb
   AND a.result->>'publication'=p.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native handover and actual recipient acknowledgement required'; END IF;

 IF NEW.definition='delivery-closure/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord c JOIN pmo_deliverydocumentbinding b ON b.version_id=(c.data->>'version_id')::bigint
  JOIN documents_version v ON v.id=b.version_id
  JOIN pmo_deliveryrecord decision ON decision.id=(c.data->>'decision_id')::bigint
  JOIN core_evidence head ON head.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE c.dossier_id=(NEW.request->>'dossier')::bigint AND c.kind='closure' AND b.dossier_id=c.dossier_id AND b.purpose='closure'
   AND decision.dossier_id=c.dossier_id AND decision.kind='closure_decision' AND decision.data->>'verdict'='approve'
   AND decision.data->>'version_id'=v.id::text AND decision.snapshot=b.snapshot AND c.snapshot=b.snapshot
   AND b.data=(head.body::jsonb->'inputs')-'template_id' AND v.template_id=(head.body::jsonb->'inputs'->>'template_id')::bigint
   AND a.result->'verified'='true'::jsonb AND a.result->>'closure'=c.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native closure, prescribed decision and current source binding required'; END IF;

 IF NEW.definition='delivery-go-live/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p JOIN documents_publicationreceipt r ON r.publication_id=p.id
  JOIN documents_version v ON v.id=p.version_id JOIN pmo_deliverydocumentbinding b ON b.version_id=v.id
  JOIN pmo_deliveryrecord g ON g.dossier_id=b.dossier_id AND g.kind IN ('go_live','go_live_reaffirmation')
  JOIN core_evidence pm ON pm.id=(g.data->>'pm_signature_id')::bigint
  JOIN core_evidence client ON client.id=(g.data->>'client_signature_id')::bigint
  JOIN core_evidence head ON head.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND b.purpose='go_live' AND v.audience='client'
   AND b.dossier_id=(NEW.request->>'dossier')::bigint AND g.data->>'receipt_id'=r.id::text AND g.snapshot=b.snapshot
   AND b.data=(head.body::jsonb->'inputs')-'template_id' AND v.template_id=(head.body::jsonb->'inputs'->>'template_id')::bigint
   AND pm.case_id=NEW.case_id AND client.case_id=NEW.case_id AND pm.kind='signature' AND client.kind='signature' AND pm.id<>client.id
   AND a.result->'verified'='true'::jsonb AND a.result->>'acceptance'=g.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native go-live acceptance, distinct actual signature evidence and source-bound client receipt required'; END IF;

 IF NEW.definition='finance-accounts/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM finance_financerun r JOIN finance_financesource s ON s.id=r.source_id
  JOIN finance_financedocumentbinding b ON b.run_id=r.id
  JOIN documents_version v ON v.id=b.version_id JOIN documents_document d ON d.id=v.document_id
  JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
  JOIN core_evidence h ON h.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE r.case_id=NEW.case_id AND s.case_id=NEW.case_id AND d.case_id=NEW.case_id AND r.kind='formula'
   AND s.id=(h.body::jsonb->>'source')::bigint AND s.batch_id=(NEW.request->>'batch')::bigint
   AND (p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id OR p.factory_work_id IS NULL)
   AND d.current_id=v.id AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint))
   AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
   AND EXISTS(SELECT 1 FROM finance_financereview fr WHERE fr.run_id=r.id AND fr.purpose='output' AND fr.verdict='approve'
    AND fr.id=(SELECT max(last.id) FROM finance_financereview last WHERE last.run_id=r.id AND last.purpose='output'))
   AND a.result->'verified'='true'::jsonb AND a.result->>'run'=r.id::text AND a.result->>'source'=s.id::text
   AND a.result->>'binding'=b.id::text AND a.result->>'publication'=p.id::text AND a.result->>'document_version'=v.id::text
   AND a.result->'receipt_ids'=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)) AND NOT EXISTS(
  SELECT 1 FROM finance_financerun r JOIN finance_financesource s ON s.id=r.source_id
  JOIN finance_financedocumentbinding b ON b.run_id=r.id
  JOIN documents_version v ON v.id=b.version_id JOIN documents_document d ON d.id=v.document_id
  JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
  JOIN core_evidence h ON h.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE r.case_id=NEW.case_id AND s.case_id=NEW.case_id AND d.case_id=NEW.case_id AND r.kind='statement'
   AND s.id=(h.body::jsonb->>'source')::bigint AND s.batch_id=(NEW.request->>'batch')::bigint
   AND (p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id OR p.factory_work_id IS NULL)
   AND d.current_id=v.id AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint))
   AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
   AND EXISTS(SELECT 1 FROM finance_financereview fr WHERE fr.run_id=r.id AND fr.purpose='output' AND fr.verdict='approve'
    AND fr.id=(SELECT max(last.id) FROM finance_financereview last WHERE last.run_id=r.id AND last.purpose='output'))
   AND a.result->'verified'='true'::jsonb AND a.result->>'run'=r.id::text AND a.result->>'source'=s.id::text
   AND a.result->>'binding'=b.id::text AND a.result->>'publication'=p.id::text AND a.result->>'document_version'=v.id::text
   AND a.result->'receipt_ids'=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
   AND EXISTS(SELECT 1 FROM policy_configuration pc JOIN policy_registeredreference pr ON pr.case_id=pc.case_id
    AND pr.ref=pc.envelope->'value'->>'artifact_ref' AND pr.version=(pc.envelope->'value'->>'artifact_version')::integer
    AND pr.sha256=pc.envelope->'value'->>'sha256'
    WHERE pc.id=NEW.policy_id AND pc.component='OPS.factory_accounting_execution'
     AND pr.schema_ref='schema:psl/factory-accounting-execution/v3' AND pr.content->>'statement_contract_id'=r.request->>'contract_id')
   AND r.result->>'status'='complete' AND r.result->>'scope'='selected_statement_lines'
   AND r.result->'whole_statement_certified'='false'::jsonb
   AND EXISTS(SELECT 1 FROM finance_financereview cr JOIN policy_configuration cc ON cc.id=cr.configuration_id
    WHERE cc.id=(r.request->>'contract_id')::bigint AND cc.case_id=r.case_id AND cc.component='D06.statement_contract'
     AND cr.purpose='formula' AND cr.verdict='approve'
     AND cr.id=(SELECT max(id) FROM finance_financereview WHERE configuration_id=cc.id AND purpose='formula')
     AND cr.id::text=r.snapshot->'reviews'->'D06.statement_contract'->>'id'
     AND (SELECT state FROM policy_policystate WHERE configuration_id=cc.id ORDER BY id DESC LIMIT 1)='active')
   AND jsonb_array_length(r.snapshot->'inputs')>0
   AND ((SELECT count(*) FROM finance_financestatementinput si WHERE si.statement_id=r.id)+(SELECT count(*) FROM finance_financestatementppeinput pi WHERE pi.statement_id=r.id))=jsonb_array_length(r.snapshot->'inputs') AND psl_statement_ppe_current(r.id) AND psl_statement_ppe_document_valid(r.id,b.version_id,b.snapshot) AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) uid WHERE EXISTS(SELECT 1 FROM finance_financestatementppeinput pi WHERE pi.statement_id=r.id) AND NOT psl_ppe_grants(r.case_id,uid::bigint,ARRAY['case.read','finance.read','ppe.read']))
   AND NOT EXISTS(SELECT 1 FROM finance_financestatementinput si
    JOIN finance_financerun sr ON sr.id=si.source_run_id
    JOIN finance_financereview rv ON rv.id=si.source_review_id
    JOIN finance_financesource ss ON ss.id=sr.source_id
    WHERE si.statement_id=r.id AND (sr.case_id<>r.case_id OR rv.run_id<>sr.id OR rv.verdict<>'approve'
     OR rv.id<>(SELECT max(id) FROM finance_financereview WHERE run_id=sr.id AND purpose='output')
     OR sr.result->>'period'<>r.result->>'period' OR sr.result->>'entity'<>r.result->>'entity'
     OR sr.result->>'currency'<>r.result->>'currency' OR ss.accounting_basis IS DISTINCT FROM r.result->>'accounting_basis'
     OR si.declaration->>'source_sign' IS NULL OR si.declaration->>'source_sign' IS DISTINCT FROM si.declaration->>'destination_sign'
     OR sr.result->'company'->si.metric->'value' IS DISTINCT FROM r.result->'company'->si.destination->'value'
     OR sr.result->'company'->si.metric->>'unit' IS DISTINCT FROM si.declaration->>'unit'))
)
 THEN RAISE EXCEPTION 'Current native accounting binding/output review and all exact recipient receipts required'; END IF;

 IF TG_OP='UPDATE' AND NEW.definition IN ('delivery-release/v1','delivery-hypercare/v1')
 AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id THEN
  IF NEW.cancel_requested OR OLD.status IN ('cancelled','followup_needed') OR NEW.status<>'ready'
   OR (OLD.lease_until IS NOT NULL AND OLD.lease_until>statement_timestamp())
   OR NOT EXISTS(SELECT 1 FROM core_evidence n JOIN core_evidence o ON o.id=OLD.source_head_id
     JOIN core_audit a ON a.case_id=n.case_id AND a.actor_id=n.created_by_id
     JOIN core_evidence e ON e.case_id=n.case_id AND a.data->'evidence'=to_jsonb(e.id)
     WHERE n.id=NEW.source_head_id AND n.body=o.body AND n.version>o.version
      AND a.action='factory.delivery_intake_reaffirmed' AND a.data->>'work'=NEW.id::text
      AND a.data->>'previous'=OLD.source_head_id::text AND a.data->>'current'=n.id::text
      AND length(btrim(a.data->>'reason')) BETWEEN 1 AND 2000
      AND coalesce(a.data->>'packet','') ~ '^[a-f0-9]{64}$')
   OR EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity t ON t.id=a.activity_id
     WHERE t.work_id=NEW.id AND t.kind='ACT03' AND a.phase='started' AND a.result->>'schema'='factory-provider-request/v1'
      AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt done WHERE done.activity_id=a.activity_id AND done.number=a.number AND done.phase IN ('observed','failed'))
      AND NOT EXISTS(SELECT 1 FROM workflows_factoryplanningreceipt WHERE attempt_id=a.id))
  THEN RAISE EXCEPTION 'Exact fresh human source instruction and reconciled original effects required'; END IF;
 END IF;

 IF NEW.definition='rfp-response/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_rfpcase r ON r.id=(NEW.request->>'rfp')::bigint AND r.case_id=NEW.case_id
   JOIN pmo_rfpintake i ON i.id=(e.body::jsonb->>'intake')::bigint AND i.rfp_id=r.id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_rfp_intake'
    AND e.body::jsonb->>'schema'='factory-rfp-intake/v1' AND e.body::jsonb->'rfp'=NEW.request->'rfp'
    AND NEW.request-ARRAY['rfp','reference']='{}'::jsonb
    AND e.body::jsonb-ARRAY['schema','rfp','intake','response_evidence','public_terms','sources','matrix','lessons']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'sources')='object' AND jsonb_typeof(e.body::jsonb->'matrix')='array'
    AND a.action='factory.rfp_inputs_recorded' AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact native same-case RFP instruction provenance required'; END IF;
  IF TG_OP='UPDATE' AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id THEN
   IF OLD.status IN ('verified','cancelled','followup_needed') OR NEW.cancel_requested OR NEW.status<>'ready'
    OR (OLD.lease_until IS NOT NULL AND OLD.lease_until>statement_timestamp())
    OR NOT EXISTS(SELECT 1 FROM core_audit a JOIN core_evidence e ON e.id=NEW.source_head_id AND e.created_by_id=a.actor_id
      WHERE a.case_id=NEW.case_id AND a.action='factory.rfp_instruction_changed'
       AND a.data->>'work'=NEW.id::text AND a.data->>'previous'=OLD.source_head_id::text
       AND a.data->>'current'=NEW.source_head_id::text AND length(btrim(a.data->>'reason')) BETWEEN 1 AND 4000)
    OR EXISTS(SELECT 1 FROM documents_publication p JOIN documents_publicationjob j ON j.publication_id=p.id
      WHERE p.factory_work_id=NEW.id AND (j.status IN ('pending','unknown','leased','held') OR
       j.status='confirmed' AND NOT EXISTS(SELECT 1 FROM pmo_rfpsubmission s WHERE s.version_id=p.version_id)))
    OR EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity t ON t.id=a.activity_id
      WHERE t.work_id=NEW.id AND t.kind='ACT03' AND a.phase='started' AND a.result->>'schema'='factory-provider-request/v1'
       AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt done WHERE done.activity_id=a.activity_id AND done.number=a.number AND done.phase IN ('observed','failed'))
       AND NOT EXISTS(SELECT 1 FROM workflows_factoryplanningreceipt pr WHERE pr.attempt_id=a.id))
   THEN RAISE EXCEPTION 'Fresh human RFP instruction and reconciled original effects required'; END IF;
  END IF;

  IF NEW.status='verified' AND NOT EXISTS(
   SELECT 1 FROM pmo_rfpdisposition d JOIN pmo_rfpoutcome o ON o.id=d.outcome_id
   JOIN pmo_rfpsubmission s ON s.id=o.submission_id JOIN pmo_rfpresponse r ON r.id=s.response_id
   JOIN pmo_rfpcase root ON root.id=r.rfp_id JOIN core_evidence h ON h.id=NEW.source_head_id
   JOIN pmo_commercialrevision cr ON cr.id=r.commercial_id
   JOIN pmo_rfpdocumentbinding b ON b.response_id=r.id AND b.version_id=s.version_id
   JOIN documents_version v ON v.id=s.version_id JOIN documents_document doc ON doc.id=v.document_id
   JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
   JOIN documents_controlledreview review ON review.id=p.review_id AND review.version_id=v.id
   JOIN workflows_factoryactivity t ON t.work_id=NEW.id AND t.kind='ACT13'
   JOIN workflows_factoryattempt a ON a.activity_id=t.id AND a.phase='observed'
   WHERE root.case_id=NEW.case_id AND root.id=(NEW.request->>'rfp')::bigint AND d.rfp_id=root.id
    AND doc.case_id=NEW.case_id AND s.snapshot=b.snapshot AND s.snapshot->>'response'=r.id::text
    AND s.snapshot->'sources'=r.snapshot AND d.snapshot->'sources'=r.snapshot AND d.snapshot->'commercial_sources'=cr.sources
    AND jsonb_array_length(s.snapshot->'reviews')=2 AND NOT EXISTS(
     SELECT 1 FROM jsonb_array_elements_text(s.snapshot->'reviews') WITH ORDINALITY item(id,nth)
     WHERE NOT EXISTS(SELECT 1 FROM pmo_rfpreview rr WHERE rr.id=item.id::bigint AND rr.response_id=r.id AND rr.verdict='approve'
      AND rr.role=CASE item.nth WHEN 1 THEN 'PMO Lead' WHEN 2 THEN 'Engineering Lead' END AND rr.created_at<=p.created_at))
    AND jsonb_array_length(s.snapshot->'costing_decisions')=3 AND NOT EXISTS(
     SELECT 1 FROM jsonb_array_elements_text(s.snapshot->'costing_decisions') WITH ORDINALITY item(id,nth)
     WHERE NOT EXISTS(SELECT 1 FROM pmo_commercialdecision cd WHERE cd.id=item.id::bigint AND cd.revision_id=cr.id AND cd.verdict='approve'
      AND cd.role=CASE item.nth WHEN 1 THEN 'PM' WHEN 2 THEN 'Head of PMO' WHEN 3 THEN 'CEO' END AND cd.created_at<=p.created_at))
    AND review.verdict='approve' AND review.payload_sha256=v.payload_sha256 AND review.created_at<=p.created_at
    AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
    AND (p.factory_work_id=NEW.id OR p.factory_work_id IS NULL)
    AND (p.factory_work_id IS NULL OR EXISTS(SELECT 1 FROM core_evidence origin WHERE origin.id=p.factory_source_id
     AND origin.case_id=NEW.case_id AND origin.kind='agent_private_rfp_intake' AND origin.body::jsonb->'rfp'=NEW.request->'rfp'))
    AND d.snapshot->>'response'=r.id::text AND d.snapshot->>'submission'=s.id::text AND d.snapshot->>'outcome'=o.id::text
    AND d.snapshot->>'case'=NEW.case_id::text AND d.snapshot->'baseline_imported'='false'::jsonb
    AND (d.kind='route_a' AND o.result='won' AND d.snapshot->>'route'='A' OR
     d.kind='loss_archive' AND o.result='lost' AND d.lessons_id=(h.body::jsonb->>'lessons')::bigint)
    AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
     SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256))
    AND s.receipt_ids=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
    AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
    AND a.result->'verified'='true'::jsonb AND a.result->>'head'=NEW.source_head_id::text
    AND a.result->>'response'=r.id::text AND a.result->>'disposition'=d.id::text AND a.result->>'submission'=s.id::text
    AND a.result->>'outcome'=o.id::text AND a.result->>'document_version'=v.id::text
    AND a.result->>'publication'=p.id::text AND a.result->'receipt_ids'=s.receipt_ids)
  THEN RAISE EXCEPTION 'Historical approved RFP submission, actual customer outcome and all exact receipts required'; END IF;

 END IF;

 IF NEW.definition='pmo-change/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN pmo_changeauthorization ca ON ca.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint
  JOIN pmo_changeversion cv ON cv.id=ca.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
  JOIN pmo_changeclosure cc ON cc.authorization_id=ca.id
  JOIN documents_publicationreceipt r ON r.id=cc.receipt_id JOIN documents_publication p ON p.id=r.publication_id
  JOIN pmo_changedocumentbinding b ON b.version_id=p.version_id AND b.authorization_id=ca.id AND b.purpose='go_live'
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND cv.id=(e.body::jsonb->>'change_version_id')::bigint
   AND cr.case_id=NEW.case_id AND cr.current_id=cv.id AND cr.id=(NEW.request->>'change')::bigint
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id
   AND cc.execution_ids=b.execution_ids AND cc.pm_signature_id<>cc.client_signature_id
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'closure'=cc.id::text
   AND a.result->>'document_version'=p.version_id::text
   AND EXISTS(SELECT 1 FROM documents_publication np JOIN pmo_changedocumentbinding nb ON nb.version_id=np.version_id
    JOIN documents_publicationreceipt nr ON nr.publication_id=np.id
    WHERE np.factory_work_id=NEW.id AND np.factory_source_id=e.id AND nb.authorization_id=ca.id AND nb.purpose='notice')
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient
    WHERE NOT EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint)))
 THEN RAISE EXCEPTION 'Observed exact native change closure and controlled recipient receipts required'; END IF;

 IF NEW.definition='pmo-emergency/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN pmo_emergencyprofile ep ON ep.id=(e.body::jsonb->>'profile_id')::bigint
  JOIN pmo_emergencyoutcome o ON o.id=(e.body::jsonb->'inputs'->>'outcome_id')::bigint AND o.profile_id=ep.id
  JOIN pmo_emergencyauthorization ea ON ea.id=o.authorization_id AND ea.profile_id=ep.id
  JOIN pmo_emergencyretrospectiverecord rr ON rr.outcome_id=o.id
  JOIN pmo_changeversion cv ON cv.id=ep.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
  JOIN pmo_emergencydocumentbinding b ON b.outcome_id=o.id
  JOIN documents_version v ON v.id=b.version_id JOIN documents_publication p ON p.version_id=v.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND cr.case_id=NEW.case_id AND cr.id=(NEW.request->>'change')::bigint AND cr.current_id=cv.id
   AND ea.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint AND ea.created_at<=o.implemented_at
   AND rr.snapshot->>'authorization_id'=ea.id::text AND rr.snapshot->>'status' IN ('evidenced_on_time','completed_with_lateness_exception')
   AND b.manifest->>'reconciliation_id'=rr.id::text AND b.manifest->>'outcome_id'=o.id::text
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id AND v.template_id=(e.body::jsonb->'inputs'->>'template_id')::bigint
   AND v.audience=e.body::jsonb->'inputs'->>'audience'
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'retrospective_record'=rr.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'retrospective_status'=rr.snapshot->>'status'
   AND EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient
    WHERE NOT EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint)))
 THEN RAISE EXCEPTION 'Observed exact native Emergency retrospective and every report receipt required; deployment and ordinary closure are not granted'; END IF;

 IF NEW.definition='finance-payroll/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN finance_payrollrequest q ON q.id=(e.body::jsonb->>'request_id')::bigint
   JOIN finance_payrollrun ar ON ar.request_id=q.id AND ar.kind='aggregate'
   JOIN finance_payrollrun mr ON mr.id=ar.parent_id AND mr.kind='match'
   JOIN finance_payrollrun cr ON cr.id=mr.parent_id AND cr.kind='combine'
   JOIN finance_payrollpublication p ON p.run_id=ar.id AND p.request_id=q.id
   JOIN finance_payrollreview rv ON rv.id=p.review_id AND rv.run_id=ar.id
   JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
   JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
   JOIN policy_configuration pc ON pc.id=(p.policy_ids->>'F18.reporting_rules')::bigint
   JOIN policy_registeredreference pr ON pr.case_id=pc.case_id AND pr.ref=pc.envelope->'value'->>'artifact_ref'
    AND pr.version=(pc.envelope->'value'->>'artifact_version')::integer AND pr.sha256=pc.envelope->'value'->>'sha256'
  WHERE e.id=NEW.source_head_id AND q.case_id=NEW.case_id AND q.reference=NEW.request->>'payroll_reference'
   AND cr.request_id=q.id AND mr.request_id=q.id
   AND (cr.metadata->'input_ids') @> (e.body::jsonb->'inputs'->'input_ids')
   AND (cr.metadata->'input_ids') <@ (e.body::jsonb->'inputs'->'input_ids')
   AND mr.hr_snapshot_id=(e.body::jsonb->'inputs'->>'hr_snapshot_id')::bigint
   AND ar.metadata->>'status'='complete' AND mr.metadata->>'status'='complete' AND cr.metadata->>'status'='complete'
   AND rv.verdict='approve' AND rv.subject_sha256=ar.sha256
   AND rv.id=(SELECT max(id) FROM finance_payrollreview WHERE run_id=ar.id)
   AND p.payload->'by_bu'=ar.result->'by_bu' AND p.payload->'eligible_total'=ar.result->'eligible_total'
   AND p.payload->>'source_run'=ar.id::text AND p.payload->>'disclosure'='aggregate_only'
   AND NOT (p.payload ? 'rows') AND p.payload->'hr_written'='false'::jsonb AND p.payload->'ledger_posted'='false'::jsonb
   AND NOT EXISTS(SELECT 1 FROM finance_payrollpublication newer WHERE newer.request_id=q.id AND newer.version>p.version)
   AND NOT EXISTS(SELECT 1 FROM finance_payrollrequest newer WHERE newer.case_id=q.case_id AND newer.reference=q.reference AND newer.version>q.version)
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'publication'=p.id::text
   AND a.result->>'run'=ar.id::text AND a.result->>'request'=q.id::text
   AND jsonb_array_length(pr.content->'recipient_ids')>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(pr.content->'recipient_ids') recipient
     WHERE NOT EXISTS(SELECT 1 FROM finance_payrollreportreceipt rr WHERE rr.publication_id=p.id AND rr.actor_id=recipient::bigint
       AND a.result->'receipt_ids' @> to_jsonb(ARRAY[rr.id]))))
 THEN RAISE EXCEPTION 'Observed exact payroll aggregate and actual recipient-owned receipts required'; END IF;

 IF NEW.definition='finance-forecast/v1' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
  JOIN finance_forecastscenario s ON s.id=(e.body::jsonb->>'scenario_id')::bigint
  WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND s.case_id=NEW.case_id
   AND e.kind='agent_private_forecast_intake' AND e.body::jsonb->>'protocol'='factory-forecast-selection/v1'
   AND s.reference=NEW.request->>'scenario_reference'
   AND e.body::jsonb-ARRAY['protocol','scenario_id','as_of','months','source_ids','template_id','audience']='{}'::jsonb
   AND e.body::jsonb->>'audience' IN ('internal','management','group')
   AND jsonb_typeof(e.body::jsonb->'source_ids')='array'
   AND jsonb_array_length(e.body::jsonb->'source_ids')=(SELECT count(*) FROM (
    SELECT s.evidence_id AS id UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'openings') item
    UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'items') item) exact_sources)
   AND NOT EXISTS(SELECT id FROM (
    SELECT s.evidence_id AS id UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'openings') item
    UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'items') item) exact_sources
    WHERE NOT e.body::jsonb->'source_ids' @> jsonb_build_array(id))
   AND (e.body::jsonb->'template_id'='null'::jsonb OR EXISTS(SELECT 1 FROM documents_template t
    WHERE t.id=(e.body::jsonb->>'template_id')::bigint AND t.case_id=NEW.case_id AND t.definition->>'document_type'=CASE WHEN e.body::jsonb->>'audience'='group' THEN 'finance_group_report' ELSE 'finance_report' END))
   AND e.body::jsonb->>'as_of'=s.payload->>'as_of' AND e.body::jsonb->'months'=s.payload->'months'
   AND a.action IN ('factory.forecast_intake','factory.forecast_source')
   AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
   AND NEW.invoice_id IS NULL AND NEW.preparation_id IS NULL)
 THEN RAISE EXCEPTION 'Exact native forecast intake provenance required'; END IF;
 IF NEW.definition='finance-forecast/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN finance_forecastscenario s ON s.id=(e.body::jsonb->>'scenario_id')::bigint
  JOIN finance_forecastrun r ON r.scenario_id=s.id JOIN finance_forecastreview rv ON rv.run_id=r.id
  JOIN finance_forecastbinding b ON b.run_id=r.id JOIN documents_version v ON v.id=b.version_id
  JOIN documents_publication p ON p.version_id=v.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND r.case_id=NEW.case_id AND s.case_id=NEW.case_id
   AND rv.verdict='approve' AND rv.id=(SELECT max(id) FROM finance_forecastreview WHERE run_id=r.id)
   AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario newer WHERE newer.case_id=s.case_id AND newer.reference=s.reference AND newer.number>s.number)
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id AND p.factory_policy_id=NEW.policy_id
   AND v.template_id=(e.body::jsonb->>'template_id')::bigint AND v.audience=e.body::jsonb->>'audience'
   AND b.snapshot->>'run_hash'=r.sha256 AND b.snapshot->>'output_review'=rv.id::text
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text
   AND a.result->>'forecast_run'=r.id::text AND a.result->>'forecast_review'=rv.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'publication'=p.id::text
   AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint
     AND pr.payload_sha256=v.payload_sha256 AND pr.payload=v.payload)))
 THEN RAISE EXCEPTION 'Observed exact native forecast approval and aggregate receipts required'; END IF;

 IF NEW.definition='finance-ppe/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e
  JOIN finance_schedulework r ON r.id=(e.body::jsonb->>'register_id')::bigint
  JOIN finance_schedulework s ON s.case_id=NEW.case_id AND s.kind='ppe_schedule'
  JOIN finance_schedulereview sr ON sr.work_id=s.id AND sr.authority->>'purpose'='schedule'
  JOIN finance_schedulereview rr ON rr.work_id=r.id AND rr.authority->>'purpose'='register'
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND s.payload->>'register_id'=r.id::text
   AND s.payload->'prior_id'=e.body::jsonb->'prior_id'
   AND s.parent_id IS NOT DISTINCT FROM (e.body::jsonb->>'ledger_id')::bigint
   AND s.reference=NEW.request->>'reference' AND s.result->>'status'='ready'
   AND psl_ppe_schedule_current(s.id) AND psl_ppe_review_current(sr.id)
   AND psl_ppe_policy_current(NEW.case_id,NEW.policy_id)
   AND psl_ppe_grants(NEW.case_id,e.created_by_id,ARRAY['case.read','finance.read','ppe.read','evidence.add'])
   AND EXISTS(SELECT 1 FROM core_audit intake WHERE intake.case_id=NEW.case_id AND intake.actor_id=e.created_by_id
    AND intake.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((intake.action='factory.ppe_intake' AND psl_ppe_grants(NEW.case_id,e.created_by_id,ARRAY['factory.start']))
     OR (intake.action='factory.ppe_source' AND psl_ppe_grants(NEW.case_id,e.created_by_id,ARRAY['factory.manage']))))
   AND sr.verdict='approve' AND rr.verdict='approve' AND sr.snapshot=s.snapshot AND rr.snapshot=r.snapshot
   AND sr.id=(SELECT max(id) FROM finance_schedulereview WHERE work_id=s.id AND authority->>'purpose'='schedule')
   AND rr.id=(SELECT max(id) FROM finance_schedulereview WHERE work_id=r.id AND authority->>'purpose'='register')
   AND NOT EXISTS(SELECT 1 FROM finance_schedulework newer WHERE newer.case_id=NEW.case_id AND
     ((newer.kind=r.kind AND newer.reference=r.reference AND newer.version>r.version) OR
      (newer.kind=s.kind AND newer.reference=s.reference AND newer.version>s.version)))
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text
   AND a.result->>'schedule'=s.id::text AND a.result->>'schedule_sha256'=s.sha256
   AND a.result->>'schedule_review'=sr.id::text AND a.result->>'register_review'=rr.id::text
   AND a.result->'ledger'=COALESCE(to_jsonb(s.parent_id),'null'::jsonb)
   AND a.result->'ledger_posted'='false'::jsonb
   AND a.result->>'full_owner_oracle_acceptance'='unresolved'
   AND (s.parent_id IS NULL OR EXISTS(SELECT 1 FROM finance_financerun note
     JOIN finance_financereview source_review ON source_review.source_id=note.source_id AND source_review.purpose='source'
     WHERE note.id=s.parent_id AND note.case_id=NEW.case_id AND note.kind='mapping'
      AND source_review.verdict='approve'
      AND source_review.id=(SELECT max(id) FROM finance_financereview WHERE source_id=note.source_id AND purpose='source')
      AND note.snapshot->'source_review'->>'id'=source_review.id::text
      AND a.result->'ledger_reviews'=jsonb_build_object('source',note.snapshot->'source_review','rules',note.snapshot->'reviews')))
   AND s.snapshot->>'register_review'=rr.id::text
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(s.snapshot->'policies') pin
     WHERE pin.value->>'status'<>'ACTIVE' OR NOT EXISTS(SELECT 1 FROM policy_configuration pc
      WHERE pc.id=(pin.value->>'id')::bigint AND pc.case_id=NEW.case_id AND pc.component=pin.key
       AND (SELECT state FROM policy_policystate WHERE configuration_id=pc.id ORDER BY id DESC LIMIT 1)='active'))
   AND NOT EXISTS(SELECT 1 FROM (VALUES(sr.actor_id),(rr.actor_id)) reviewer(id)
     WHERE NOT EXISTS(SELECT 1 FROM auth_user u JOIN identity_grant g ON g.user_id=u.id
      WHERE u.id=reviewer.id AND u.is_active AND g.case_id=NEW.case_id AND g.action='ppe.review' AND g.active)))
 THEN RAISE EXCEPTION 'Observed exact current human-reviewed PPE schedule and accounting note required'; END IF;

 IF NEW.definition='finance-schedules/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN core_evidence supplied ON supplied.id=(e.body::jsonb->>'evidence_id')::bigint
  JOIN finance_schedulework s ON s.evidence_id=supplied.id AND s.case_id=NEW.case_id AND s.kind=NEW.request->>'kind' AND s.reference=NEW.request->>'reference'
  JOIN finance_schedulereview r ON r.work_id=s.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND s.parent_id IS NOT DISTINCT FROM (e.body::jsonb->>'parent_id')::bigint
   AND s.payload=CASE WHEN s.kind='income' THEN e.body::jsonb->'payload' ELSE supplied.body::jsonb END
   AND s.result->>'status'='ready' AND psl_schedules_review_current(r.id)
   AND psl_schedules_policy_current(NEW.case_id,NEW.policy_id)
   AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['case.read','finance.read','schedules.read','evidence.add'])
   AND EXISTS(SELECT 1 FROM core_audit intake WHERE intake.case_id=NEW.case_id AND intake.actor_id=e.created_by_id
    AND intake.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((intake.action='factory.schedules_intake' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.start']))
     OR (intake.action='factory.schedules_source' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.manage']))))
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text
   AND a.result->>'schedule'=s.id::text AND a.result->>'schedule_sha256'=s.sha256
   AND a.result->>'schedule_review'=r.id::text AND a.result->>'source_evidence'=supplied.id::text
   AND a.result->'parent'=COALESCE(to_jsonb(s.parent_id),'null'::jsonb)
   AND a.result->'ledger_posted'='false'::jsonb AND a.result->'native_workbook_verified'='false'::jsonb)
 THEN RAISE EXCEPTION 'Observed exact current human-reviewed selected schedule required'; END IF;

 IF TG_OP='UPDATE' AND NEW.definition='finance-forecast/v1' AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id
 AND ((SELECT body::jsonb->>'audience'='group' FROM core_evidence WHERE id=NEW.source_head_id)
 IS DISTINCT FROM (SELECT body::jsonb->>'audience'='group' FROM core_evidence WHERE id=OLD.source_head_id))
 THEN RAISE EXCEPTION 'Separate group audience work identity is immutable'; END IF;

 IF NEW.definition='pmo-weekly-report/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p JOIN documents_version v ON v.id=p.version_id
  JOIN documents_controlledreview rv ON rv.id=p.review_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND p.factory_policy_id=NEW.policy_id
   AND psl_reporting_document(NEW.id,NEW.source_head_id,v.id)
   AND rv.version_id=v.id AND rv.verdict='approve' AND rv.payload_sha256=v.payload_sha256
   AND rv.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
   AND psl_reporting_review(NEW.case_id,rv.id)
   AND psl_reporting_principals(NEW.id,v.id,p.actor_id)
   AND psl_reporting_distribution(NEW.case_id,v.id,p.policies,p.recipient_ids,p.retention_days)
   AND psl_reporting_grants(NEW.case_id,p.actor_id,ARRAY['case.read','report.read','factory.execute','document.publish'])
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=NEW.source_head_id::text AND a.result->>'document_version'=v.id::text
   AND a.result->>'publication'=p.id::text AND a.result->'complete_project_coverage'='false'::jsonb AND a.result->'external_delivery_verified'='false'::jsonb AND a.result->'business_approval_granted'='false'::jsonb
   AND jsonb_array_length(p.recipient_ids)>0
   AND (SELECT count(*) FROM documents_publicationreceipt WHERE publication_id=p.id)=jsonb_array_length(p.recipient_ids)
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint
     AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256 AND psl_reporting_grants(NEW.case_id,pr.recipient_id,ARRAY['document.receive:client']))))
 THEN RAISE EXCEPTION 'Observed exact current weekly client report, native PMO Lead review and every recipient receipt required'; END IF;

 IF NEW.definition='pmo-escalation/v1' AND NEW.status='verified' AND NOT EXISTS(
 SELECT 1 FROM documents_publication p JOIN documents_version v ON v.id=p.version_id JOIN documents_publicationjob j ON j.publication_id=p.id
 JOIN pmo_escalationdocumentbinding b ON b.version_id=v.id JOIN pmo_escalationrequest r ON r.id=b.request_id JOIN pmo_escalationprofile ep ON ep.id=r.profile_id
 JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13' JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
 WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND p.factory_policy_id=NEW.policy_id AND j.status='confirmed'
 AND psl_escalation_document(NEW.id,v.id,p.review_id,p.actor_id,p.factory_policy_id,p.factory_source_id,p.recipient_ids,p.policies)
 AND a.result->'verified'='true'::jsonb AND a.result->'issue_resolution_verified'='false'::jsonb AND a.result->>'head'=NEW.source_head_id::text
 AND a.result->>'verification_scope'='reviewed_escalation_communication' AND a.result->>'request'=r.id::text AND a.result->>'profile'=ep.id::text AND a.result->>'issue_state'=ep.state_id::text
 AND a.result->'decision'=COALESCE(to_jsonb(b.decision_id),'null'::jsonb) AND a.result->>'direction'=r.direction AND a.result->>'target'=r.target
 AND a.result->>'document_version'=v.id::text AND a.result->>'publication'=p.id::text
 AND a.result->'receipt_ids'=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
 AND (SELECT count(*) FROM documents_publicationreceipt WHERE publication_id=p.id)=jsonb_array_length(p.recipient_ids)
 AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256)))
 THEN RAISE EXCEPTION 'Observed exact current communication and every receipt required; issue resolution is not verified'; END IF;

 IF NEW.definition='pmo-minutes/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN core_evidence note ON note.id=(e.body::jsonb->>'evidence_id')::bigint AND note.case_id=e.case_id
   JOIN documents_template t ON t.id=(e.body::jsonb->>'template_id')::bigint AND t.case_id=e.case_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_minutes_intake'
    AND e.body::jsonb->>'protocol'='factory-minutes-intake/v1' AND note.kind='meeting_notes'
    AND t.definition->>'document_type'='minutes' AND t.definition->'audience_fields' ? (e.body::jsonb->>'audience')
    AND (e.body::jsonb->>'audience'='internal' AND e.body::jsonb->'publish'='false'::jsonb OR e.body::jsonb->>'audience'='client' AND e.body::jsonb->'publish'='true'::jsonb)
    AND e.body::jsonb - ARRAY['protocol','meeting_version_id','evidence_id','template_id','audience','publish']='{}'::jsonb
    AND a.action IN ('factory.minutes_intake','factory.minutes_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND encode(sha256(convert_to(e.body,'UTF8')),'hex')=e.sha256)
   THEN RAISE EXCEPTION 'Exact authorized typed formal-minutes intake required'; END IF;
  IF NEW.status='verified' AND NOT EXISTS(
   SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
   WHERE fa.work_id=NEW.id AND fa.kind='ACT13' AND a.phase='observed'
    AND a.result->'verified'='true'::jsonb AND a.result->>'head'=NEW.source_head_id::text
    AND a.result->'actions_completed'='false'::jsonb AND a.result->'scope_changed'='false'::jsonb
    AND psl_minutes_current(NEW.id,NEW.source_head_id,(a.result->>'document_version')::bigint)
    AND psl_schedules_policy_current(NEW.case_id,NEW.policy_id)
    AND a.result->'manifest'=(SELECT manifest FROM pmo_minutesreportbinding WHERE version_id=(a.result->>'document_version')::bigint)
    AND ((SELECT body::jsonb->'publish' FROM core_evidence WHERE id=NEW.source_head_id)='false'::jsonb OR EXISTS(
     SELECT 1 FROM documents_publication p JOIN documents_controlledreview r ON r.id=p.review_id JOIN documents_version v ON v.id=p.version_id
     WHERE p.id=(a.result->>'publication')::bigint AND p.version_id=(a.result->>'document_version')::bigint
      AND p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND p.factory_policy_id=NEW.policy_id
      AND r.version_id=v.id AND r.verdict='approve' AND r.payload_sha256=v.payload_sha256
      AND r.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
      AND psl_schedules_authority_current(NEW.case_id,r.authority)
      AND psl_schedules_grants(NEW.case_id,r.actor_id,ARRAY['document.review_controlled'])
      AND psl_schedules_authority_current(NEW.case_id,p.policies)
      AND p.actor_id=(psl_schedules_values(NEW.policy_id)->0->>'executor_id')::bigint
      AND psl_schedules_grants(NEW.case_id,p.actor_id,ARRAY['case.read','meeting.read','factory.execute','document.publish'])
      AND p.recipient_ids=(SELECT jsonb_agg(DISTINCT (recipient->>'user_id')::bigint ORDER BY (recipient->>'user_id')::bigint)
       FROM jsonb_array_elements(psl_schedules_values((p.policies->>'D11.recipient_grant_refs')::bigint)) recipient WHERE recipient->>'audience'=v.audience)
      AND p.retention_days=(psl_schedules_values((p.policies->>'D11.template_storage_retention_rules')::bigint)->0->>'retention_days')::integer
      AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT psl_schedules_grants(NEW.case_id,recipient::bigint,ARRAY['document.receive:'||v.audience]))
      AND jsonb_array_length(p.recipient_ids)>0
      AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(
       SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint
        AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256)))))
   THEN RAISE EXCEPTION 'Observed current human-confirmed minutes and exact requested recipient receipts required'; END IF;
 END IF;

 IF NEW.definition='finance-bu/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN finance_buwork w ON w.case_id=NEW.case_id AND w.kind=NEW.request->>'mode'
  JOIN finance_bureport p ON p.work_id=w.id JOIN finance_bureview rv ON rv.id=p.review_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  JOIN policy_configuration pc ON pc.id=(p.policy_ids->>'BU.disclosure_rules')::bigint
  WHERE e.id=NEW.source_head_id AND w.reference='factory-bu-'||NEW.id::text
   AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['case.read','bu.read','bu.private.read','evidence.add'])
   AND EXISTS(SELECT 1 FROM core_audit origin WHERE origin.case_id=NEW.case_id AND origin.actor_id=e.created_by_id
    AND origin.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((origin.action='factory.bu_intake' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.start']))
     OR (origin.action='factory.bu_source' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.manage']))))
   AND w.metadata->>'status'='complete' AND w.payload->'conserved'='true'::jsonb
   AND psl_bu_current(w.id) AND psl_bu_review(rv.id) AND psl_bu_private(w.id,p.actor_id) AND psl_bu_authority(w.id,p.actor_id,'publish',p.policy_ids)
   AND (COALESCE(w.metadata->'historical','false'::jsonb)='false'::jsonb OR EXISTS(SELECT 1 FROM finance_bureview history WHERE history.work_id=w.id AND history.purpose='historical' AND psl_bu_review(history.id)))
   AND rv.work_id=w.id AND rv.purpose=w.kind AND rv.verdict='approve' AND rv.subject_sha256=w.sha256
   AND rv.id=(SELECT max(id) FROM finance_bureview WHERE work_id=w.id AND purpose=w.kind)
   AND NOT EXISTS(SELECT 1 FROM finance_buwork newer WHERE newer.case_id=w.case_id AND newer.kind=w.kind AND newer.reference=w.reference AND newer.version>w.version AND newer.metadata->'accepted'='true'::jsonb)
   AND NOT EXISTS(SELECT 1 FROM finance_bureport newer JOIN finance_buwork nw ON nw.id=newer.work_id WHERE nw.case_id=w.case_id AND nw.kind=w.kind AND nw.metadata->'scope'=w.metadata->'scope' AND newer.id>p.id)
   AND ((w.kind='staff' AND w.payroll_id=(e.body::jsonb->'inputs'->>'payroll_id')::bigint AND w.metadata->'rule_ids'=e.body::jsonb->'inputs'->'rule_ids')
    OR (w.kind='event' AND w.parent_id=(e.body::jsonb->'inputs'->>'source_id')::bigint AND w.metadata->'comparison'=e.body::jsonb->'inputs'->'comparison'))
   AND psl_schedules_policy_current(NEW.case_id,pc.id)
   AND psl_schedules_grants(NEW.case_id,p.actor_id,ARRAY['case.read','bu.read','bu.private.read','bu.publish'])
   AND psl_schedules_grants(NEW.case_id,rv.actor_id,ARRAY['case.read','bu.read','bu.private.read','bu.review'])
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(w.metadata->'policy_ids') pin WHERE NOT psl_schedules_policy_current(NEW.case_id,(pin.value#>>'{}')::bigint))
   AND p.payload-ARRAY['entity','period','currency','unit','by_bu','company_source_total','allocated_total','company_only','residual','conserved','source_work','coverage','native_authenticity_verified','destination','ledger_posted','source_written','disclosure']='{}'::jsonb
   AND p.payload->>'disclosure'='aggregate_only' AND NOT (p.payload ? 'rows') AND p.payload->'ledger_posted'='false'::jsonb AND p.payload->'source_written'='false'::jsonb
   AND p.payload->>'source_work'=w.id::text AND p.payload->'by_bu'=w.payload->'by_bu'
   AND p.payload->'company_source_total'=w.payload->'source_total' AND p.payload->'allocated_total'=w.payload->'allocated_total' AND p.payload->'residual'=w.payload->'residual'
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'work'=w.id::text AND a.result->>'publication'=p.id::text
   AND a.result->'private_payloads_in_result'='false'::jsonb AND a.result->'source_written'='false'::jsonb AND a.result->'ledger_posted'='false'::jsonb
   AND jsonb_array_length(psl_schedules_values(pc.id)->0->'recipient_ids')>0
   AND (SELECT count(*) FROM finance_bureceipt WHERE report_id=p.id)=jsonb_array_length(psl_schedules_values(pc.id)->0->'recipient_ids')
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(psl_schedules_values(pc.id)->0->'recipient_ids') recipient WHERE NOT EXISTS(
    SELECT 1 FROM finance_bureceipt rr WHERE rr.report_id=p.id AND rr.actor_id=recipient::bigint
     AND a.result->'receipt_ids' @> to_jsonb(ARRAY[rr.id])
     AND psl_schedules_grants(NEW.case_id,rr.actor_id,ARRAY['case.read','bu.read','bu.report.read','bu.receive']))))
 THEN RAISE EXCEPTION 'Observed exact reviewed BU aggregate and actual recipient-owned receipts required'; END IF;
 RETURN NEW;
END $$;"""

PREVIOUS_TASK = r"""CREATE OR REPLACE FUNCTION psl_factory_task_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='UPDATE' AND (NEW.kind,NEW.context,NEW.factory_key) IS DISTINCT FROM (OLD.kind,OLD.context,OLD.factory_key)
 THEN RAISE EXCEPTION 'Human task packet and source identity are immutable'; END IF;
 IF NEW.kind='document_review' AND NEW.version_id IS NULL THEN RAISE EXCEPTION 'Document review version required'; END IF;
 IF NEW.kind<>'document_review' AND (NEW.version_id IS NOT NULL OR NEW.factory_key IS NULL OR NEW.kind NOT IN ('factory_information','factory_review','factory_governance','factory_accounting_review'))
 THEN RAISE EXCEPTION 'Closed factory task contract required'; END IF;
 RETURN NEW;
END $$;
"""

IDENTITY = r"""CREATE OR REPLACE FUNCTION psl_factory_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Factory history cannot be deleted'; END IF;
 IF TG_OP='UPDATE' THEN
  IF (NEW.case_id,NEW.actor_id,NEW.key,NEW.definition,NEW.request,NEW.request_hash,NEW.created_at)
    IS DISTINCT FROM (OLD.case_id,OLD.actor_id,OLD.key,OLD.definition,OLD.request,OLD.request_hash,OLD.created_at)
    OR NEW.budget_used<OLD.budget_used OR NEW.fence<OLD.fence OR NEW.revision<OLD.revision
    OR (OLD.budget_used>0 AND NEW.budget_limit<>OLD.budget_limit)
  THEN RAISE EXCEPTION 'Immutable factory identity and monotonic shared budget required'; END IF;
  IF OLD.source_head_id IS NOT NULL AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id
   AND (NEW.source_head_id IS NULL OR NOT EXISTS(SELECT 1 FROM core_evidence n JOIN core_evidence o ON o.id=OLD.source_head_id WHERE n.id=NEW.source_head_id AND n.version>o.version))
  THEN RAISE EXCEPTION 'Forward native source successor required'; END IF;
 END IF;
 IF NEW.definition NOT IN ('pmo-issues/v1','finance-ledger/v1','engagement/v1','pmo-minutes/v1','pmo-finance/v1','planning/v1','commercial/v1','delivery-release/v1','delivery-hypercare/v1','delivery-archive/v1','delivery-handover/v1','delivery-closure/v1','delivery-go-live/v1','finance-accounts/v1','rfp-response/v1','finance-schedules/v1','finance-ppe/v1','pmo-change/v1','finance-forecast/v1','finance-payroll/v1','pmo-emergency/v1','finance-bu/v1','pmo-weekly-report/v1','pmo-leadership-report/v1','pmo-escalation/v1') THEN RAISE EXCEPTION 'Closed factory definition required'; END IF;
 IF (NEW.invoice_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_invoice i WHERE i.id=NEW.invoice_id AND i.case_id=NEW.case_id))
  OR (NEW.preparation_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_billingpreparation p WHERE p.id=NEW.preparation_id AND p.case_id=NEW.case_id))
  OR (NEW.policy_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM policy_configuration p WHERE p.id=NEW.policy_id AND p.case_id=NEW.case_id
    AND p.component=CASE NEW.definition WHEN 'pmo-issues/v1' THEN 'OPS.factory_issue_execution' WHEN 'finance-ledger/v1' THEN 'OPS.factory_ledger_execution' WHEN 'engagement/v1' THEN 'OPS.factory_engagement_execution' WHEN 'pmo-minutes/v1' THEN 'OPS.factory_minutes_execution' WHEN 'planning/v1' THEN 'OPS.factory_planning_execution' WHEN 'commercial/v1' THEN 'OPS.factory_commercial_execution' WHEN 'delivery-release/v1' THEN 'OPS.factory_delivery_execution' WHEN 'delivery-hypercare/v1' THEN 'OPS.factory_hypercare_execution' WHEN 'delivery-archive/v1' THEN 'OPS.factory_archive_execution' WHEN 'delivery-handover/v1' THEN 'OPS.factory_handover_execution' WHEN 'delivery-closure/v1' THEN 'OPS.factory_closure_execution' WHEN 'delivery-go-live/v1' THEN 'OPS.factory_go_live_execution' WHEN 'finance-schedules/v1' THEN 'OPS.factory_schedules_execution' WHEN 'pmo-escalation/v1' THEN 'OPS.factory_escalation_execution' WHEN 'finance-ppe/v1' THEN 'OPS.factory_ppe_execution' WHEN 'pmo-change/v1' THEN 'OPS.factory_change_execution' WHEN 'finance-bu/v1' THEN 'OPS.factory_bu_execution' WHEN 'finance-forecast/v1' THEN 'OPS.factory_forecast_execution' WHEN 'finance-payroll/v1' THEN 'OPS.factory_payroll_execution' WHEN 'pmo-emergency/v1' THEN 'OPS.factory_emergency_execution' WHEN 'pmo-weekly-report/v1' THEN 'OPS.factory_reporting_execution' WHEN 'pmo-leadership-report/v1' THEN 'OPS.factory_leadership_execution' WHEN 'finance-accounts/v1' THEN 'OPS.factory_accounting_execution' WHEN 'rfp-response/v1' THEN 'OPS.factory_rfp_execution' ELSE 'OPS.factory_execution' END))
 THEN RAISE EXCEPTION 'Same-case native factory references required'; END IF;
 IF NEW.definition='pmo-finance/v1' AND NEW.source_head_id IS NOT NULL THEN RAISE EXCEPTION 'Invoice work cannot carry a domain source head'; END IF;
 IF NEW.definition='planning/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
    SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='planning_packet' AND a.action='planning.recorded'
    AND a.data=jsonb_build_object('kind','packet','evidence_id',e.id,'sha256',e.sha256) AND e.body::jsonb->'engagement_id'=NEW.request->'engagement')
  THEN RAISE EXCEPTION 'Native same-engagement planning packet required'; END IF;
 END IF;
 IF NEW.definition='commercial/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
    SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_commercial_intake'
    AND e.body::jsonb->>'protocol'='factory-commercial-intake/v1' AND a.action='factory.commercial_intake'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native private commercial intake required'; END IF;
 END IF;

 IF NEW.definition='delivery-release/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_delivery_intake'
    AND d.case_id=NEW.case_id AND e.body::jsonb->>'protocol'='factory-delivery-intake/v1'
    AND e.body::jsonb->>'dossier_id'=d.id::text AND a.action='factory.delivery_intake'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case delivery intake and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-hypercare/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_delivery_intake'
    AND d.case_id=NEW.case_id AND e.body::jsonb->>'protocol'='factory-delivery-intake/v1'
    AND e.body::jsonb->>'dossier_id'=d.id::text AND a.action='factory.delivery_intake'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case delivery intake and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-archive/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_archive_intake'
    AND e.body::jsonb->>'protocol'='factory-archive-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inventory']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inventory')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.archive_intake','factory.archive_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case declared archive intake and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-handover/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_handover_intake'
    AND e.body::jsonb->>'protocol'='factory-handover-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.handover_intake','factory.handover_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case handover input provenance and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-closure/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_closure_intake'
    AND e.body::jsonb->>'protocol'='factory-closure-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.closure_intake','factory.closure_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case closure input provenance and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-go-live/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_go_live_intake'
    AND e.body::jsonb->>'protocol'='factory-go-live-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.go_live_intake','factory.go_live_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case go_live input provenance and dossier required'; END IF;
 END IF;

 IF NEW.definition='finance-accounts/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN finance_financesource s ON s.id=(e.body::jsonb->>'source')::bigint
   JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_accounting_intake'
    AND e.body::jsonb->>'schema'='factory-accounting-intake/v1' AND s.case_id=NEW.case_id
    AND s.batch_id=(NEW.request->>'batch')::bigint AND s.entity=NEW.request->>'entity'
    AND e.body::jsonb->'batch'=NEW.request->'batch' AND e.body::jsonb->'entity'=NEW.request->'entity'
    AND e.body::jsonb->'reference'=NEW.request->'reference'
    AND a.action='factory.accounting_inputs_recorded'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native exact accounting intake/source references required'; END IF;
 END IF;

 IF NEW.definition='pmo-change/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_changeversion v ON v.id=(e.body::jsonb->>'change_version_id')::bigint
   JOIN pmo_changerequest c ON c.id=v.change_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_change_intake'
    AND c.case_id=NEW.case_id AND c.id=(NEW.request->>'change')::bigint
    AND e.body::jsonb->>'protocol'='factory-change-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','change_version_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object'
    AND a.action IN ('factory.change_intake','factory.change_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-project native change intake provenance required'; END IF;
 END IF;

 IF NEW.definition='pmo-emergency/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_emergencyprofile ep ON ep.id=(e.body::jsonb->>'profile_id')::bigint
   JOIN pmo_changeversion cv ON cv.id=ep.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_emergency_intake'
    AND cr.case_id=NEW.case_id AND cr.id=(NEW.request->>'change')::bigint AND cv.category='Emergency' AND cv.incident_id IS NOT NULL
    AND e.body::jsonb->>'protocol'='factory-emergency-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','profile_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object'
    AND a.action IN ('factory.emergency_intake','factory.emergency_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-project incident-linked native Emergency source required'; END IF;
 END IF;

 IF NEW.definition='finance-payroll/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN finance_payrollrequest q ON q.id=(e.body::jsonb->>'request_id')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_payroll_intake'
    AND q.case_id=NEW.case_id AND q.reference=NEW.request->>'payroll_reference'
    AND e.body::jsonb->>'protocol'='factory-payroll-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','request_id','inputs']='{}'::jsonb
    AND (e.body::jsonb->'inputs')-ARRAY['input_ids','hr_snapshot_id']='{}'::jsonb
    AND jsonb_array_length(e.body::jsonb->'inputs'->'input_ids')=2
    AND (SELECT count(DISTINCT i.provider) FROM finance_payrollinput i
      WHERE i.id IN (SELECT value::bigint FROM jsonb_array_elements_text(e.body::jsonb->'inputs'->'input_ids'))
       AND i.request_id=q.id AND i.metadata->'accepted'='true'::jsonb)=2
    AND a.action IN ('factory.payroll_intake','factory.payroll_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-workspace restricted payroll provenance required'; END IF;
 END IF;

 IF NEW.definition='finance-ppe/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN finance_schedulework r ON r.id=(e.body::jsonb->>'register_id')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_ppe_intake'
    AND r.case_id=NEW.case_id AND r.kind='ppe_register' AND r.reference=NEW.request->>'register_reference'
    AND e.body::jsonb->>'protocol'='factory-ppe-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','register_id','prior_id','ledger_id']='{}'::jsonb
    AND a.action IN ('factory.ppe_intake','factory.ppe_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-case native PPE register provenance required'; END IF;
 END IF;

 IF NEW.definition='finance-schedules/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN core_evidence supplied ON supplied.id=(e.body::jsonb->>'evidence_id')::bigint AND supplied.case_id=e.case_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_schedules_intake'
    AND e.body::jsonb->>'protocol'='factory-schedules-intake/v1' AND e.body::jsonb->>'kind'=NEW.request->>'kind'
    AND e.body::jsonb-ARRAY['protocol','kind','parent_id','evidence_id','payload']='{}'::jsonb
    AND ((NEW.request->>'kind'='inventory' AND supplied.kind='schedule_inventory' AND e.body::jsonb->'payload'='null'::jsonb AND e.body::jsonb->'parent_id'='null'::jsonb)
     OR (NEW.request->>'kind'='income' AND supplied.kind='income_detail' AND EXISTS(SELECT 1 FROM finance_financerun n WHERE n.id=(e.body::jsonb->>'parent_id')::bigint AND n.case_id=NEW.case_id AND n.kind='mapping')))
    AND a.action IN ('factory.schedules_intake','factory.schedules_source') AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact native schedule source provenance required'; END IF;
 END IF;

 IF NEW.definition='pmo-weekly-report/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_reporting_intake'
    AND e.body::jsonb->>'protocol'='factory-weekly-report-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','inputs','manifest','captured_at']='{}'::jsonb
    AND (e.body::jsonb->'inputs')-ARRAY['template_id','content_id','start_at','end_at']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'manifest')='object'
    AND e.body::jsonb->'inputs'->>'start_at'=NEW.request->>'start_at' AND e.body::jsonb->'inputs'->>'end_at'=NEW.request->>'end_at'
    AND NEW.request->>'kind'='weekly_client' AND NEW.request->>'audience'='client'
    AND a.action IN ('factory.reporting_intake','factory.reporting_source') AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact private selected-period weekly report source required'; END IF;
 END IF;

 IF NEW.definition='pmo-escalation/v1' AND (NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
 SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
 JOIN pmo_escalationrequest r ON r.id=(psl_escalation_intake(e.id)->>'request_id')::bigint JOIN pmo_escalationprofile ep ON ep.id=r.profile_id
 JOIN pmo_issuestate s ON s.id=ep.state_id JOIN pmo_issue i ON i.id=s.issue_id
 WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND i.case_id=NEW.case_id AND i.id=(NEW.request->>'issue')::bigint
 AND e.kind='agent_private_escalation_intake' AND psl_escalation_intake(e.id)->>'protocol'='factory-escalation-intake/v1'
 AND (psl_escalation_intake(e.id)-ARRAY['protocol','request_id','profile_id','template_id'])='{}'::jsonb AND psl_escalation_intake(e.id)->>'profile_id'=ep.id::text
 AND r.direction=NEW.request->>'direction' AND r.target=NEW.request->>'target'
 AND a.action IN ('factory.escalation_intake','factory.escalation_source') AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)))
 THEN RAISE EXCEPTION 'Exact same-case source-bound escalation request required'; END IF;

 IF NEW.definition='finance-bu/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_bu_intake'
    AND e.sha256=encode(sha256(convert_to(e.body,'UTF8')),'hex')
    AND e.body::jsonb->>'protocol'='factory-bu-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','inputs']='{}'::jsonb
    AND (e.body::jsonb->'inputs')-ARRAY['mode','payroll_id','source_id','rule_ids','comparison']='{}'::jsonb
    AND e.body::jsonb->'inputs'->>'mode'=NEW.request->>'mode'
    AND jsonb_array_length(e.body::jsonb->'inputs'->'rule_ids')<=100
    AND a.action IN ('factory.bu_intake','factory.bu_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((NEW.request->>'mode'='staff' AND EXISTS(SELECT 1 FROM finance_payrollrun r JOIN finance_payrollrequest q ON q.id=r.request_id
      WHERE r.id=(e.body::jsonb->'inputs'->>'payroll_id')::bigint AND r.kind='match' AND q.case_id=NEW.case_id
       AND q.reference=NEW.request->>'source_reference' AND NEW.request->'scope'=jsonb_build_object('entity',q.metadata->'entity','period',q.metadata->'period','currency',q.metadata->'currency')
       AND e.body::jsonb->'inputs'->'source_id'='null'::jsonb AND e.body::jsonb->'inputs'->'comparison'='null'::jsonb
       AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(e.body::jsonb->'inputs'->'rule_ids') ri WHERE NOT EXISTS(
        SELECT 1 FROM finance_buwork rule WHERE rule.id=ri::bigint AND rule.case_id=NEW.case_id AND rule.kind='rule' AND rule.payroll_id=r.id))))
     OR (NEW.request->>'mode'='event' AND EXISTS(SELECT 1 FROM finance_buwork s
      WHERE s.id=(e.body::jsonb->'inputs'->>'source_id')::bigint AND s.case_id=NEW.case_id AND s.kind='source'
       AND s.reference=NEW.request->>'source_reference' AND s.metadata->'accepted'='true'::jsonb AND s.metadata->'scope'=NEW.request->'scope'
       AND e.body::jsonb->'inputs'->'payroll_id'='null'::jsonb AND e.body::jsonb->'inputs'->'rule_ids'='[]'::jsonb
       AND (e.body::jsonb->'inputs'->'comparison'='null'::jsonb OR EXISTS(SELECT 1 FROM finance_financerun fr
        WHERE fr.id=(e.body::jsonb->'inputs'->'comparison'->>'run_id')::bigint AND fr.case_id=NEW.case_id AND fr.kind='allocation'))))))
  THEN RAISE EXCEPTION 'Exact scoped native BU intake required'; END IF;
 END IF;
 IF NEW.status='verified' THEN
  IF NEW.definition='pmo-finance/v1' AND NOT EXISTS(
    SELECT 1 FROM finance_invoiceissue i JOIN finance_invoicedelivery d ON d.invoice_id=i.invoice_id JOIN finance_invoice n ON n.id=i.invoice_id
    WHERE n.id=NEW.invoice_id AND n.case_id=NEW.case_id AND i.sha256=n.sha256 AND i.payload=n.payload)
  THEN RAISE EXCEPTION 'Native invoice receipts required; agent completion is not verification'; END IF;
  IF NEW.definition='planning/v1' AND NOT EXISTS(
    SELECT 1 FROM pmo_deliverysource s JOIN pmo_deliverydossier d ON d.id=s.dossier_id JOIN core_evidence e ON e.id=s.evidence_id
    JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE d.case_id=NEW.case_id AND e.case_id=NEW.case_id AND e.kind='planning_readiness' AND s.kind='scope_baseline'
    AND e.body::jsonb->>'packet_id'=NEW.source_head_id::text AND e.body::jsonb->'inputs'->>'candidate_id'=d.candidate_id::text
    AND s.external_ref='psl:planning-readiness:'||e.id::text AND a.action='planning.recorded'
    AND a.data=jsonb_build_object('kind','ready','evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native planning readiness and delivery source required'; END IF;
  IF NEW.definition='commercial/v1' AND NOT EXISTS(
    SELECT 1 FROM pmo_commercialdocumentbinding b JOIN documents_version v ON v.id=b.version_id JOIN documents_document doc ON doc.id=v.document_id
    JOIN documents_publication p ON p.version_id=v.id JOIN pmo_commercialrevision r ON r.id=b.revision_id
    JOIN pmo_commercialcase c ON c.id=r.dossier_id JOIN pmo_costingbinding cb ON cb.costing_id=(r.sources->>'costing')::bigint
    JOIN pmo_costingrun cr ON cr.id=cb.run_id JOIN core_evidence e ON e.id=NEW.source_head_id
    WHERE c.case_id=NEW.case_id AND doc.case_id=NEW.case_id AND cr.case_id=NEW.case_id AND c.current_id=r.id AND cr.result->>'status'='known'
    AND r.sources->'requirements'=e.body::jsonb->'sources'->'requirements' AND r.sources->'plan'=e.body::jsonb->'sources'->'plan'
    AND r.sources->'engineering_estimate'=e.body::jsonb->'sources'->'engineering_estimate' AND r.sources->'security_estimate'=e.body::jsonb->'sources'->'security_estimate'
    AND r.sources->'sow'=e.body::jsonb->'sources'->'sow' AND cr.evidence_id::text=e.body::jsonb->'sources'->>'inputs'
    AND jsonb_array_length(p.recipient_ids)>0 AND NOT EXISTS(
      SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) AS destinations(recipient) WHERE NOT EXISTS(
       SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id::text=destinations.recipient
       AND pr.payload_sha256=v.payload_sha256 AND pr.payload=v.payload)))
  THEN RAISE EXCEPTION 'Exact native costing, commercial document and all recipient receipts required'; END IF;
 END IF;

 IF NEW.definition='delivery-release/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='release_ready'
   AND r.snapshot->'deployment_authorized'='false'::jsonb AND r.snapshot->>'financial_controls'='independent'
   AND a.phase='observed' AND a.result->>'release_ready'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Native source-bound release evidence required; no deployment authority is granted'; END IF;

 IF NEW.definition='delivery-hypercare/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='hypercare'
   AND r.snapshot->'qualified'='true'::jsonb
   AND a.phase='observed' AND a.result->>'hypercare'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Native source-bound qualified hypercare required; no closure or release authority is granted'; END IF;

 IF NEW.definition='delivery-archive/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN core_evidence e ON e.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='archive'
   AND r.data->'inventory'=e.body::jsonb->'inventory'
   AND r.snapshot->'physical_purge_performed'='false'::jsonb
   AND r.snapshot->>'repository'='internal-versioned'
   AND a.phase='observed' AND a.result->>'archive'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Exact observed native archive index required; no physical purge or closure authority'; END IF;

 IF NEW.definition='delivery-handover/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p JOIN documents_publicationreceipt r ON r.publication_id=p.id
  JOIN pmo_deliverydocumentbinding b ON b.version_id=p.version_id
  JOIN pmo_deliveryrecord h ON h.dossier_id=b.dossier_id AND h.kind='handover'
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND b.purpose='handover'
   AND b.dossier_id=(NEW.request->>'dossier')::bigint AND h.data->>'receipt_id'=r.id::text
   AND h.data->>'status'='received' AND h.actor_id=r.recipient_id
   AND a.phase='observed' AND fa.kind='ACT13' AND a.result->'verified'='true'::jsonb
   AND a.result->>'publication'=p.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native handover and actual recipient acknowledgement required'; END IF;

 IF NEW.definition='delivery-closure/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord c JOIN pmo_deliverydocumentbinding b ON b.version_id=(c.data->>'version_id')::bigint
  JOIN documents_version v ON v.id=b.version_id
  JOIN pmo_deliveryrecord decision ON decision.id=(c.data->>'decision_id')::bigint
  JOIN core_evidence head ON head.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE c.dossier_id=(NEW.request->>'dossier')::bigint AND c.kind='closure' AND b.dossier_id=c.dossier_id AND b.purpose='closure'
   AND decision.dossier_id=c.dossier_id AND decision.kind='closure_decision' AND decision.data->>'verdict'='approve'
   AND decision.data->>'version_id'=v.id::text AND decision.snapshot=b.snapshot AND c.snapshot=b.snapshot
   AND b.data=(head.body::jsonb->'inputs')-'template_id' AND v.template_id=(head.body::jsonb->'inputs'->>'template_id')::bigint
   AND a.result->'verified'='true'::jsonb AND a.result->>'closure'=c.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native closure, prescribed decision and current source binding required'; END IF;

 IF NEW.definition='delivery-go-live/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p JOIN documents_publicationreceipt r ON r.publication_id=p.id
  JOIN documents_version v ON v.id=p.version_id JOIN pmo_deliverydocumentbinding b ON b.version_id=v.id
  JOIN pmo_deliveryrecord g ON g.dossier_id=b.dossier_id AND g.kind IN ('go_live','go_live_reaffirmation')
  JOIN core_evidence pm ON pm.id=(g.data->>'pm_signature_id')::bigint
  JOIN core_evidence client ON client.id=(g.data->>'client_signature_id')::bigint
  JOIN core_evidence head ON head.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND b.purpose='go_live' AND v.audience='client'
   AND b.dossier_id=(NEW.request->>'dossier')::bigint AND g.data->>'receipt_id'=r.id::text AND g.snapshot=b.snapshot
   AND b.data=(head.body::jsonb->'inputs')-'template_id' AND v.template_id=(head.body::jsonb->'inputs'->>'template_id')::bigint
   AND pm.case_id=NEW.case_id AND client.case_id=NEW.case_id AND pm.kind='signature' AND client.kind='signature' AND pm.id<>client.id
   AND a.result->'verified'='true'::jsonb AND a.result->>'acceptance'=g.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native go-live acceptance, distinct actual signature evidence and source-bound client receipt required'; END IF;

 IF NEW.definition='finance-accounts/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM finance_financerun r JOIN finance_financesource s ON s.id=r.source_id
  JOIN finance_financedocumentbinding b ON b.run_id=r.id
  JOIN documents_version v ON v.id=b.version_id JOIN documents_document d ON d.id=v.document_id
  JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
  JOIN core_evidence h ON h.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE r.case_id=NEW.case_id AND s.case_id=NEW.case_id AND d.case_id=NEW.case_id AND r.kind='formula'
   AND s.id=(h.body::jsonb->>'source')::bigint AND s.batch_id=(NEW.request->>'batch')::bigint
   AND (p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id OR p.factory_work_id IS NULL)
   AND d.current_id=v.id AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint))
   AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
   AND EXISTS(SELECT 1 FROM finance_financereview fr WHERE fr.run_id=r.id AND fr.purpose='output' AND fr.verdict='approve'
    AND fr.id=(SELECT max(last.id) FROM finance_financereview last WHERE last.run_id=r.id AND last.purpose='output'))
   AND a.result->'verified'='true'::jsonb AND a.result->>'run'=r.id::text AND a.result->>'source'=s.id::text
   AND a.result->>'binding'=b.id::text AND a.result->>'publication'=p.id::text AND a.result->>'document_version'=v.id::text
   AND a.result->'receipt_ids'=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)) AND NOT EXISTS(
  SELECT 1 FROM finance_financerun r JOIN finance_financesource s ON s.id=r.source_id
  JOIN finance_financedocumentbinding b ON b.run_id=r.id
  JOIN documents_version v ON v.id=b.version_id JOIN documents_document d ON d.id=v.document_id
  JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
  JOIN core_evidence h ON h.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE r.case_id=NEW.case_id AND s.case_id=NEW.case_id AND d.case_id=NEW.case_id AND r.kind='statement'
   AND s.id=(h.body::jsonb->>'source')::bigint AND s.batch_id=(NEW.request->>'batch')::bigint
   AND (p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id OR p.factory_work_id IS NULL)
   AND d.current_id=v.id AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint))
   AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
   AND EXISTS(SELECT 1 FROM finance_financereview fr WHERE fr.run_id=r.id AND fr.purpose='output' AND fr.verdict='approve'
    AND fr.id=(SELECT max(last.id) FROM finance_financereview last WHERE last.run_id=r.id AND last.purpose='output'))
   AND a.result->'verified'='true'::jsonb AND a.result->>'run'=r.id::text AND a.result->>'source'=s.id::text
   AND a.result->>'binding'=b.id::text AND a.result->>'publication'=p.id::text AND a.result->>'document_version'=v.id::text
   AND a.result->'receipt_ids'=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
   AND EXISTS(SELECT 1 FROM policy_configuration pc JOIN policy_registeredreference pr ON pr.case_id=pc.case_id
    AND pr.ref=pc.envelope->'value'->>'artifact_ref' AND pr.version=(pc.envelope->'value'->>'artifact_version')::integer
    AND pr.sha256=pc.envelope->'value'->>'sha256'
    WHERE pc.id=NEW.policy_id AND pc.component='OPS.factory_accounting_execution'
     AND pr.schema_ref='schema:psl/factory-accounting-execution/v3' AND pr.content->>'statement_contract_id'=r.request->>'contract_id')
   AND r.result->>'status'='complete' AND r.result->>'scope'='selected_statement_lines'
   AND r.result->'whole_statement_certified'='false'::jsonb
   AND EXISTS(SELECT 1 FROM finance_financereview cr JOIN policy_configuration cc ON cc.id=cr.configuration_id
    WHERE cc.id=(r.request->>'contract_id')::bigint AND cc.case_id=r.case_id AND cc.component='D06.statement_contract'
     AND cr.purpose='formula' AND cr.verdict='approve'
     AND cr.id=(SELECT max(id) FROM finance_financereview WHERE configuration_id=cc.id AND purpose='formula')
     AND cr.id::text=r.snapshot->'reviews'->'D06.statement_contract'->>'id'
     AND (SELECT state FROM policy_policystate WHERE configuration_id=cc.id ORDER BY id DESC LIMIT 1)='active')
   AND jsonb_array_length(r.snapshot->'inputs')>0
   AND ((SELECT count(*) FROM finance_financestatementinput si WHERE si.statement_id=r.id)+(SELECT count(*) FROM finance_financestatementppeinput pi WHERE pi.statement_id=r.id))=jsonb_array_length(r.snapshot->'inputs') AND psl_statement_ppe_current(r.id) AND psl_statement_ppe_document_valid(r.id,b.version_id,b.snapshot) AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) uid WHERE EXISTS(SELECT 1 FROM finance_financestatementppeinput pi WHERE pi.statement_id=r.id) AND NOT psl_ppe_grants(r.case_id,uid::bigint,ARRAY['case.read','finance.read','ppe.read']))
   AND NOT EXISTS(SELECT 1 FROM finance_financestatementinput si
    JOIN finance_financerun sr ON sr.id=si.source_run_id
    JOIN finance_financereview rv ON rv.id=si.source_review_id
    JOIN finance_financesource ss ON ss.id=sr.source_id
    WHERE si.statement_id=r.id AND (sr.case_id<>r.case_id OR rv.run_id<>sr.id OR rv.verdict<>'approve'
     OR rv.id<>(SELECT max(id) FROM finance_financereview WHERE run_id=sr.id AND purpose='output')
     OR sr.result->>'period'<>r.result->>'period' OR sr.result->>'entity'<>r.result->>'entity'
     OR sr.result->>'currency'<>r.result->>'currency' OR ss.accounting_basis IS DISTINCT FROM r.result->>'accounting_basis'
     OR si.declaration->>'source_sign' IS NULL OR si.declaration->>'source_sign' IS DISTINCT FROM si.declaration->>'destination_sign'
     OR sr.result->'company'->si.metric->'value' IS DISTINCT FROM r.result->'company'->si.destination->'value'
     OR sr.result->'company'->si.metric->>'unit' IS DISTINCT FROM si.declaration->>'unit'))
)
 THEN RAISE EXCEPTION 'Current native accounting binding/output review and all exact recipient receipts required'; END IF;

 IF TG_OP='UPDATE' AND NEW.definition IN ('delivery-release/v1','delivery-hypercare/v1')
 AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id THEN
  IF NEW.cancel_requested OR OLD.status IN ('cancelled','followup_needed') OR NEW.status<>'ready'
   OR (OLD.lease_until IS NOT NULL AND OLD.lease_until>statement_timestamp())
   OR NOT EXISTS(SELECT 1 FROM core_evidence n JOIN core_evidence o ON o.id=OLD.source_head_id
     JOIN core_audit a ON a.case_id=n.case_id AND a.actor_id=n.created_by_id
     JOIN core_evidence e ON e.case_id=n.case_id AND a.data->'evidence'=to_jsonb(e.id)
     WHERE n.id=NEW.source_head_id AND n.body=o.body AND n.version>o.version
      AND a.action='factory.delivery_intake_reaffirmed' AND a.data->>'work'=NEW.id::text
      AND a.data->>'previous'=OLD.source_head_id::text AND a.data->>'current'=n.id::text
      AND length(btrim(a.data->>'reason')) BETWEEN 1 AND 2000
      AND coalesce(a.data->>'packet','') ~ '^[a-f0-9]{64}$')
   OR EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity t ON t.id=a.activity_id
     WHERE t.work_id=NEW.id AND t.kind='ACT03' AND a.phase='started' AND a.result->>'schema'='factory-provider-request/v1'
      AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt done WHERE done.activity_id=a.activity_id AND done.number=a.number AND done.phase IN ('observed','failed'))
      AND NOT EXISTS(SELECT 1 FROM workflows_factoryplanningreceipt WHERE attempt_id=a.id))
  THEN RAISE EXCEPTION 'Exact fresh human source instruction and reconciled original effects required'; END IF;
 END IF;

 IF NEW.definition='rfp-response/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_rfpcase r ON r.id=(NEW.request->>'rfp')::bigint AND r.case_id=NEW.case_id
   JOIN pmo_rfpintake i ON i.id=(e.body::jsonb->>'intake')::bigint AND i.rfp_id=r.id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_rfp_intake'
    AND e.body::jsonb->>'schema'='factory-rfp-intake/v1' AND e.body::jsonb->'rfp'=NEW.request->'rfp'
    AND NEW.request-ARRAY['rfp','reference']='{}'::jsonb
    AND e.body::jsonb-ARRAY['schema','rfp','intake','response_evidence','public_terms','sources','matrix','lessons']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'sources')='object' AND jsonb_typeof(e.body::jsonb->'matrix')='array'
    AND a.action='factory.rfp_inputs_recorded' AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact native same-case RFP instruction provenance required'; END IF;
  IF TG_OP='UPDATE' AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id THEN
   IF OLD.status IN ('verified','cancelled','followup_needed') OR NEW.cancel_requested OR NEW.status<>'ready'
    OR (OLD.lease_until IS NOT NULL AND OLD.lease_until>statement_timestamp())
    OR NOT EXISTS(SELECT 1 FROM core_audit a JOIN core_evidence e ON e.id=NEW.source_head_id AND e.created_by_id=a.actor_id
      WHERE a.case_id=NEW.case_id AND a.action='factory.rfp_instruction_changed'
       AND a.data->>'work'=NEW.id::text AND a.data->>'previous'=OLD.source_head_id::text
       AND a.data->>'current'=NEW.source_head_id::text AND length(btrim(a.data->>'reason')) BETWEEN 1 AND 4000)
    OR EXISTS(SELECT 1 FROM documents_publication p JOIN documents_publicationjob j ON j.publication_id=p.id
      WHERE p.factory_work_id=NEW.id AND (j.status IN ('pending','unknown','leased','held') OR
       j.status='confirmed' AND NOT EXISTS(SELECT 1 FROM pmo_rfpsubmission s WHERE s.version_id=p.version_id)))
    OR EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity t ON t.id=a.activity_id
      WHERE t.work_id=NEW.id AND t.kind='ACT03' AND a.phase='started' AND a.result->>'schema'='factory-provider-request/v1'
       AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt done WHERE done.activity_id=a.activity_id AND done.number=a.number AND done.phase IN ('observed','failed'))
       AND NOT EXISTS(SELECT 1 FROM workflows_factoryplanningreceipt pr WHERE pr.attempt_id=a.id))
   THEN RAISE EXCEPTION 'Fresh human RFP instruction and reconciled original effects required'; END IF;
  END IF;

  IF NEW.status='verified' AND NOT EXISTS(
   SELECT 1 FROM pmo_rfpdisposition d JOIN pmo_rfpoutcome o ON o.id=d.outcome_id
   JOIN pmo_rfpsubmission s ON s.id=o.submission_id JOIN pmo_rfpresponse r ON r.id=s.response_id
   JOIN pmo_rfpcase root ON root.id=r.rfp_id JOIN core_evidence h ON h.id=NEW.source_head_id
   JOIN pmo_commercialrevision cr ON cr.id=r.commercial_id
   JOIN pmo_rfpdocumentbinding b ON b.response_id=r.id AND b.version_id=s.version_id
   JOIN documents_version v ON v.id=s.version_id JOIN documents_document doc ON doc.id=v.document_id
   JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
   JOIN documents_controlledreview review ON review.id=p.review_id AND review.version_id=v.id
   JOIN workflows_factoryactivity t ON t.work_id=NEW.id AND t.kind='ACT13'
   JOIN workflows_factoryattempt a ON a.activity_id=t.id AND a.phase='observed'
   WHERE root.case_id=NEW.case_id AND root.id=(NEW.request->>'rfp')::bigint AND d.rfp_id=root.id
    AND doc.case_id=NEW.case_id AND s.snapshot=b.snapshot AND s.snapshot->>'response'=r.id::text
    AND s.snapshot->'sources'=r.snapshot AND d.snapshot->'sources'=r.snapshot AND d.snapshot->'commercial_sources'=cr.sources
    AND jsonb_array_length(s.snapshot->'reviews')=2 AND NOT EXISTS(
     SELECT 1 FROM jsonb_array_elements_text(s.snapshot->'reviews') WITH ORDINALITY item(id,nth)
     WHERE NOT EXISTS(SELECT 1 FROM pmo_rfpreview rr WHERE rr.id=item.id::bigint AND rr.response_id=r.id AND rr.verdict='approve'
      AND rr.role=CASE item.nth WHEN 1 THEN 'PMO Lead' WHEN 2 THEN 'Engineering Lead' END AND rr.created_at<=p.created_at))
    AND jsonb_array_length(s.snapshot->'costing_decisions')=3 AND NOT EXISTS(
     SELECT 1 FROM jsonb_array_elements_text(s.snapshot->'costing_decisions') WITH ORDINALITY item(id,nth)
     WHERE NOT EXISTS(SELECT 1 FROM pmo_commercialdecision cd WHERE cd.id=item.id::bigint AND cd.revision_id=cr.id AND cd.verdict='approve'
      AND cd.role=CASE item.nth WHEN 1 THEN 'PM' WHEN 2 THEN 'Head of PMO' WHEN 3 THEN 'CEO' END AND cd.created_at<=p.created_at))
    AND review.verdict='approve' AND review.payload_sha256=v.payload_sha256 AND review.created_at<=p.created_at
    AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
    AND (p.factory_work_id=NEW.id OR p.factory_work_id IS NULL)
    AND (p.factory_work_id IS NULL OR EXISTS(SELECT 1 FROM core_evidence origin WHERE origin.id=p.factory_source_id
     AND origin.case_id=NEW.case_id AND origin.kind='agent_private_rfp_intake' AND origin.body::jsonb->'rfp'=NEW.request->'rfp'))
    AND d.snapshot->>'response'=r.id::text AND d.snapshot->>'submission'=s.id::text AND d.snapshot->>'outcome'=o.id::text
    AND d.snapshot->>'case'=NEW.case_id::text AND d.snapshot->'baseline_imported'='false'::jsonb
    AND (d.kind='route_a' AND o.result='won' AND d.snapshot->>'route'='A' OR
     d.kind='loss_archive' AND o.result='lost' AND d.lessons_id=(h.body::jsonb->>'lessons')::bigint)
    AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
     SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256))
    AND s.receipt_ids=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
    AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
    AND a.result->'verified'='true'::jsonb AND a.result->>'head'=NEW.source_head_id::text
    AND a.result->>'response'=r.id::text AND a.result->>'disposition'=d.id::text AND a.result->>'submission'=s.id::text
    AND a.result->>'outcome'=o.id::text AND a.result->>'document_version'=v.id::text
    AND a.result->>'publication'=p.id::text AND a.result->'receipt_ids'=s.receipt_ids)
  THEN RAISE EXCEPTION 'Historical approved RFP submission, actual customer outcome and all exact receipts required'; END IF;

 END IF;

 IF NEW.definition='pmo-change/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN pmo_changeauthorization ca ON ca.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint
  JOIN pmo_changeversion cv ON cv.id=ca.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
  JOIN pmo_changeclosure cc ON cc.authorization_id=ca.id
  JOIN documents_publicationreceipt r ON r.id=cc.receipt_id JOIN documents_publication p ON p.id=r.publication_id
  JOIN pmo_changedocumentbinding b ON b.version_id=p.version_id AND b.authorization_id=ca.id AND b.purpose='go_live'
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND cv.id=(e.body::jsonb->>'change_version_id')::bigint
   AND cr.case_id=NEW.case_id AND cr.current_id=cv.id AND cr.id=(NEW.request->>'change')::bigint
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id
   AND cc.execution_ids=b.execution_ids AND cc.pm_signature_id<>cc.client_signature_id
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'closure'=cc.id::text
   AND a.result->>'document_version'=p.version_id::text
   AND EXISTS(SELECT 1 FROM documents_publication np JOIN pmo_changedocumentbinding nb ON nb.version_id=np.version_id
    JOIN documents_publicationreceipt nr ON nr.publication_id=np.id
    WHERE np.factory_work_id=NEW.id AND np.factory_source_id=e.id AND nb.authorization_id=ca.id AND nb.purpose='notice')
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient
    WHERE NOT EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint)))
 THEN RAISE EXCEPTION 'Observed exact native change closure and controlled recipient receipts required'; END IF;

 IF NEW.definition='pmo-emergency/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN pmo_emergencyprofile ep ON ep.id=(e.body::jsonb->>'profile_id')::bigint
  JOIN pmo_emergencyoutcome o ON o.id=(e.body::jsonb->'inputs'->>'outcome_id')::bigint AND o.profile_id=ep.id
  JOIN pmo_emergencyauthorization ea ON ea.id=o.authorization_id AND ea.profile_id=ep.id
  JOIN pmo_emergencyretrospectiverecord rr ON rr.outcome_id=o.id
  JOIN pmo_changeversion cv ON cv.id=ep.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
  JOIN pmo_emergencydocumentbinding b ON b.outcome_id=o.id
  JOIN documents_version v ON v.id=b.version_id JOIN documents_publication p ON p.version_id=v.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND cr.case_id=NEW.case_id AND cr.id=(NEW.request->>'change')::bigint AND cr.current_id=cv.id
   AND ea.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint AND ea.created_at<=o.implemented_at
   AND rr.snapshot->>'authorization_id'=ea.id::text AND rr.snapshot->>'status' IN ('evidenced_on_time','completed_with_lateness_exception')
   AND b.manifest->>'reconciliation_id'=rr.id::text AND b.manifest->>'outcome_id'=o.id::text
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id AND v.template_id=(e.body::jsonb->'inputs'->>'template_id')::bigint
   AND v.audience=e.body::jsonb->'inputs'->>'audience'
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'retrospective_record'=rr.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'retrospective_status'=rr.snapshot->>'status'
   AND EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient
    WHERE NOT EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint)))
 THEN RAISE EXCEPTION 'Observed exact native Emergency retrospective and every report receipt required; deployment and ordinary closure are not granted'; END IF;

 IF NEW.definition='finance-payroll/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN finance_payrollrequest q ON q.id=(e.body::jsonb->>'request_id')::bigint
   JOIN finance_payrollrun ar ON ar.request_id=q.id AND ar.kind='aggregate'
   JOIN finance_payrollrun mr ON mr.id=ar.parent_id AND mr.kind='match'
   JOIN finance_payrollrun cr ON cr.id=mr.parent_id AND cr.kind='combine'
   JOIN finance_payrollpublication p ON p.run_id=ar.id AND p.request_id=q.id
   JOIN finance_payrollreview rv ON rv.id=p.review_id AND rv.run_id=ar.id
   JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
   JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
   JOIN policy_configuration pc ON pc.id=(p.policy_ids->>'F18.reporting_rules')::bigint
   JOIN policy_registeredreference pr ON pr.case_id=pc.case_id AND pr.ref=pc.envelope->'value'->>'artifact_ref'
    AND pr.version=(pc.envelope->'value'->>'artifact_version')::integer AND pr.sha256=pc.envelope->'value'->>'sha256'
  WHERE e.id=NEW.source_head_id AND q.case_id=NEW.case_id AND q.reference=NEW.request->>'payroll_reference'
   AND cr.request_id=q.id AND mr.request_id=q.id
   AND (cr.metadata->'input_ids') @> (e.body::jsonb->'inputs'->'input_ids')
   AND (cr.metadata->'input_ids') <@ (e.body::jsonb->'inputs'->'input_ids')
   AND mr.hr_snapshot_id=(e.body::jsonb->'inputs'->>'hr_snapshot_id')::bigint
   AND ar.metadata->>'status'='complete' AND mr.metadata->>'status'='complete' AND cr.metadata->>'status'='complete'
   AND rv.verdict='approve' AND rv.subject_sha256=ar.sha256
   AND rv.id=(SELECT max(id) FROM finance_payrollreview WHERE run_id=ar.id)
   AND p.payload->'by_bu'=ar.result->'by_bu' AND p.payload->'eligible_total'=ar.result->'eligible_total'
   AND p.payload->>'source_run'=ar.id::text AND p.payload->>'disclosure'='aggregate_only'
   AND NOT (p.payload ? 'rows') AND p.payload->'hr_written'='false'::jsonb AND p.payload->'ledger_posted'='false'::jsonb
   AND NOT EXISTS(SELECT 1 FROM finance_payrollpublication newer WHERE newer.request_id=q.id AND newer.version>p.version)
   AND NOT EXISTS(SELECT 1 FROM finance_payrollrequest newer WHERE newer.case_id=q.case_id AND newer.reference=q.reference AND newer.version>q.version)
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'publication'=p.id::text
   AND a.result->>'run'=ar.id::text AND a.result->>'request'=q.id::text
   AND jsonb_array_length(pr.content->'recipient_ids')>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(pr.content->'recipient_ids') recipient
     WHERE NOT EXISTS(SELECT 1 FROM finance_payrollreportreceipt rr WHERE rr.publication_id=p.id AND rr.actor_id=recipient::bigint
       AND a.result->'receipt_ids' @> to_jsonb(ARRAY[rr.id]))))
 THEN RAISE EXCEPTION 'Observed exact payroll aggregate and actual recipient-owned receipts required'; END IF;

 IF NEW.definition='finance-forecast/v1' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
  JOIN finance_forecastscenario s ON s.id=(e.body::jsonb->>'scenario_id')::bigint
  WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND s.case_id=NEW.case_id
   AND e.kind='agent_private_forecast_intake' AND e.body::jsonb->>'protocol'='factory-forecast-selection/v1'
   AND s.reference=NEW.request->>'scenario_reference'
   AND e.body::jsonb-ARRAY['protocol','scenario_id','as_of','months','source_ids','template_id','audience']='{}'::jsonb
   AND e.body::jsonb->>'audience' IN ('internal','management','group')
   AND jsonb_typeof(e.body::jsonb->'source_ids')='array'
   AND jsonb_array_length(e.body::jsonb->'source_ids')=(SELECT count(*) FROM (
    SELECT s.evidence_id AS id UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'openings') item
    UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'items') item) exact_sources)
   AND NOT EXISTS(SELECT id FROM (
    SELECT s.evidence_id AS id UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'openings') item
    UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'items') item) exact_sources
    WHERE NOT e.body::jsonb->'source_ids' @> jsonb_build_array(id))
   AND (e.body::jsonb->'template_id'='null'::jsonb OR EXISTS(SELECT 1 FROM documents_template t
    WHERE t.id=(e.body::jsonb->>'template_id')::bigint AND t.case_id=NEW.case_id AND t.definition->>'document_type'=CASE WHEN e.body::jsonb->>'audience'='group' THEN 'finance_group_report' ELSE 'finance_report' END))
   AND e.body::jsonb->>'as_of'=s.payload->>'as_of' AND e.body::jsonb->'months'=s.payload->'months'
   AND a.action IN ('factory.forecast_intake','factory.forecast_source')
   AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
   AND NEW.invoice_id IS NULL AND NEW.preparation_id IS NULL)
 THEN RAISE EXCEPTION 'Exact native forecast intake provenance required'; END IF;
 IF NEW.definition='finance-forecast/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN finance_forecastscenario s ON s.id=(e.body::jsonb->>'scenario_id')::bigint
  JOIN finance_forecastrun r ON r.scenario_id=s.id JOIN finance_forecastreview rv ON rv.run_id=r.id
  JOIN finance_forecastbinding b ON b.run_id=r.id JOIN documents_version v ON v.id=b.version_id
  JOIN documents_publication p ON p.version_id=v.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND r.case_id=NEW.case_id AND s.case_id=NEW.case_id
   AND rv.verdict='approve' AND rv.id=(SELECT max(id) FROM finance_forecastreview WHERE run_id=r.id)
   AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario newer WHERE newer.case_id=s.case_id AND newer.reference=s.reference AND newer.number>s.number)
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id AND p.factory_policy_id=NEW.policy_id
   AND v.template_id=(e.body::jsonb->>'template_id')::bigint AND v.audience=e.body::jsonb->>'audience'
   AND b.snapshot->>'run_hash'=r.sha256 AND b.snapshot->>'output_review'=rv.id::text
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text
   AND a.result->>'forecast_run'=r.id::text AND a.result->>'forecast_review'=rv.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'publication'=p.id::text
   AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint
     AND pr.payload_sha256=v.payload_sha256 AND pr.payload=v.payload)))
 THEN RAISE EXCEPTION 'Observed exact native forecast approval and aggregate receipts required'; END IF;

 IF NEW.definition='finance-ppe/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e
  JOIN finance_schedulework r ON r.id=(e.body::jsonb->>'register_id')::bigint
  JOIN finance_schedulework s ON s.case_id=NEW.case_id AND s.kind='ppe_schedule'
  JOIN finance_schedulereview sr ON sr.work_id=s.id AND sr.authority->>'purpose'='schedule'
  JOIN finance_schedulereview rr ON rr.work_id=r.id AND rr.authority->>'purpose'='register'
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND s.payload->>'register_id'=r.id::text
   AND s.payload->'prior_id'=e.body::jsonb->'prior_id'
   AND s.parent_id IS NOT DISTINCT FROM (e.body::jsonb->>'ledger_id')::bigint
   AND s.reference=NEW.request->>'reference' AND s.result->>'status'='ready'
   AND psl_ppe_schedule_current(s.id) AND psl_ppe_review_current(sr.id)
   AND psl_ppe_policy_current(NEW.case_id,NEW.policy_id)
   AND psl_ppe_grants(NEW.case_id,e.created_by_id,ARRAY['case.read','finance.read','ppe.read','evidence.add'])
   AND EXISTS(SELECT 1 FROM core_audit intake WHERE intake.case_id=NEW.case_id AND intake.actor_id=e.created_by_id
    AND intake.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((intake.action='factory.ppe_intake' AND psl_ppe_grants(NEW.case_id,e.created_by_id,ARRAY['factory.start']))
     OR (intake.action='factory.ppe_source' AND psl_ppe_grants(NEW.case_id,e.created_by_id,ARRAY['factory.manage']))))
   AND sr.verdict='approve' AND rr.verdict='approve' AND sr.snapshot=s.snapshot AND rr.snapshot=r.snapshot
   AND sr.id=(SELECT max(id) FROM finance_schedulereview WHERE work_id=s.id AND authority->>'purpose'='schedule')
   AND rr.id=(SELECT max(id) FROM finance_schedulereview WHERE work_id=r.id AND authority->>'purpose'='register')
   AND NOT EXISTS(SELECT 1 FROM finance_schedulework newer WHERE newer.case_id=NEW.case_id AND
     ((newer.kind=r.kind AND newer.reference=r.reference AND newer.version>r.version) OR
      (newer.kind=s.kind AND newer.reference=s.reference AND newer.version>s.version)))
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text
   AND a.result->>'schedule'=s.id::text AND a.result->>'schedule_sha256'=s.sha256
   AND a.result->>'schedule_review'=sr.id::text AND a.result->>'register_review'=rr.id::text
   AND a.result->'ledger'=COALESCE(to_jsonb(s.parent_id),'null'::jsonb)
   AND a.result->'ledger_posted'='false'::jsonb
   AND a.result->>'full_owner_oracle_acceptance'='unresolved'
   AND (s.parent_id IS NULL OR EXISTS(SELECT 1 FROM finance_financerun note
     JOIN finance_financereview source_review ON source_review.source_id=note.source_id AND source_review.purpose='source'
     WHERE note.id=s.parent_id AND note.case_id=NEW.case_id AND note.kind='mapping'
      AND source_review.verdict='approve'
      AND source_review.id=(SELECT max(id) FROM finance_financereview WHERE source_id=note.source_id AND purpose='source')
      AND note.snapshot->'source_review'->>'id'=source_review.id::text
      AND a.result->'ledger_reviews'=jsonb_build_object('source',note.snapshot->'source_review','rules',note.snapshot->'reviews')))
   AND s.snapshot->>'register_review'=rr.id::text
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(s.snapshot->'policies') pin
     WHERE pin.value->>'status'<>'ACTIVE' OR NOT EXISTS(SELECT 1 FROM policy_configuration pc
      WHERE pc.id=(pin.value->>'id')::bigint AND pc.case_id=NEW.case_id AND pc.component=pin.key
       AND (SELECT state FROM policy_policystate WHERE configuration_id=pc.id ORDER BY id DESC LIMIT 1)='active'))
   AND NOT EXISTS(SELECT 1 FROM (VALUES(sr.actor_id),(rr.actor_id)) reviewer(id)
     WHERE NOT EXISTS(SELECT 1 FROM auth_user u JOIN identity_grant g ON g.user_id=u.id
      WHERE u.id=reviewer.id AND u.is_active AND g.case_id=NEW.case_id AND g.action='ppe.review' AND g.active)))
 THEN RAISE EXCEPTION 'Observed exact current human-reviewed PPE schedule and accounting note required'; END IF;

 IF NEW.definition='finance-schedules/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN core_evidence supplied ON supplied.id=(e.body::jsonb->>'evidence_id')::bigint
  JOIN finance_schedulework s ON s.evidence_id=supplied.id AND s.case_id=NEW.case_id AND s.kind=NEW.request->>'kind' AND s.reference=NEW.request->>'reference'
  JOIN finance_schedulereview r ON r.work_id=s.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND s.parent_id IS NOT DISTINCT FROM (e.body::jsonb->>'parent_id')::bigint
   AND s.payload=CASE WHEN s.kind='income' THEN e.body::jsonb->'payload' ELSE supplied.body::jsonb END
   AND s.result->>'status'='ready' AND psl_schedules_review_current(r.id)
   AND psl_schedules_policy_current(NEW.case_id,NEW.policy_id)
   AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['case.read','finance.read','schedules.read','evidence.add'])
   AND EXISTS(SELECT 1 FROM core_audit intake WHERE intake.case_id=NEW.case_id AND intake.actor_id=e.created_by_id
    AND intake.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((intake.action='factory.schedules_intake' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.start']))
     OR (intake.action='factory.schedules_source' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.manage']))))
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text
   AND a.result->>'schedule'=s.id::text AND a.result->>'schedule_sha256'=s.sha256
   AND a.result->>'schedule_review'=r.id::text AND a.result->>'source_evidence'=supplied.id::text
   AND a.result->'parent'=COALESCE(to_jsonb(s.parent_id),'null'::jsonb)
   AND a.result->'ledger_posted'='false'::jsonb AND a.result->'native_workbook_verified'='false'::jsonb)
 THEN RAISE EXCEPTION 'Observed exact current human-reviewed selected schedule required'; END IF;

 IF TG_OP='UPDATE' AND NEW.definition='finance-forecast/v1' AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id
 AND ((SELECT body::jsonb->>'audience'='group' FROM core_evidence WHERE id=NEW.source_head_id)
 IS DISTINCT FROM (SELECT body::jsonb->>'audience'='group' FROM core_evidence WHERE id=OLD.source_head_id))
 THEN RAISE EXCEPTION 'Separate group audience work identity is immutable'; END IF;

 IF NEW.definition='pmo-weekly-report/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p JOIN documents_version v ON v.id=p.version_id
  JOIN documents_controlledreview rv ON rv.id=p.review_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND p.factory_policy_id=NEW.policy_id
   AND psl_reporting_document(NEW.id,NEW.source_head_id,v.id)
   AND rv.version_id=v.id AND rv.verdict='approve' AND rv.payload_sha256=v.payload_sha256
   AND rv.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
   AND psl_reporting_review(NEW.case_id,rv.id)
   AND psl_reporting_principals(NEW.id,v.id,p.actor_id)
   AND psl_reporting_distribution(NEW.case_id,v.id,p.policies,p.recipient_ids,p.retention_days)
   AND psl_reporting_grants(NEW.case_id,p.actor_id,ARRAY['case.read','report.read','factory.execute','document.publish'])
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=NEW.source_head_id::text AND a.result->>'document_version'=v.id::text
   AND a.result->>'publication'=p.id::text AND a.result->'complete_project_coverage'='false'::jsonb AND a.result->'external_delivery_verified'='false'::jsonb AND a.result->'business_approval_granted'='false'::jsonb
   AND jsonb_array_length(p.recipient_ids)>0
   AND (SELECT count(*) FROM documents_publicationreceipt WHERE publication_id=p.id)=jsonb_array_length(p.recipient_ids)
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint
     AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256 AND psl_reporting_grants(NEW.case_id,pr.recipient_id,ARRAY['document.receive:client']))))
 THEN RAISE EXCEPTION 'Observed exact current weekly client report, native PMO Lead review and every recipient receipt required'; END IF;

 IF NEW.definition='pmo-escalation/v1' AND NEW.status='verified' AND NOT EXISTS(
 SELECT 1 FROM documents_publication p JOIN documents_version v ON v.id=p.version_id JOIN documents_publicationjob j ON j.publication_id=p.id
 JOIN pmo_escalationdocumentbinding b ON b.version_id=v.id JOIN pmo_escalationrequest r ON r.id=b.request_id JOIN pmo_escalationprofile ep ON ep.id=r.profile_id
 JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13' JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
 WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND p.factory_policy_id=NEW.policy_id AND j.status='confirmed'
 AND psl_escalation_document(NEW.id,v.id,p.review_id,p.actor_id,p.factory_policy_id,p.factory_source_id,p.recipient_ids,p.policies)
 AND a.result->'verified'='true'::jsonb AND a.result->'issue_resolution_verified'='false'::jsonb AND a.result->>'head'=NEW.source_head_id::text
 AND a.result->>'verification_scope'='reviewed_escalation_communication' AND a.result->>'request'=r.id::text AND a.result->>'profile'=ep.id::text AND a.result->>'issue_state'=ep.state_id::text
 AND a.result->'decision'=COALESCE(to_jsonb(b.decision_id),'null'::jsonb) AND a.result->>'direction'=r.direction AND a.result->>'target'=r.target
 AND a.result->>'document_version'=v.id::text AND a.result->>'publication'=p.id::text
 AND a.result->'receipt_ids'=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
 AND (SELECT count(*) FROM documents_publicationreceipt WHERE publication_id=p.id)=jsonb_array_length(p.recipient_ids)
 AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256)))
 THEN RAISE EXCEPTION 'Observed exact current communication and every receipt required; issue resolution is not verified'; END IF;

 IF NEW.definition='pmo-minutes/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN core_evidence note ON note.id=(e.body::jsonb->>'evidence_id')::bigint AND note.case_id=e.case_id
   JOIN documents_template t ON t.id=(e.body::jsonb->>'template_id')::bigint AND t.case_id=e.case_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_minutes_intake'
    AND e.body::jsonb->>'protocol'='factory-minutes-intake/v1' AND note.kind='meeting_notes'
    AND t.definition->>'document_type'='minutes' AND t.definition->'audience_fields' ? (e.body::jsonb->>'audience')
    AND (e.body::jsonb->>'audience'='internal' AND e.body::jsonb->'publish'='false'::jsonb OR e.body::jsonb->>'audience'='client' AND e.body::jsonb->'publish'='true'::jsonb)
    AND e.body::jsonb - ARRAY['protocol','meeting_version_id','evidence_id','template_id','audience','publish']='{}'::jsonb
    AND a.action IN ('factory.minutes_intake','factory.minutes_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND encode(sha256(convert_to(e.body,'UTF8')),'hex')=e.sha256)
   THEN RAISE EXCEPTION 'Exact authorized typed formal-minutes intake required'; END IF;
  IF NEW.status='verified' AND NOT EXISTS(
   SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
   WHERE fa.work_id=NEW.id AND fa.kind='ACT13' AND a.phase='observed'
    AND a.result->'verified'='true'::jsonb AND a.result->>'head'=NEW.source_head_id::text
    AND a.result->'actions_completed'='false'::jsonb AND a.result->'scope_changed'='false'::jsonb
    AND psl_minutes_current(NEW.id,NEW.source_head_id,(a.result->>'document_version')::bigint)
    AND psl_schedules_policy_current(NEW.case_id,NEW.policy_id)
    AND a.result->'manifest'=(SELECT manifest FROM pmo_minutesreportbinding WHERE version_id=(a.result->>'document_version')::bigint)
    AND ((SELECT body::jsonb->'publish' FROM core_evidence WHERE id=NEW.source_head_id)='false'::jsonb OR EXISTS(
     SELECT 1 FROM documents_publication p JOIN documents_controlledreview r ON r.id=p.review_id JOIN documents_version v ON v.id=p.version_id
     WHERE p.id=(a.result->>'publication')::bigint AND p.version_id=(a.result->>'document_version')::bigint
      AND p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND p.factory_policy_id=NEW.policy_id
      AND r.version_id=v.id AND r.verdict='approve' AND r.payload_sha256=v.payload_sha256
      AND r.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
      AND psl_schedules_authority_current(NEW.case_id,r.authority)
      AND psl_schedules_grants(NEW.case_id,r.actor_id,ARRAY['document.review_controlled'])
      AND psl_schedules_authority_current(NEW.case_id,p.policies)
      AND p.actor_id=(psl_schedules_values(NEW.policy_id)->0->>'executor_id')::bigint
      AND psl_schedules_grants(NEW.case_id,p.actor_id,ARRAY['case.read','meeting.read','factory.execute','document.publish'])
      AND p.recipient_ids=(SELECT jsonb_agg(DISTINCT (recipient->>'user_id')::bigint ORDER BY (recipient->>'user_id')::bigint)
       FROM jsonb_array_elements(psl_schedules_values((p.policies->>'D11.recipient_grant_refs')::bigint)) recipient WHERE recipient->>'audience'=v.audience)
      AND p.retention_days=(psl_schedules_values((p.policies->>'D11.template_storage_retention_rules')::bigint)->0->>'retention_days')::integer
      AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT psl_schedules_grants(NEW.case_id,recipient::bigint,ARRAY['document.receive:'||v.audience]))
      AND jsonb_array_length(p.recipient_ids)>0
      AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(
       SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint
        AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256)))))
   THEN RAISE EXCEPTION 'Observed current human-confirmed minutes and exact requested recipient receipts required'; END IF;
 END IF;

 IF NEW.definition='finance-bu/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN finance_buwork w ON w.case_id=NEW.case_id AND w.kind=NEW.request->>'mode'
  JOIN finance_bureport p ON p.work_id=w.id JOIN finance_bureview rv ON rv.id=p.review_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  JOIN policy_configuration pc ON pc.id=(p.policy_ids->>'BU.disclosure_rules')::bigint
  WHERE e.id=NEW.source_head_id AND w.reference='factory-bu-'||NEW.id::text
   AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['case.read','bu.read','bu.private.read','evidence.add'])
   AND EXISTS(SELECT 1 FROM core_audit origin WHERE origin.case_id=NEW.case_id AND origin.actor_id=e.created_by_id
    AND origin.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((origin.action='factory.bu_intake' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.start']))
     OR (origin.action='factory.bu_source' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.manage']))))
   AND w.metadata->>'status'='complete' AND w.payload->'conserved'='true'::jsonb
   AND psl_bu_current(w.id) AND psl_bu_review(rv.id) AND psl_bu_private(w.id,p.actor_id) AND psl_bu_authority(w.id,p.actor_id,'publish',p.policy_ids)
   AND (COALESCE(w.metadata->'historical','false'::jsonb)='false'::jsonb OR EXISTS(SELECT 1 FROM finance_bureview history WHERE history.work_id=w.id AND history.purpose='historical' AND psl_bu_review(history.id)))
   AND rv.work_id=w.id AND rv.purpose=w.kind AND rv.verdict='approve' AND rv.subject_sha256=w.sha256
   AND rv.id=(SELECT max(id) FROM finance_bureview WHERE work_id=w.id AND purpose=w.kind)
   AND NOT EXISTS(SELECT 1 FROM finance_buwork newer WHERE newer.case_id=w.case_id AND newer.kind=w.kind AND newer.reference=w.reference AND newer.version>w.version AND newer.metadata->'accepted'='true'::jsonb)
   AND NOT EXISTS(SELECT 1 FROM finance_bureport newer JOIN finance_buwork nw ON nw.id=newer.work_id WHERE nw.case_id=w.case_id AND nw.kind=w.kind AND nw.metadata->'scope'=w.metadata->'scope' AND newer.id>p.id)
   AND ((w.kind='staff' AND w.payroll_id=(e.body::jsonb->'inputs'->>'payroll_id')::bigint AND w.metadata->'rule_ids'=e.body::jsonb->'inputs'->'rule_ids')
    OR (w.kind='event' AND w.parent_id=(e.body::jsonb->'inputs'->>'source_id')::bigint AND w.metadata->'comparison'=e.body::jsonb->'inputs'->'comparison'))
   AND psl_schedules_policy_current(NEW.case_id,pc.id)
   AND psl_schedules_grants(NEW.case_id,p.actor_id,ARRAY['case.read','bu.read','bu.private.read','bu.publish'])
   AND psl_schedules_grants(NEW.case_id,rv.actor_id,ARRAY['case.read','bu.read','bu.private.read','bu.review'])
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(w.metadata->'policy_ids') pin WHERE NOT psl_schedules_policy_current(NEW.case_id,(pin.value#>>'{}')::bigint))
   AND p.payload-ARRAY['entity','period','currency','unit','by_bu','company_source_total','allocated_total','company_only','residual','conserved','source_work','coverage','native_authenticity_verified','destination','ledger_posted','source_written','disclosure']='{}'::jsonb
   AND p.payload->>'disclosure'='aggregate_only' AND NOT (p.payload ? 'rows') AND p.payload->'ledger_posted'='false'::jsonb AND p.payload->'source_written'='false'::jsonb
   AND p.payload->>'source_work'=w.id::text AND p.payload->'by_bu'=w.payload->'by_bu'
   AND p.payload->'company_source_total'=w.payload->'source_total' AND p.payload->'allocated_total'=w.payload->'allocated_total' AND p.payload->'residual'=w.payload->'residual'
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'work'=w.id::text AND a.result->>'publication'=p.id::text
   AND a.result->'private_payloads_in_result'='false'::jsonb AND a.result->'source_written'='false'::jsonb AND a.result->'ledger_posted'='false'::jsonb
   AND jsonb_array_length(psl_schedules_values(pc.id)->0->'recipient_ids')>0
   AND (SELECT count(*) FROM finance_bureceipt WHERE report_id=p.id)=jsonb_array_length(psl_schedules_values(pc.id)->0->'recipient_ids')
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(psl_schedules_values(pc.id)->0->'recipient_ids') recipient WHERE NOT EXISTS(
    SELECT 1 FROM finance_bureceipt rr WHERE rr.report_id=p.id AND rr.actor_id=recipient::bigint
     AND a.result->'receipt_ids' @> to_jsonb(ARRAY[rr.id])
     AND psl_schedules_grants(NEW.case_id,rr.actor_id,ARRAY['case.read','bu.read','bu.report.read','bu.receive']))))
 THEN RAISE EXCEPTION 'Observed exact reviewed BU aggregate and actual recipient-owned receipts required'; END IF;
 RETURN NEW;
END $$;"""

TASK = r"""CREATE OR REPLACE FUNCTION psl_factory_task_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='UPDATE' AND (NEW.kind,NEW.context,NEW.factory_key) IS DISTINCT FROM (OLD.kind,OLD.context,OLD.factory_key)
 THEN RAISE EXCEPTION 'Human task packet and source identity are immutable'; END IF;
 IF NEW.kind='document_review' AND NEW.version_id IS NULL THEN RAISE EXCEPTION 'Document review version required'; END IF;
 IF NEW.kind<>'document_review' AND (NEW.version_id IS NOT NULL OR NEW.factory_key IS NULL OR NEW.kind NOT IN ('issue_followup','factory_information','factory_review','factory_governance','factory_accounting_review'))
 THEN RAISE EXCEPTION 'Closed factory task contract required'; END IF;
 RETURN NEW;
END $$;
"""

GUARDS = r"""
CREATE OR REPLACE FUNCTION psl_issue_factory_source(w workflows_factorywork) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
 JOIN pmo_issuestate s ON s.id=(e.body::jsonb->>'state_id')::bigint JOIN pmo_issue i ON i.id=s.issue_id
 WHERE e.id=w.source_head_id AND e.case_id=w.case_id AND e.kind='agent_private_issue_intake' AND e.source='psl:factory-issue-intake/v1'
 AND encode(sha256(convert_to(e.body,'UTF8')),'hex')=e.sha256
 AND e.body::jsonb->>'protocol'='factory-issue-intake/v1'
 AND e.body::jsonb-ARRAY['protocol','issue_id','state_id','reference_revision_id']='{}'::jsonb
 AND e.body::jsonb ?& ARRAY['protocol','issue_id','state_id','reference_revision_id']
 AND i.id::text=e.body::jsonb->>'issue_id' AND i.id::text=w.request->>'issue_id' AND i.case_id=w.case_id
 AND (e.body::jsonb->'reference_revision_id'='null'::jsonb OR EXISTS(SELECT 1 FROM pmo_issuereferencerevision r WHERE r.id::text=e.body::jsonb->>'reference_revision_id' AND r.issue_id=i.id))
 AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
 AND a.action IN ('factory.issue_intake','factory.issue_source','factory.issue_owner_source'));
$$;
CREATE OR REPLACE FUNCTION psl_issue_factory_current(w workflows_factorywork,r jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT psl_issue_factory_source(w) AND EXISTS(
 SELECT 1 FROM core_evidence e JOIN pmo_issue i ON i.id::text=w.request->>'issue_id'
 JOIN pmo_issuestate s ON s.id=i.current_id
 JOIN workflows_taskevent reply ON reply.id::text=r->>'owner_response'
 JOIN workflows_humantask t ON t.id=reply.task_id
 WHERE e.id=w.source_head_id AND e.body::jsonb->>'state_id'=s.id::text
 AND e.body::jsonb->'reference_revision_id'=COALESCE((SELECT to_jsonb(id) FROM pmo_issuereferencerevision WHERE issue_id=i.id ORDER BY number DESC LIMIT 1),'null'::jsonb)
 AND t.case_id=w.case_id AND t.kind='issue_followup' AND t.status='completed' AND t.context->>'work'=w.id::text
 AND reply.action='issue.owner_response' AND reply.data->>'head'=e.id::text AND reply.data->>'state_id'=s.id::text AND reply.actor_id=s.owner_id AND s.actor_id=reply.actor_id
 AND psl_schedules_grants(w.case_id,reply.actor_id,ARRAY['case.read','issue.read','issue.own','issue.work'])
 AND psl_schedules_grants(w.case_id,COALESCE((SELECT principal_id FROM workflows_factoryexecutionbinding WHERE id=w.execution_binding_id),w.actor_id),ARRAY['case.read','issue.read','factory.execute','agent.issues'])
 AND EXISTS(SELECT 1 FROM core_audit a WHERE a.case_id=w.case_id AND a.actor_id=e.created_by_id AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
 AND psl_schedules_grants(w.case_id,e.created_by_id,ARRAY['case.read','issue.read','evidence.add',CASE a.action WHEN 'factory.issue_intake' THEN 'factory.start' WHEN 'factory.issue_source' THEN 'factory.manage' ELSE 'issue.work' END]))
 AND psl_engagement_public_source(w.case_id,s.evidence_id)
 AND (s.fix_id IS NULL OR psl_engagement_public_source(w.case_id,s.fix_id)) AND (s.root_cause_id IS NULL OR psl_engagement_public_source(w.case_id,s.root_cause_id))
 AND r->'verified'='true'::jsonb AND r->>'verification_scope'='issue_investigation_and_owner_followup'
 AND r->>'head'=e.id::text AND r->>'state_id'=s.id::text AND r->>'issue_id'=i.id::text
 AND r->'issue_resolution_verified'='false'::jsonb AND r->'external_lifecycle_changed'='false'::jsonb
 AND EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity act ON act.id=a.activity_id WHERE a.id::text=r->>'investigation_attempt' AND act.work_id=w.id AND act.kind='ACT04' AND a.phase='observed' AND a.result->>'head'=e.id::text AND a.result->'investigation'->>'state_id'=s.id::text)
 AND NOT EXISTS(SELECT 1 FROM pmo_issuereferencerevision rr,LATERAL jsonb_array_elements(rr.references) link
  WHERE rr.id::text=e.body::jsonb->>'reference_revision_id' AND (
    NOT psl_engagement_public_source(w.case_id,(link->>'evidence_id')::bigint)
    OR NOT psl_schedules_grants(w.case_id,rr.actor_id,ARRAY['issue.manage'])
    OR (link->>'observation_id' IS NOT NULL AND NOT EXISTS(
      SELECT 1 FROM pmo_issuereferenceobservation obs JOIN pmo_issuereferencecontract c ON c.id=obs.contract_id JOIN core_evidence se ON se.id=obs.evidence_id
      WHERE obs.id::text=link->>'observation_id' AND obs.issue_id=i.id AND obs.source_ref=link->>'source_ref' AND c.kind=link->>'kind' AND obs.source_sha256=se.sha256
      AND psl_schedules_grants(w.case_id,COALESCE((SELECT principal_id FROM workflows_factoryexecutionbinding WHERE id=w.execution_binding_id),w.actor_id),ARRAY['issue.reference.'||c.kind||'.read'])
      AND psl_schedules_grants(w.case_id,c.actor_id,ARRAY['issue.reference.configure','evidence.add'])
      AND psl_schedules_grants(w.case_id,obs.actor_id,ARRAY['issue.reference.observe'])
      AND psl_schedules_grants(w.case_id,se.created_by_id,ARRAY['evidence.add'])
      AND NOT EXISTS(SELECT 1 FROM pmo_issuereferenceobservation newer WHERE newer.issue_id=i.id AND newer.contract_id=c.id AND newer.source_ref=obs.source_ref AND newer.id>obs.id)
      AND NOT EXISTS(SELECT 1 FROM core_evidence newer WHERE newer.case_id=w.case_id AND newer.kind=se.kind AND newer.source=se.source AND newer.version>se.version AND psl_escalation_json(newer.body)->>'source_identity'=c.source_identity AND psl_escalation_json(newer.body)->>'source_ref'=obs.source_ref)
    ))))
 AND psl_schedules_policy_current(w.case_id,w.policy_id)
 AND EXISTS(SELECT 1 FROM policy_configuration WHERE id=w.policy_id AND component='OPS.factory_issue_execution'));
$$;
CREATE OR REPLACE FUNCTION psl_issue_factory_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NEW.definition<>'pmo-issues/v1' THEN RETURN NEW; END IF;
 IF NEW.preparation_id IS NOT NULL OR NEW.invoice_id IS NOT NULL OR NOT psl_issue_factory_source(NEW) THEN RAISE EXCEPTION 'Exact issue investigation source required'; END IF;
 IF NEW.status='verified' AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity act ON act.id=a.activity_id
  WHERE act.work_id=NEW.id AND act.kind='ACT13' AND a.phase='observed'
   AND a.id=(SELECT max(x.id) FROM workflows_factoryattempt x JOIN workflows_factoryactivity y ON y.id=x.activity_id WHERE y.work_id=NEW.id AND y.kind='ACT13' AND x.phase='observed')
   AND psl_issue_factory_current(NEW,a.result)) THEN RAISE EXCEPTION 'Current issue investigation and native owner response required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_issue_factory_guard BEFORE INSERT OR UPDATE ON workflows_factorywork FOR EACH ROW EXECUTE FUNCTION psl_issue_factory_guard();
CREATE OR REPLACE FUNCTION psl_issue_task_event() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE t workflows_humantask%ROWTYPE;
BEGIN
 SELECT * INTO t FROM workflows_humantask WHERE id=CASE WHEN TG_OP='DELETE' THEN OLD.task_id ELSE NEW.task_id END;
 IF t.kind<>'issue_followup' THEN IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF; END IF;
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Issue follow-up history is append-only'; END IF;
 IF NEW.action='issue.owner_response' AND NOT EXISTS(SELECT 1 FROM pmo_issuestate s JOIN pmo_issue i ON i.id=s.issue_id JOIN core_evidence e ON e.id=(NEW.data->>'head')::bigint
 WHERE s.id::text=NEW.data->>'state_id' AND s.id=i.current_id AND i.case_id=t.case_id AND i.id::text=t.context->>'issue_id'
 AND s.actor_id=NEW.actor_id AND s.owner_id=NEW.actor_id AND s.evidence_id::text=NEW.data->>'evidence_id' AND s.id<>(t.context->>'state_id')::bigint
 AND e.case_id=t.case_id AND e.kind='agent_private_issue_intake' AND e.body::jsonb->>'state_id'=s.id::text
 AND psl_schedules_grants(t.case_id,NEW.actor_id,ARRAY['issue.work','issue.own']))
 THEN RAISE EXCEPTION 'Exact actual owner progress required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_issue_task_event BEFORE INSERT OR UPDATE OR DELETE ON workflows_taskevent FOR EACH ROW EXECUTE FUNCTION psl_issue_task_event();
"""

DROP_GUARDS = r"""DROP TRIGGER psl_issue_task_event ON workflows_taskevent;
DROP FUNCTION psl_issue_task_event();
DROP TRIGGER psl_issue_factory_guard ON workflows_factorywork;
DROP FUNCTION psl_issue_factory_guard();
DROP FUNCTION psl_issue_factory_current(workflows_factorywork,jsonb);
DROP FUNCTION psl_issue_factory_source(workflows_factorywork);
"""

class Migration(migrations.Migration):
    dependencies = [('workflows', '0079_statement_ppe_verification'), ('pmo', '0044_issue_reference_observations')]
    operations = [migrations.RunSQL(IDENTITY + TASK + GUARDS, DROP_GUARDS + PREVIOUS_TASK + PREVIOUS_IDENTITY)]
