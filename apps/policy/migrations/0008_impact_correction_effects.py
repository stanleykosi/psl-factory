"""Extend the closed technical impact registry; retain prior immutable history."""
from django.db import migrations

class Migration(migrations.Migration):
    dependencies=[('policy','0007_pilot_runtime_startup_identity')]
    operations=[migrations.RunSQL("""
CREATE OR REPLACE FUNCTION psl_policy_impact_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE previous policy_configuration; successor policy_configuration; assessment policy_impactassessment; proof core_evidence;
BEGIN
 IF TG_TABLE_NAME='policy_impactassessment' THEN
  SELECT * INTO previous FROM policy_configuration WHERE id=NEW.previous_id;
  SELECT * INTO successor FROM policy_configuration WHERE id=NEW.successor_id;
  SELECT * INTO proof FROM core_evidence WHERE id=NEW.evidence_id;
  IF previous.case_id IS DISTINCT FROM successor.case_id OR previous.component IS DISTINCT FROM successor.component
   OR successor.revision<=previous.revision OR proof.case_id IS DISTINCT FROM previous.case_id OR proof.kind IS DISTINCT FROM 'policy_decision'
   OR jsonb_typeof(NEW.adapters) IS DISTINCT FROM 'array' OR jsonb_array_length(NEW.adapters) NOT BETWEEN 1 AND 10
   OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(NEW.adapters) AS k(value) WHERE value NOT IN ('pmo.decisions','pmo.actions','pmo.schedules','finance.runs','finance.billing','finance.invoice_effects','finance.correction_effects','baas.events','baas.reports','baas.response_effects'))
   OR (SELECT count(DISTINCT value) FROM jsonb_array_elements_text(NEW.adapters) AS k(value)) <> jsonb_array_length(NEW.adapters)
   OR jsonb_typeof(NEW.observation) IS DISTINCT FROM 'object' OR NEW.observation->>'format' IS DISTINCT FROM 'psl.policy-impact/v1'
   OR NEW.observation->>'previous' IS DISTINCT FROM NEW.previous_id::text OR NEW.observation->>'successor' IS DISTINCT FROM NEW.successor_id::text
   OR NEW.sha256 !~ '^[0-9a-f]{64}$' OR NEW.operation_key !~ '^[0-9a-f]{64}$'
   OR length(trim(NEW.reason))=0
  THEN RAISE EXCEPTION 'PSL invalid policy impact assessment identity'; END IF;
 ELSE
  SELECT * INTO assessment FROM policy_impactassessment WHERE id=NEW.assessment_id FOR UPDATE;
  SELECT * INTO previous FROM policy_configuration WHERE id=assessment.previous_id;
  SELECT * INTO proof FROM core_evidence WHERE id=NEW.evidence_id;
  IF NEW.actor_id=assessment.actor_id OR NEW.verdict NOT IN ('accept','reject','defer')
   OR proof.case_id IS DISTINCT FROM previous.case_id OR proof.kind IS DISTINCT FROM 'policy_decision'
   OR NEW.observed_sha256 !~ '^[0-9a-f]{64}$' OR length(trim(NEW.reason))=0
   OR (NEW.verdict='accept' AND NEW.observed_sha256 IS DISTINCT FROM assessment.sha256)
  THEN RAISE EXCEPTION 'PSL invalid engineering impact review identity'; END IF;
 END IF;
 RETURN NEW;
END; $$;
""", """
CREATE OR REPLACE FUNCTION psl_policy_impact_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE previous policy_configuration; successor policy_configuration; assessment policy_impactassessment; proof core_evidence;
BEGIN
 IF TG_TABLE_NAME='policy_impactassessment' THEN
  SELECT * INTO previous FROM policy_configuration WHERE id=NEW.previous_id;
  SELECT * INTO successor FROM policy_configuration WHERE id=NEW.successor_id;
  SELECT * INTO proof FROM core_evidence WHERE id=NEW.evidence_id;
  IF previous.case_id IS DISTINCT FROM successor.case_id OR previous.component IS DISTINCT FROM successor.component
   OR successor.revision<=previous.revision OR proof.case_id IS DISTINCT FROM previous.case_id OR proof.kind IS DISTINCT FROM 'policy_decision'
   OR jsonb_typeof(NEW.adapters) IS DISTINCT FROM 'array' OR jsonb_array_length(NEW.adapters) NOT BETWEEN 1 AND 9
   OR jsonb_typeof(NEW.observation) IS DISTINCT FROM 'object' OR NEW.observation->>'format' IS DISTINCT FROM 'psl.policy-impact/v1'
   OR NEW.observation->>'previous' IS DISTINCT FROM NEW.previous_id::text OR NEW.observation->>'successor' IS DISTINCT FROM NEW.successor_id::text
   OR NEW.sha256 !~ '^[0-9a-f]{64}$' OR NEW.operation_key !~ '^[0-9a-f]{64}$'
   OR length(trim(NEW.reason))=0
  THEN RAISE EXCEPTION 'PSL invalid policy impact assessment identity'; END IF;
 ELSE
  SELECT * INTO assessment FROM policy_impactassessment WHERE id=NEW.assessment_id FOR UPDATE;
  SELECT * INTO previous FROM policy_configuration WHERE id=assessment.previous_id;
  SELECT * INTO proof FROM core_evidence WHERE id=NEW.evidence_id;
  IF NEW.actor_id=assessment.actor_id OR NEW.verdict NOT IN ('accept','reject','defer')
   OR proof.case_id IS DISTINCT FROM previous.case_id OR proof.kind IS DISTINCT FROM 'policy_decision'
   OR NEW.observed_sha256 !~ '^[0-9a-f]{64}$' OR length(trim(NEW.reason))=0
   OR (NEW.verdict='accept' AND NEW.observed_sha256 IS DISTINCT FROM assessment.sha256)
  THEN RAISE EXCEPTION 'PSL invalid engineering impact review identity'; END IF;
 END IF;
 RETURN NEW;
END; $$;
""")]
