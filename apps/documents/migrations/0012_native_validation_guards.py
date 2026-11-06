from django.db import migrations

class Migration(migrations.Migration):
    dependencies=[('documents','0011_native_file_acceptance')]
    operations=[migrations.RunSQL("""CREATE FUNCTION psl_native_validation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p documents_validationpackage; e documents_validationexample; r documents_validationreview;
 family text; job_id bigint; source_case uuid; source_created timestamptz;
BEGIN
 IF NEW.provenance->>'format' IS DISTINCT FROM 'psl.native-validation/v1' THEN RETURN NEW; END IF;
 SELECT * INTO p FROM documents_validationpackage WHERE id=NEW.package_id;
 SELECT * INTO e FROM documents_validationexample WHERE id=NEW.example_id;
 SELECT * INTO r FROM documents_validationreview WHERE id=NEW.expectation_review_id;
 family=NEW.provenance->>'family';job_id=(NEW.provenance->>'job')::bigint;
 IF family='handoff' THEN SELECT j0.case_id,j0.created_at INTO source_case,source_created FROM workflows_outbox j0  WHERE j0.id=job_id;
 ELSIF family='publication' THEN SELECT j3.case_id,j0.created_at INTO source_case,source_created FROM documents_publicationjob j0 JOIN documents_publication j1 ON j0.publication_id=j1.id JOIN documents_version j2 ON j1.version_id=j2.id JOIN documents_document j3 ON j2.document_id=j3.id WHERE j0.id=job_id;
 ELSIF family='invoice' THEN SELECT j1.case_id,j0.created_at INTO source_case,source_created FROM finance_invoicejob j0 JOIN finance_invoice j1 ON j0.invoice_id=j1.id WHERE j0.id=job_id;
 ELSIF family='engineering' THEN SELECT j1.case_id,j0.created_at INTO source_case,source_created FROM baas_correctivejob j0 JOIN baas_correctiverequest j1 ON j0.request_id=j1.id WHERE j0.id=job_id;
 ELSIF family='partner' THEN SELECT j2.case_id,j0.created_at INTO source_case,source_created FROM baas_partnerfinancejob j0 JOIN baas_partnerreport j1 ON j0.report_id=j1.id JOIN baas_partnerrecord j2 ON j1.record_id=j2.id WHERE j0.id=job_id;
 ELSIF family='approval' THEN SELECT j1.case_id,j0.created_at INTO source_case,source_created FROM pmo_approvalroutejob j0 JOIN pmo_approvalrequest j1 ON j0.request_id=j1.id WHERE j0.id=job_id;
 ELSIF family='supportresponse' THEN SELECT j1.case_id,j0.created_at INTO source_case,source_created FROM baas_supportresponsejob j0 JOIN baas_supportresponsepacket j1 ON j0.packet_id=j1.id WHERE j0.id=job_id;
 ELSIF family='supportchannel' THEN SELECT j1.case_id,j0.created_at INTO source_case,source_created FROM baas_supportchannelcheck j0 JOIN baas_supportchannelclaim j1 ON j0.claim_id=j1.id WHERE j0.id=job_id;
 ELSIF family='ledgerdata' THEN SELECT j1.case_id,j0.created_at INTO source_case,source_created FROM agents_evidenceextraction j0 JOIN agents_evidenceprojection j1 ON j0.projection_id=j1.id WHERE j0.id=job_id;
 ELSIF family='financefollowup' THEN SELECT j3.case_id,j0.created_at INTO source_case,source_created FROM workflows_financefollowupdispatch j0 JOIN workflows_nativefinancepacket j1 ON j0.packet_id=j1.id JOIN workflows_nativefinancemapping j2 ON j1.mapping_id=j2.id JOIN workflows_reconstitutionplan j3 ON j2.plan_id=j3.id WHERE j0.id=job_id;
 ELSE RAISE EXCEPTION 'PSL unknown native validation source'; END IF;
 IF source_case IS DISTINCT FROM p.case_id OR source_created<=r.created_at OR source_created IS NULL
 OR NOT EXISTS (SELECT 1 FROM core_evidence WHERE id=NEW.evidence_id AND case_id=p.case_id)
 OR NEW.provenance->>'evidence_class' IS DISTINCT FROM (SELECT CASE WHEN synthetic THEN 'synthetic_native_execution' ELSE 'operational_native_execution' END FROM core_case WHERE id=p.case_id)
 OR e.case_id IS DISTINCT FROM p.case_id OR r.package_id IS DISTINCT FROM p.id
 OR r.kind IS DISTINCT FROM 'expectations' OR r.verdict IS DISTINCT FROM 'approve'
 OR NOT p.payload->'example_ids' @> to_jsonb(NEW.example_id)
 OR NEW.provenance->>'build_ref' IS DISTINCT FROM p.payload->>'build_ref'
 OR NEW.provenance->>'source_identity' IS NULL OR NEW.provenance->>'source_identity' !~ '^[a-f0-9]{64}$'
 OR NEW.provenance->>'scope' IS DISTINCT FROM 'native_source_receipt_only'
 OR NEW.provenance->'external_acceptance_claimed' IS DISTINCT FROM 'false'::jsonb
 OR NEW.result->>'implementation' IS DISTINCT FROM 'psl.native-validation/v1'
 OR NEW.result->>'execution_evidence' IS DISTINCT FROM 'native_source_observation'
 OR NEW.actual->>'family' IS DISTINCT FROM family
 OR jsonb_typeof(NEW.actual->'receipt_present') IS DISTINCT FROM 'boolean'
 THEN RAISE EXCEPTION 'PSL invalid native workflow evaluation identity'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER psl_native_validation_identity BEFORE INSERT ON documents_validationreplay FOR EACH ROW EXECUTE FUNCTION psl_native_validation_guard();
""", "DROP TRIGGER psl_native_validation_identity ON documents_validationreplay; DROP FUNCTION psl_native_validation_guard();")]
