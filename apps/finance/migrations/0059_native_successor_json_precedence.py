from django.db import migrations
SQL=r"""
CREATE OR REPLACE FUNCTION psl_native_successor_metadata_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE link jsonb;
BEGIN
 IF NEW.pin ? 'lineage_contract' OR NEW.result ? 'successors' THEN
   IF NEW.pin->>'lineage_contract' IS DISTINCT FROM 'psl.finance-successor-lineage/v1' OR
      NEW.result->'successors'->>'format' IS DISTINCT FROM 'psl.finance-successor-lineage/v1' OR
      jsonb_typeof(NEW.result->'successors'->'lineage') IS DISTINCT FROM 'array' OR
      (NEW.result->'successors') - ARRAY['format','lineage'] IS DISTINCT FROM '{}'::jsonb THEN
      RAISE EXCEPTION 'Exact opt-in successor metadata supplement required'; END IF;
   FOR link IN SELECT value FROM jsonb_array_elements(NEW.result->'successors'->'lineage') LOOP
     IF link - ARRAY['proposal_ref','relation','successor_ref','status','review_ref','successor_receipt','execution_authorized','financial_effect_verified','debt_waived'] IS DISTINCT FROM '{}'::jsonb OR
        coalesce(link->>'proposal_ref','') !~ '^[0-9]+$' OR coalesce(link->>'successor_ref','') !~ '^[0-9]+$' OR
        coalesce(link->>'relation','') NOT IN ('intent_generation','legal_correction') OR
        coalesce(link->>'status','') NOT IN ('proposed','held','current','stale') OR
        coalesce(link->>'successor_receipt','') NOT IN ('unverified','unknown','present') OR
        link->'execution_authorized' IS DISTINCT FROM 'false'::jsonb OR
        link->'financial_effect_verified' IS DISTINCT FROM 'false'::jsonb OR link->'debt_waived' IS DISTINCT FROM 'false'::jsonb OR
        (link->>'status'='current' AND coalesce(link->>'review_ref','') !~ '^[0-9]+$') OR
        (link->>'successor_receipt'='present' AND link->>'status'<>'current') THEN
        RAISE EXCEPTION 'Bounded inert successor metadata required'; END IF;
   END LOOP;
 END IF;
 RETURN NEW;
END $$;
"""
class Migration(migrations.Migration):
    dependencies=[('finance','0058_native_successor_metadata_guard')]
    operations=[migrations.RunSQL(SQL,reverse_sql=migrations.RunSQL.noop)]
