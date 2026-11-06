from django.db import migrations

SQL="""CREATE OR REPLACE FUNCTION psl_af13_native_probe() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE b workflows_acceptedprotectionreadiness; BEGIN
 PERFORM 1 FROM workflows_integrationcontract WHERE id=NEW.contract_id FOR UPDATE;
 SELECT * INTO b FROM workflows_acceptedprotectionreadiness WHERE contract_id=NEW.contract_id;
 IF FOUND THEN
  IF NEW.intent->'native_accepted_protection' IS DISTINCT FROM jsonb_build_object('binding',b.id,'sha256',b.sha256,'source',b.snapshot) OR NEW.intent->>'kind' NOT IN ('health','receipt') OR NEW.intent ?| ARRAY['native_file','native_protection','native_publication'] OR (NEW.intent->>'kind'='receipt' AND NEW.intent->'source_job' IS DISTINCT FROM to_jsonb(b.job_id)) OR (NEW.intent->>'kind'='health' AND NEW.intent->'source_job' IS DISTINCT FROM 'null'::jsonb) THEN RAISE EXCEPTION 'Exact AF13 native probe provenance required'; END IF;
 ELSIF NEW.intent ? 'native_accepted_protection' OR EXISTS(SELECT 1 FROM workflows_integrationcontract c JOIN workflows_integrationcontract prior_contract ON prior_contract.case_id=c.case_id AND prior_contract.reference=c.reference JOIN workflows_acceptedprotectionreadiness previous ON previous.contract_id=prior_contract.id WHERE c.id=NEW.contract_id) THEN RAISE EXCEPTION 'Unbound AF13 native probe or private history downgrade';
 END IF;
 RETURN NEW; END $$;
"""

class Migration(migrations.Migration):
 dependencies=[('workflows','0018_accepted_protection_native_guards')]
 operations=[migrations.RunSQL(SQL,"""CREATE OR REPLACE FUNCTION psl_af13_native_probe() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE b workflows_acceptedprotectionreadiness; BEGIN
 PERFORM 1 FROM workflows_integrationcontract WHERE id=NEW.contract_id FOR UPDATE;
 SELECT * INTO b FROM workflows_acceptedprotectionreadiness WHERE contract_id=NEW.contract_id;
 IF FOUND THEN
  IF NEW.intent->'native_accepted_protection' IS DISTINCT FROM jsonb_build_object('binding',b.id,'sha256',b.sha256,'source',b.snapshot) OR NEW.intent->>'kind' NOT IN ('health','receipt') OR NEW.intent ?| ARRAY['native_file','native_protection','native_publication'] OR (NEW.intent->>'kind'='receipt' AND NEW.intent->'source_job' IS DISTINCT FROM to_jsonb(b.job_id)) OR (NEW.intent->>'kind'='health' AND NEW.intent->'source_job' IS DISTINCT FROM 'null'::jsonb) THEN RAISE EXCEPTION 'Exact AF13 native probe provenance required'; END IF;
 ELSIF NEW.intent ? 'native_accepted_protection' OR EXISTS(SELECT 1 FROM workflows_integrationcontract c JOIN workflows_integrationcontract old ON old.case_id=c.case_id AND old.reference=c.reference JOIN workflows_acceptedprotectionreadiness previous ON previous.contract_id=old.id WHERE c.id=NEW.contract_id) THEN RAISE EXCEPTION 'Unbound AF13 native probe or private history downgrade';
 END IF;
 RETURN NEW; END $$;
""")]
