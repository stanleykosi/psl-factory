"""P43 frozen formal-minutes and optional outward publication guard.

Literal SQL preserves actual predecessor operations; no mutable helper imports.
"""
from django.db import migrations

PREVIOUS = r"""
CREATE OR REPLACE FUNCTION psl_publication_factory_scope() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF (NEW.factory_work_id IS NULL) IS DISTINCT FROM (NEW.factory_policy_id IS NULL)
  OR (NEW.factory_work_id IS NULL) IS DISTINCT FROM (NEW.factory_source_id IS NULL)
 THEN RAISE EXCEPTION 'Complete optional factory publication scope required'; END IF;
 IF NEW.factory_work_id IS NOT NULL AND NOT EXISTS(
  SELECT 1 FROM workflows_factorywork w JOIN documents_version v ON v.id=NEW.version_id JOIN documents_document d ON d.id=v.document_id
   JOIN policy_configuration p ON p.id=NEW.factory_policy_id JOIN core_evidence e ON e.id=NEW.factory_source_id
   WHERE w.id=NEW.factory_work_id AND w.case_id=d.case_id AND p.case_id=w.case_id AND e.case_id=w.case_id
   AND (
    (w.definition='commercial/v1' AND p.component='OPS.factory_commercial_execution' AND e.kind='agent_private_commercial_intake'
     AND EXISTS(SELECT 1 FROM pmo_commercialdocumentbinding b JOIN pmo_commercialrevision r ON r.id=b.revision_id JOIN pmo_commercialcase c ON c.id=r.dossier_id WHERE b.version_id=v.id AND c.case_id=w.case_id))
    OR
    (w.definition='delivery-handover/v1' AND p.component='OPS.factory_handover_execution' AND e.kind='agent_private_handover_intake'
     AND w.policy_id=p.id AND w.source_head_id=e.id
     AND EXISTS(SELECT 1 FROM pmo_deliverydocumentbinding b JOIN pmo_deliverydossier dd ON dd.id=b.dossier_id
      WHERE b.version_id=v.id AND b.purpose='handover' AND dd.case_id=w.case_id AND b.dossier_id=(w.request->>'dossier')::bigint)
     AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
      WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text))
    OR
    (w.definition='delivery-go-live/v1' AND p.component='OPS.factory_go_live_execution' AND e.kind='agent_private_go_live_intake'
     AND w.policy_id=p.id AND w.source_head_id=e.id
     AND EXISTS(SELECT 1 FROM pmo_deliverydocumentbinding b JOIN pmo_deliverydossier dd ON dd.id=b.dossier_id
      WHERE b.version_id=v.id AND b.purpose='go_live' AND v.audience='client' AND dd.case_id=w.case_id AND b.dossier_id=(w.request->>'dossier')::bigint)
     AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
      WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text))
    OR
    (w.definition='finance-accounts/v1' AND p.component='OPS.factory_accounting_execution'
     AND e.kind='agent_private_accounting_intake'
     AND EXISTS(SELECT 1 FROM finance_financedocumentbinding b JOIN finance_financerun r ON r.id=b.run_id
      JOIN finance_financesource s ON s.id=r.source_id WHERE b.version_id=v.id AND r.case_id=w.case_id
       AND r.kind='formula' AND s.id=(e.body::jsonb->>'source')::bigint AND s.batch_id=(w.request->>'batch')::bigint))

    OR
    (w.definition='rfp-response/v1' AND p.component='OPS.factory_rfp_execution'
     AND e.kind='agent_private_rfp_intake' AND w.policy_id=p.id AND w.source_head_id=e.id AND v.audience='client'
     AND EXISTS(SELECT 1 FROM pmo_rfpdocumentbinding b JOIN pmo_rfpresponse r ON r.id=b.response_id
      JOIN pmo_rfpcase root ON root.id=r.rfp_id JOIN pmo_commercialrevision cr ON cr.id=r.commercial_id
      JOIN core_evidence draft ON draft.id=(cr.sources->>'sow')::bigint
      WHERE b.version_id=v.id AND root.case_id=w.case_id AND root.id=(w.request->>'rfp')::bigint
       AND root.current_response_id=r.id AND root.current_intake_id=r.intake_id AND r.intake_id=(e.body::jsonb->>'intake')::bigint
       AND r.evidence_id=(e.body::jsonb->>'response_evidence')::bigint AND r.matrix=e.body::jsonb->'matrix'
       AND draft.body::jsonb->'public_terms_id'=e.body::jsonb->'public_terms'
       AND cr.sources->'requirements'=e.body::jsonb->'sources'->'requirements'
       AND cr.sources->'plan'=e.body::jsonb->'sources'->'plan' AND cr.sources->'costing'=e.body::jsonb->'sources'->'costing')
     AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
      WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed'
       AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text))

    OR
    (w.definition='finance-accounts/v1' AND p.component='OPS.factory_accounting_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND e.kind='agent_private_accounting_intake'
     AND EXISTS(SELECT 1 FROM finance_financedocumentbinding b JOIN finance_financerun r ON r.id=b.run_id
      JOIN finance_financesource s ON s.id=r.source_id
      JOIN policy_registeredreference cfg ON cfg.case_id=p.case_id
       AND cfg.ref=p.envelope->'value'->>'artifact_ref' AND cfg.version=(p.envelope->'value'->>'artifact_version')::integer
       AND cfg.sha256=p.envelope->'value'->>'sha256'
      WHERE b.version_id=v.id AND r.case_id=w.case_id AND r.kind='statement'
       AND cfg.schema_ref='schema:psl/factory-accounting-execution/v3'
       AND cfg.content->>'statement_contract_id'=r.request->>'contract_id'
       AND r.result->>'scope'='selected_statement_lines' AND r.result->'whole_statement_certified'='false'::jsonb
       AND r.result->>'status'='complete' AND s.id=(e.body::jsonb->>'source')::bigint AND s.batch_id=(w.request->>'batch')::bigint
       AND (SELECT count(*) FROM finance_financestatementinput si WHERE si.statement_id=r.id)=jsonb_array_length(r.snapshot->'inputs')
       AND jsonb_array_length(r.snapshot->'inputs')>0
       AND EXISTS(SELECT 1 FROM finance_financereview fr WHERE fr.run_id=r.id AND fr.purpose='output' AND fr.verdict='approve'
        AND fr.id=(SELECT max(id) FROM finance_financereview WHERE run_id=r.id AND purpose='output')
        AND b.snapshot->>'output_review'=fr.id::text)
       AND NOT EXISTS(SELECT 1 FROM finance_financestatementinput si JOIN finance_financereview fr ON fr.id=si.source_review_id
        WHERE si.statement_id=r.id AND (fr.verdict<>'approve' OR fr.run_id<>si.source_run_id
         OR fr.id<>(SELECT max(id) FROM finance_financereview WHERE run_id=si.source_run_id AND purpose='output')))))

    OR
    (w.definition='pmo-change/v1' AND p.component='OPS.factory_change_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND e.kind='agent_private_change_intake'
     AND EXISTS(SELECT 1 FROM pmo_changedocumentbinding b
      JOIN pmo_changeauthorization ca ON ca.id=b.authorization_id JOIN pmo_changeversion cv ON cv.id=ca.version_id
      JOIN pmo_changerequest cr ON cr.id=cv.change_id
      WHERE b.version_id=v.id AND b.purpose IN ('notice','go_live') AND v.audience='client'
       AND cr.case_id=w.case_id AND cr.id=(w.request->>'change')::bigint AND cr.current_id=cv.id
       AND cv.id=(e.body::jsonb->>'change_version_id')::bigint
       AND ca.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint
       AND v.template_id=(e.body::jsonb->'inputs'->>'template_id')::bigint
       AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
        WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed'
         AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text AND a.result->>'purpose'=b.purpose)))

    OR
    (w.definition='pmo-emergency/v1' AND p.component='OPS.factory_emergency_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND e.kind='agent_private_emergency_intake'
     AND EXISTS(SELECT 1 FROM pmo_emergencydocumentbinding b JOIN pmo_emergencyoutcome o ON o.id=b.outcome_id
      JOIN pmo_emergencyprofile ep ON ep.id=o.profile_id JOIN pmo_changeversion cv ON cv.id=ep.version_id
      JOIN pmo_changerequest cr ON cr.id=cv.change_id JOIN pmo_emergencyretrospectiverecord rr ON rr.outcome_id=o.id
      JOIN pmo_emergencyauthorization ea ON ea.id=o.authorization_id AND ea.profile_id=ep.id
      WHERE b.version_id=v.id AND cr.case_id=w.case_id AND cr.id=(w.request->>'change')::bigint AND cr.current_id=cv.id
       AND ep.id=(e.body::jsonb->>'profile_id')::bigint AND o.id=(e.body::jsonb->'inputs'->>'outcome_id')::bigint
       AND ea.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint AND ea.created_at<=o.implemented_at
       AND b.manifest->>'reconciliation_id'=rr.id::text
       AND v.template_id=(e.body::jsonb->'inputs'->>'template_id')::bigint AND v.audience=e.body::jsonb->'inputs'->>'audience'
       AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
        WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed'
         AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text AND a.result->>'outcome'=o.id::text)))

    OR
    (w.definition='finance-forecast/v1' AND p.component='OPS.factory_forecast_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND e.kind='agent_private_forecast_intake'
     AND EXISTS(SELECT 1 FROM finance_forecastbinding b JOIN finance_forecastrun r ON r.id=b.run_id
      JOIN finance_forecastscenario s ON s.id=r.scenario_id JOIN finance_forecastreview rv ON rv.run_id=r.id
      WHERE b.version_id=v.id AND r.case_id=w.case_id AND s.case_id=w.case_id
       AND s.reference=w.request->>'scenario_reference' AND s.id=(e.body::jsonb->>'scenario_id')::bigint
       AND rv.verdict='approve' AND rv.id=(SELECT max(id) FROM finance_forecastreview WHERE run_id=r.id)
       AND b.snapshot->>'output_review'=rv.id::text AND b.snapshot->>'run_hash'=r.sha256
       AND v.template_id=(e.body::jsonb->>'template_id')::bigint AND v.audience=e.body::jsonb->>'audience'
       AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario newer WHERE newer.case_id=s.case_id AND newer.reference=s.reference AND newer.number>s.number)
       AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
        WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'head'=e.id::text
         AND a.result->>'document_version'=v.id::text AND a.result->>'forecast_run'=r.id::text)))

    OR
    (w.definition='pmo-weekly-report/v1' AND p.component='OPS.factory_reporting_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND NOT w.cancel_requested
     AND w.status NOT IN ('verified','cancelled','followup_needed')
     AND psl_reporting_document(w.id,e.id,v.id)
     AND EXISTS(SELECT 1 FROM documents_controlledreview rv WHERE rv.id=NEW.review_id AND rv.version_id=v.id
      AND rv.verdict='approve' AND rv.payload_sha256=v.payload_sha256
      AND rv.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
      AND psl_reporting_review(w.case_id,rv.id))
     AND psl_reporting_principals(w.id,v.id,NEW.actor_id)
     AND psl_reporting_distribution(w.case_id,v.id,NEW.policies,NEW.recipient_ids,NEW.retention_days)
     AND psl_reporting_grants(w.case_id,NEW.actor_id,ARRAY['case.read','report.read','factory.execute','document.publish']))

    OR
    (w.definition='pmo-escalation/v1' AND NOT w.cancel_requested AND w.status NOT IN ('verified','cancelled','followup_needed')
     AND psl_escalation_document(w.id,v.id,NEW.review_id,NEW.actor_id,p.id,e.id,NEW.recipient_ids,NEW.policies))

   ))
 THEN RAISE EXCEPTION 'Exact same-case registered factory publication references required'; END IF;

 IF NEW.factory_work_id IS NULL AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factorywork w ON w.id=fa.work_id
 JOIN workflows_factoryattempt a ON a.activity_id=fa.id WHERE w.definition='pmo-escalation/v1' AND fa.kind='ACT09' AND a.phase='observed'
 AND a.result->>'document_version'=NEW.version_id::text)
 THEN RAISE EXCEPTION 'Observed escalation communication requires its exact factory scope'; END IF;
 RETURN NEW;
END $$;
"""

SQL = r"""
CREATE OR REPLACE FUNCTION psl_publication_factory_scope() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF (NEW.factory_work_id IS NULL) IS DISTINCT FROM (NEW.factory_policy_id IS NULL)
  OR (NEW.factory_work_id IS NULL) IS DISTINCT FROM (NEW.factory_source_id IS NULL)
 THEN RAISE EXCEPTION 'Complete optional factory publication scope required'; END IF;
 IF NEW.factory_work_id IS NOT NULL AND NOT EXISTS(
  SELECT 1 FROM workflows_factorywork w JOIN documents_version v ON v.id=NEW.version_id JOIN documents_document d ON d.id=v.document_id
   JOIN policy_configuration p ON p.id=NEW.factory_policy_id JOIN core_evidence e ON e.id=NEW.factory_source_id
   WHERE w.id=NEW.factory_work_id AND w.case_id=d.case_id AND p.case_id=w.case_id AND e.case_id=w.case_id
   AND (
    (w.definition='commercial/v1' AND p.component='OPS.factory_commercial_execution' AND e.kind='agent_private_commercial_intake'
     AND EXISTS(SELECT 1 FROM pmo_commercialdocumentbinding b JOIN pmo_commercialrevision r ON r.id=b.revision_id JOIN pmo_commercialcase c ON c.id=r.dossier_id WHERE b.version_id=v.id AND c.case_id=w.case_id))
    OR
    (w.definition='delivery-handover/v1' AND p.component='OPS.factory_handover_execution' AND e.kind='agent_private_handover_intake'
     AND w.policy_id=p.id AND w.source_head_id=e.id
     AND EXISTS(SELECT 1 FROM pmo_deliverydocumentbinding b JOIN pmo_deliverydossier dd ON dd.id=b.dossier_id
      WHERE b.version_id=v.id AND b.purpose='handover' AND dd.case_id=w.case_id AND b.dossier_id=(w.request->>'dossier')::bigint)
     AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
      WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text))
    OR
    (w.definition='delivery-go-live/v1' AND p.component='OPS.factory_go_live_execution' AND e.kind='agent_private_go_live_intake'
     AND w.policy_id=p.id AND w.source_head_id=e.id
     AND EXISTS(SELECT 1 FROM pmo_deliverydocumentbinding b JOIN pmo_deliverydossier dd ON dd.id=b.dossier_id
      WHERE b.version_id=v.id AND b.purpose='go_live' AND v.audience='client' AND dd.case_id=w.case_id AND b.dossier_id=(w.request->>'dossier')::bigint)
     AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
      WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text))
    OR
    (w.definition='finance-accounts/v1' AND p.component='OPS.factory_accounting_execution'
     AND e.kind='agent_private_accounting_intake'
     AND EXISTS(SELECT 1 FROM finance_financedocumentbinding b JOIN finance_financerun r ON r.id=b.run_id
      JOIN finance_financesource s ON s.id=r.source_id WHERE b.version_id=v.id AND r.case_id=w.case_id
       AND r.kind='formula' AND s.id=(e.body::jsonb->>'source')::bigint AND s.batch_id=(w.request->>'batch')::bigint))

    OR
    (w.definition='rfp-response/v1' AND p.component='OPS.factory_rfp_execution'
     AND e.kind='agent_private_rfp_intake' AND w.policy_id=p.id AND w.source_head_id=e.id AND v.audience='client'
     AND EXISTS(SELECT 1 FROM pmo_rfpdocumentbinding b JOIN pmo_rfpresponse r ON r.id=b.response_id
      JOIN pmo_rfpcase root ON root.id=r.rfp_id JOIN pmo_commercialrevision cr ON cr.id=r.commercial_id
      JOIN core_evidence draft ON draft.id=(cr.sources->>'sow')::bigint
      WHERE b.version_id=v.id AND root.case_id=w.case_id AND root.id=(w.request->>'rfp')::bigint
       AND root.current_response_id=r.id AND root.current_intake_id=r.intake_id AND r.intake_id=(e.body::jsonb->>'intake')::bigint
       AND r.evidence_id=(e.body::jsonb->>'response_evidence')::bigint AND r.matrix=e.body::jsonb->'matrix'
       AND draft.body::jsonb->'public_terms_id'=e.body::jsonb->'public_terms'
       AND cr.sources->'requirements'=e.body::jsonb->'sources'->'requirements'
       AND cr.sources->'plan'=e.body::jsonb->'sources'->'plan' AND cr.sources->'costing'=e.body::jsonb->'sources'->'costing')
     AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
      WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed'
       AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text))

    OR
    (w.definition='finance-accounts/v1' AND p.component='OPS.factory_accounting_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND e.kind='agent_private_accounting_intake'
     AND EXISTS(SELECT 1 FROM finance_financedocumentbinding b JOIN finance_financerun r ON r.id=b.run_id
      JOIN finance_financesource s ON s.id=r.source_id
      JOIN policy_registeredreference cfg ON cfg.case_id=p.case_id
       AND cfg.ref=p.envelope->'value'->>'artifact_ref' AND cfg.version=(p.envelope->'value'->>'artifact_version')::integer
       AND cfg.sha256=p.envelope->'value'->>'sha256'
      WHERE b.version_id=v.id AND r.case_id=w.case_id AND r.kind='statement'
       AND cfg.schema_ref='schema:psl/factory-accounting-execution/v3'
       AND cfg.content->>'statement_contract_id'=r.request->>'contract_id'
       AND r.result->>'scope'='selected_statement_lines' AND r.result->'whole_statement_certified'='false'::jsonb
       AND r.result->>'status'='complete' AND s.id=(e.body::jsonb->>'source')::bigint AND s.batch_id=(w.request->>'batch')::bigint
       AND (SELECT count(*) FROM finance_financestatementinput si WHERE si.statement_id=r.id)=jsonb_array_length(r.snapshot->'inputs')
       AND jsonb_array_length(r.snapshot->'inputs')>0
       AND EXISTS(SELECT 1 FROM finance_financereview fr WHERE fr.run_id=r.id AND fr.purpose='output' AND fr.verdict='approve'
        AND fr.id=(SELECT max(id) FROM finance_financereview WHERE run_id=r.id AND purpose='output')
        AND b.snapshot->>'output_review'=fr.id::text)
       AND NOT EXISTS(SELECT 1 FROM finance_financestatementinput si JOIN finance_financereview fr ON fr.id=si.source_review_id
        WHERE si.statement_id=r.id AND (fr.verdict<>'approve' OR fr.run_id<>si.source_run_id
         OR fr.id<>(SELECT max(id) FROM finance_financereview WHERE run_id=si.source_run_id AND purpose='output')))))

    OR
    (w.definition='pmo-change/v1' AND p.component='OPS.factory_change_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND e.kind='agent_private_change_intake'
     AND EXISTS(SELECT 1 FROM pmo_changedocumentbinding b
      JOIN pmo_changeauthorization ca ON ca.id=b.authorization_id JOIN pmo_changeversion cv ON cv.id=ca.version_id
      JOIN pmo_changerequest cr ON cr.id=cv.change_id
      WHERE b.version_id=v.id AND b.purpose IN ('notice','go_live') AND v.audience='client'
       AND cr.case_id=w.case_id AND cr.id=(w.request->>'change')::bigint AND cr.current_id=cv.id
       AND cv.id=(e.body::jsonb->>'change_version_id')::bigint
       AND ca.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint
       AND v.template_id=(e.body::jsonb->'inputs'->>'template_id')::bigint
       AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
        WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed'
         AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text AND a.result->>'purpose'=b.purpose)))

    OR
    (w.definition='pmo-emergency/v1' AND p.component='OPS.factory_emergency_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND e.kind='agent_private_emergency_intake'
     AND EXISTS(SELECT 1 FROM pmo_emergencydocumentbinding b JOIN pmo_emergencyoutcome o ON o.id=b.outcome_id
      JOIN pmo_emergencyprofile ep ON ep.id=o.profile_id JOIN pmo_changeversion cv ON cv.id=ep.version_id
      JOIN pmo_changerequest cr ON cr.id=cv.change_id JOIN pmo_emergencyretrospectiverecord rr ON rr.outcome_id=o.id
      JOIN pmo_emergencyauthorization ea ON ea.id=o.authorization_id AND ea.profile_id=ep.id
      WHERE b.version_id=v.id AND cr.case_id=w.case_id AND cr.id=(w.request->>'change')::bigint AND cr.current_id=cv.id
       AND ep.id=(e.body::jsonb->>'profile_id')::bigint AND o.id=(e.body::jsonb->'inputs'->>'outcome_id')::bigint
       AND ea.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint AND ea.created_at<=o.implemented_at
       AND b.manifest->>'reconciliation_id'=rr.id::text
       AND v.template_id=(e.body::jsonb->'inputs'->>'template_id')::bigint AND v.audience=e.body::jsonb->'inputs'->>'audience'
       AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
        WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed'
         AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text AND a.result->>'outcome'=o.id::text)))

    OR
    (w.definition='finance-forecast/v1' AND p.component='OPS.factory_forecast_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND e.kind='agent_private_forecast_intake'
     AND EXISTS(SELECT 1 FROM finance_forecastbinding b JOIN finance_forecastrun r ON r.id=b.run_id
      JOIN finance_forecastscenario s ON s.id=r.scenario_id JOIN finance_forecastreview rv ON rv.run_id=r.id
      WHERE b.version_id=v.id AND r.case_id=w.case_id AND s.case_id=w.case_id
       AND s.reference=w.request->>'scenario_reference' AND s.id=(e.body::jsonb->>'scenario_id')::bigint
       AND rv.verdict='approve' AND rv.id=(SELECT max(id) FROM finance_forecastreview WHERE run_id=r.id)
       AND b.snapshot->>'output_review'=rv.id::text AND b.snapshot->>'run_hash'=r.sha256
       AND v.template_id=(e.body::jsonb->>'template_id')::bigint AND v.audience=e.body::jsonb->>'audience'
       AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario newer WHERE newer.case_id=s.case_id AND newer.reference=s.reference AND newer.number>s.number)
       AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
        WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'head'=e.id::text
         AND a.result->>'document_version'=v.id::text AND a.result->>'forecast_run'=r.id::text)))

    OR
    (w.definition='pmo-weekly-report/v1' AND p.component='OPS.factory_reporting_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND NOT w.cancel_requested
     AND w.status NOT IN ('verified','cancelled','followup_needed')
     AND psl_reporting_document(w.id,e.id,v.id)
     AND EXISTS(SELECT 1 FROM documents_controlledreview rv WHERE rv.id=NEW.review_id AND rv.version_id=v.id
      AND rv.verdict='approve' AND rv.payload_sha256=v.payload_sha256
      AND rv.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
      AND psl_reporting_review(w.case_id,rv.id))
     AND psl_reporting_principals(w.id,v.id,NEW.actor_id)
     AND psl_reporting_distribution(w.case_id,v.id,NEW.policies,NEW.recipient_ids,NEW.retention_days)
     AND psl_reporting_grants(w.case_id,NEW.actor_id,ARRAY['case.read','report.read','factory.execute','document.publish']))

    OR
    (w.definition='pmo-escalation/v1' AND NOT w.cancel_requested AND w.status NOT IN ('verified','cancelled','followup_needed')
     AND psl_escalation_document(w.id,v.id,NEW.review_id,NEW.actor_id,p.id,e.id,NEW.recipient_ids,NEW.policies))

    OR
    (w.definition='pmo-minutes/v1' AND p.component='OPS.factory_minutes_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND e.kind='agent_private_minutes_intake'
     AND e.body::jsonb->'publish'='true'::jsonb AND v.audience='client'
     AND NOT w.cancel_requested AND w.status NOT IN ('verified','cancelled','followup_needed')
     AND psl_schedules_policy_current(w.case_id,p.id)
     AND NEW.actor_id=(psl_schedules_values(p.id)->0->>'executor_id')::bigint
     AND psl_schedules_grants(w.case_id,NEW.actor_id,ARRAY['case.read','meeting.read','factory.execute','document.publish'])
     AND psl_minutes_current(w.id,e.id,v.id))

   ))
 THEN RAISE EXCEPTION 'Exact same-case registered factory publication references required'; END IF;

 IF NEW.factory_work_id IS NULL AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factorywork w ON w.id=fa.work_id
 JOIN workflows_factoryattempt a ON a.activity_id=fa.id WHERE w.definition='pmo-escalation/v1' AND fa.kind='ACT09' AND a.phase='observed'
 AND a.result->>'document_version'=NEW.version_id::text)
 THEN RAISE EXCEPTION 'Observed escalation communication requires its exact factory scope'; END IF;
 RETURN NEW;
END $$;
"""

REVERSE = r"""
CREATE OR REPLACE FUNCTION psl_publication_factory_scope() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF (NEW.factory_work_id IS NULL) IS DISTINCT FROM (NEW.factory_policy_id IS NULL)
  OR (NEW.factory_work_id IS NULL) IS DISTINCT FROM (NEW.factory_source_id IS NULL)
 THEN RAISE EXCEPTION 'Complete optional factory publication scope required'; END IF;
 IF NEW.factory_work_id IS NOT NULL AND NOT EXISTS(
  SELECT 1 FROM workflows_factorywork w JOIN documents_version v ON v.id=NEW.version_id JOIN documents_document d ON d.id=v.document_id
   JOIN policy_configuration p ON p.id=NEW.factory_policy_id JOIN core_evidence e ON e.id=NEW.factory_source_id
   WHERE w.id=NEW.factory_work_id AND w.case_id=d.case_id AND p.case_id=w.case_id AND e.case_id=w.case_id
   AND (
    (w.definition='commercial/v1' AND p.component='OPS.factory_commercial_execution' AND e.kind='agent_private_commercial_intake'
     AND EXISTS(SELECT 1 FROM pmo_commercialdocumentbinding b JOIN pmo_commercialrevision r ON r.id=b.revision_id JOIN pmo_commercialcase c ON c.id=r.dossier_id WHERE b.version_id=v.id AND c.case_id=w.case_id))
    OR
    (w.definition='delivery-handover/v1' AND p.component='OPS.factory_handover_execution' AND e.kind='agent_private_handover_intake'
     AND w.policy_id=p.id AND w.source_head_id=e.id
     AND EXISTS(SELECT 1 FROM pmo_deliverydocumentbinding b JOIN pmo_deliverydossier dd ON dd.id=b.dossier_id
      WHERE b.version_id=v.id AND b.purpose='handover' AND dd.case_id=w.case_id AND b.dossier_id=(w.request->>'dossier')::bigint)
     AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
      WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text))
    OR
    (w.definition='delivery-go-live/v1' AND p.component='OPS.factory_go_live_execution' AND e.kind='agent_private_go_live_intake'
     AND w.policy_id=p.id AND w.source_head_id=e.id
     AND EXISTS(SELECT 1 FROM pmo_deliverydocumentbinding b JOIN pmo_deliverydossier dd ON dd.id=b.dossier_id
      WHERE b.version_id=v.id AND b.purpose='go_live' AND v.audience='client' AND dd.case_id=w.case_id AND b.dossier_id=(w.request->>'dossier')::bigint)
     AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
      WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text))
    OR
    (w.definition='finance-accounts/v1' AND p.component='OPS.factory_accounting_execution'
     AND e.kind='agent_private_accounting_intake'
     AND EXISTS(SELECT 1 FROM finance_financedocumentbinding b JOIN finance_financerun r ON r.id=b.run_id
      JOIN finance_financesource s ON s.id=r.source_id WHERE b.version_id=v.id AND r.case_id=w.case_id
       AND r.kind='formula' AND s.id=(e.body::jsonb->>'source')::bigint AND s.batch_id=(w.request->>'batch')::bigint))

    OR
    (w.definition='rfp-response/v1' AND p.component='OPS.factory_rfp_execution'
     AND e.kind='agent_private_rfp_intake' AND w.policy_id=p.id AND w.source_head_id=e.id AND v.audience='client'
     AND EXISTS(SELECT 1 FROM pmo_rfpdocumentbinding b JOIN pmo_rfpresponse r ON r.id=b.response_id
      JOIN pmo_rfpcase root ON root.id=r.rfp_id JOIN pmo_commercialrevision cr ON cr.id=r.commercial_id
      JOIN core_evidence draft ON draft.id=(cr.sources->>'sow')::bigint
      WHERE b.version_id=v.id AND root.case_id=w.case_id AND root.id=(w.request->>'rfp')::bigint
       AND root.current_response_id=r.id AND root.current_intake_id=r.intake_id AND r.intake_id=(e.body::jsonb->>'intake')::bigint
       AND r.evidence_id=(e.body::jsonb->>'response_evidence')::bigint AND r.matrix=e.body::jsonb->'matrix'
       AND draft.body::jsonb->'public_terms_id'=e.body::jsonb->'public_terms'
       AND cr.sources->'requirements'=e.body::jsonb->'sources'->'requirements'
       AND cr.sources->'plan'=e.body::jsonb->'sources'->'plan' AND cr.sources->'costing'=e.body::jsonb->'sources'->'costing')
     AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
      WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed'
       AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text))

    OR
    (w.definition='finance-accounts/v1' AND p.component='OPS.factory_accounting_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND e.kind='agent_private_accounting_intake'
     AND EXISTS(SELECT 1 FROM finance_financedocumentbinding b JOIN finance_financerun r ON r.id=b.run_id
      JOIN finance_financesource s ON s.id=r.source_id
      JOIN policy_registeredreference cfg ON cfg.case_id=p.case_id
       AND cfg.ref=p.envelope->'value'->>'artifact_ref' AND cfg.version=(p.envelope->'value'->>'artifact_version')::integer
       AND cfg.sha256=p.envelope->'value'->>'sha256'
      WHERE b.version_id=v.id AND r.case_id=w.case_id AND r.kind='statement'
       AND cfg.schema_ref='schema:psl/factory-accounting-execution/v3'
       AND cfg.content->>'statement_contract_id'=r.request->>'contract_id'
       AND r.result->>'scope'='selected_statement_lines' AND r.result->'whole_statement_certified'='false'::jsonb
       AND r.result->>'status'='complete' AND s.id=(e.body::jsonb->>'source')::bigint AND s.batch_id=(w.request->>'batch')::bigint
       AND (SELECT count(*) FROM finance_financestatementinput si WHERE si.statement_id=r.id)=jsonb_array_length(r.snapshot->'inputs')
       AND jsonb_array_length(r.snapshot->'inputs')>0
       AND EXISTS(SELECT 1 FROM finance_financereview fr WHERE fr.run_id=r.id AND fr.purpose='output' AND fr.verdict='approve'
        AND fr.id=(SELECT max(id) FROM finance_financereview WHERE run_id=r.id AND purpose='output')
        AND b.snapshot->>'output_review'=fr.id::text)
       AND NOT EXISTS(SELECT 1 FROM finance_financestatementinput si JOIN finance_financereview fr ON fr.id=si.source_review_id
        WHERE si.statement_id=r.id AND (fr.verdict<>'approve' OR fr.run_id<>si.source_run_id
         OR fr.id<>(SELECT max(id) FROM finance_financereview WHERE run_id=si.source_run_id AND purpose='output')))))

    OR
    (w.definition='pmo-change/v1' AND p.component='OPS.factory_change_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND e.kind='agent_private_change_intake'
     AND EXISTS(SELECT 1 FROM pmo_changedocumentbinding b
      JOIN pmo_changeauthorization ca ON ca.id=b.authorization_id JOIN pmo_changeversion cv ON cv.id=ca.version_id
      JOIN pmo_changerequest cr ON cr.id=cv.change_id
      WHERE b.version_id=v.id AND b.purpose IN ('notice','go_live') AND v.audience='client'
       AND cr.case_id=w.case_id AND cr.id=(w.request->>'change')::bigint AND cr.current_id=cv.id
       AND cv.id=(e.body::jsonb->>'change_version_id')::bigint
       AND ca.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint
       AND v.template_id=(e.body::jsonb->'inputs'->>'template_id')::bigint
       AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
        WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed'
         AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text AND a.result->>'purpose'=b.purpose)))

    OR
    (w.definition='pmo-emergency/v1' AND p.component='OPS.factory_emergency_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND e.kind='agent_private_emergency_intake'
     AND EXISTS(SELECT 1 FROM pmo_emergencydocumentbinding b JOIN pmo_emergencyoutcome o ON o.id=b.outcome_id
      JOIN pmo_emergencyprofile ep ON ep.id=o.profile_id JOIN pmo_changeversion cv ON cv.id=ep.version_id
      JOIN pmo_changerequest cr ON cr.id=cv.change_id JOIN pmo_emergencyretrospectiverecord rr ON rr.outcome_id=o.id
      JOIN pmo_emergencyauthorization ea ON ea.id=o.authorization_id AND ea.profile_id=ep.id
      WHERE b.version_id=v.id AND cr.case_id=w.case_id AND cr.id=(w.request->>'change')::bigint AND cr.current_id=cv.id
       AND ep.id=(e.body::jsonb->>'profile_id')::bigint AND o.id=(e.body::jsonb->'inputs'->>'outcome_id')::bigint
       AND ea.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint AND ea.created_at<=o.implemented_at
       AND b.manifest->>'reconciliation_id'=rr.id::text
       AND v.template_id=(e.body::jsonb->'inputs'->>'template_id')::bigint AND v.audience=e.body::jsonb->'inputs'->>'audience'
       AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
        WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed'
         AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text AND a.result->>'outcome'=o.id::text)))

    OR
    (w.definition='finance-forecast/v1' AND p.component='OPS.factory_forecast_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND e.kind='agent_private_forecast_intake'
     AND EXISTS(SELECT 1 FROM finance_forecastbinding b JOIN finance_forecastrun r ON r.id=b.run_id
      JOIN finance_forecastscenario s ON s.id=r.scenario_id JOIN finance_forecastreview rv ON rv.run_id=r.id
      WHERE b.version_id=v.id AND r.case_id=w.case_id AND s.case_id=w.case_id
       AND s.reference=w.request->>'scenario_reference' AND s.id=(e.body::jsonb->>'scenario_id')::bigint
       AND rv.verdict='approve' AND rv.id=(SELECT max(id) FROM finance_forecastreview WHERE run_id=r.id)
       AND b.snapshot->>'output_review'=rv.id::text AND b.snapshot->>'run_hash'=r.sha256
       AND v.template_id=(e.body::jsonb->>'template_id')::bigint AND v.audience=e.body::jsonb->>'audience'
       AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario newer WHERE newer.case_id=s.case_id AND newer.reference=s.reference AND newer.number>s.number)
       AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
        WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'head'=e.id::text
         AND a.result->>'document_version'=v.id::text AND a.result->>'forecast_run'=r.id::text)))

    OR
    (w.definition='pmo-weekly-report/v1' AND p.component='OPS.factory_reporting_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND NOT w.cancel_requested
     AND w.status NOT IN ('verified','cancelled','followup_needed')
     AND psl_reporting_document(w.id,e.id,v.id)
     AND EXISTS(SELECT 1 FROM documents_controlledreview rv WHERE rv.id=NEW.review_id AND rv.version_id=v.id
      AND rv.verdict='approve' AND rv.payload_sha256=v.payload_sha256
      AND rv.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
      AND psl_reporting_review(w.case_id,rv.id))
     AND psl_reporting_principals(w.id,v.id,NEW.actor_id)
     AND psl_reporting_distribution(w.case_id,v.id,NEW.policies,NEW.recipient_ids,NEW.retention_days)
     AND psl_reporting_grants(w.case_id,NEW.actor_id,ARRAY['case.read','report.read','factory.execute','document.publish']))

    OR
    (w.definition='pmo-escalation/v1' AND NOT w.cancel_requested AND w.status NOT IN ('verified','cancelled','followup_needed')
     AND psl_escalation_document(w.id,v.id,NEW.review_id,NEW.actor_id,p.id,e.id,NEW.recipient_ids,NEW.policies))

   ))
 THEN RAISE EXCEPTION 'Exact same-case registered factory publication references required'; END IF;

 IF NEW.factory_work_id IS NULL AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factorywork w ON w.id=fa.work_id
 JOIN workflows_factoryattempt a ON a.activity_id=fa.id WHERE w.definition='pmo-escalation/v1' AND fa.kind='ACT09' AND a.phase='observed'
 AND a.result->>'document_version'=NEW.version_id::text)
 THEN RAISE EXCEPTION 'Observed escalation communication requires its exact factory scope'; END IF;
 RETURN NEW;
END $$;
"""

class Migration(migrations.Migration):
    dependencies = [('documents', '0027_factory_escalation'), ('workflows', '0074_factory_minutes')]
    operations = [migrations.RunSQL(SQL, REVERSE)]
