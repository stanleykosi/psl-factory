import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


SQL = r"""
CREATE FUNCTION psl_change_applicability_policy(r pmo_changeclosureapplicability,cid uuid,vid bigint) RETURNS boolean LANGUAGE plpgsql VOLATILE AS $$
DECLARE p policy_configuration; rr policy_registeredreference; rules jsonb; entry jsonb; owner jsonb; src core_evidence;
BEGIN
 SELECT * INTO STRICT p FROM policy_configuration WHERE id=r.policy_id AND case_id=cid AND component='D11.change_go_live_client_applicability';
 IF psl_reporting_policy(cid,p.id) IS DISTINCT FROM true THEN RETURN false; END IF;
 SELECT * INTO STRICT rr FROM policy_registeredreference WHERE case_id=cid AND ref=p.envelope->'value'->>'artifact_ref'
  AND version::text=p.envelope->'value'->>'artifact_version' AND sha256=p.envelope->'value'->>'sha256'
  AND schema_ref='schema:psl/change-go-live-client-applicability/v1' AND schema_ref=p.envelope->'value'->>'schema_ref';
 rules:=rr.content;
 IF psl_gl_keys(rules,ARRAY['protocol','case_id','entries','allow_synthetic']) IS DISTINCT FROM true
 OR rules->>'protocol' IS DISTINCT FROM 'change-go-live-client-applicability/v1' OR rules->>'case_id' IS DISTINCT FROM cid::text
 OR jsonb_typeof(rules->'entries') IS DISTINCT FROM 'array' OR jsonb_array_length(rules->'entries')>100
 OR NOT EXISTS(SELECT 1 FROM core_case WHERE id=cid AND kind='project' AND to_jsonb(synthetic)=rules->'allow_synthetic')
 OR (SELECT count(*) FROM jsonb_array_elements(rules->'entries') x WHERE x->>'authorization_id'=r.authorization_id::text)<>1
 THEN RETURN false; END IF;
 SELECT x INTO STRICT entry FROM jsonb_array_elements(rules->'entries') x WHERE x->>'authorization_id'=r.authorization_id::text;
 IF psl_gl_keys(entry,ARRAY['change_version_id','authorization_id','requirement','source','owner','rationale']) IS DISTINCT FROM true
 OR entry->'change_version_id' IS DISTINCT FROM to_jsonb(vid) OR entry->'authorization_id' IS DISTINCT FROM to_jsonb(r.authorization_id)
 OR entry->>'requirement' IS DISTINCT FROM r.requirement OR r.requirement NOT IN ('required','not_applicable')
 OR jsonb_typeof(entry->'rationale') IS DISTINCT FROM 'string' OR length(btrim(entry->>'rationale')) NOT BETWEEN 1 AND 200
 OR r.declaration->'applicability' IS DISTINCT FROM jsonb_build_object('policy_id',p.id,'revision',p.revision,'entry',entry)
 THEN RETURN false; END IF;
 SELECT * INTO STRICT src FROM core_evidence WHERE id=(entry->'source'->>'id')::bigint AND case_id=cid AND kind='policy_decision';
 IF entry->'source' IS DISTINCT FROM jsonb_build_object('id',src.id,'version',src.version,'sha256',src.sha256) THEN RETURN false; END IF;
 owner:=entry->'owner';
 IF psl_gl_keys(owner,ARRAY['actor_id','role','authority']) IS DISTINCT FROM true
 OR psl_gl_keys(owner->'authority',ARRAY['D05.role_principal_assignments']) IS DISTINCT FROM true
 OR jsonb_typeof(owner->'actor_id') IS DISTINCT FROM 'number'
 OR psl_schedules_grants(cid,(owner->>'actor_id')::bigint,ARRAY['case.read']) IS DISTINCT FROM true
 OR psl_schedules_role_current(cid,(owner->>'actor_id')::bigint,owner->'authority',owner->>'role') IS DISTINCT FROM true
 OR psl_schedules_authority_current(cid,owner->'authority') IS DISTINCT FROM true
 OR length(btrim(r.operation_key)) NOT BETWEEN 1 AND 100
 THEN RETURN false; END IF;
 RETURN true;
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;

CREATE FUNCTION psl_change_applicability_current(r pmo_changeclosureapplicability) RETURNS boolean LANGUAGE plpgsql VOLATILE AS $$
DECLARE a jsonb:=r.declaration; ca pmo_changeauthorization; cv pmo_changeversion; cr pmo_changerequest;
 rec documents_publicationreceipt; v documents_version; b pmo_changedocumentbinding; ce core_evidence;
 old pmo_changeclosureapplicability; legacy pmo_changeclosuresignaturebinding; closed pmo_changeclosure; s jsonb; e core_evidence; role text; k text;
 executions jsonb; ids jsonb; prior bigint; signed timestamptz;
BEGIN
 SELECT * INTO STRICT ca FROM pmo_changeauthorization WHERE id=r.authorization_id;
 SELECT * INTO STRICT cv FROM pmo_changeversion WHERE id=ca.version_id;
 SELECT * INTO STRICT cr FROM pmo_changerequest WHERE id=cv.change_id AND current_id=cv.id;
 SELECT * INTO STRICT ce FROM core_evidence WHERE id=cv.evidence_id AND case_id=cr.case_id;
 SELECT * INTO STRICT rec FROM documents_publicationreceipt WHERE id=r.receipt_id;
 SELECT vv.* INTO STRICT v FROM documents_version vv JOIN documents_publication p ON p.version_id=vv.id WHERE p.id=rec.publication_id;
 SELECT * INTO STRICT b FROM pmo_changedocumentbinding WHERE version_id=v.id AND authorization_id=ca.id AND purpose='go_live';
 SELECT jsonb_agg(x.id ORDER BY x.kind),jsonb_agg(jsonb_build_object('id',x.id,'kind',x.kind,'evidence',jsonb_build_object('id',ev.id,'version',ev.version,'sha256',ev.sha256)) ORDER BY x.kind)
 INTO ids,executions FROM (SELECT DISTINCT ON (kind) * FROM pmo_changeexecutionevent WHERE authorization_id=ca.id ORDER BY kind,id DESC) x JOIN core_evidence ev ON ev.id=x.evidence_id;
 IF jsonb_array_length(ids)<>4 OR ids<>r.execution_ids OR ids<>b.execution_ids
  OR NOT EXISTS(SELECT 1 FROM pmo_changeexecutionevent t JOIN pmo_changeexecutionevent i ON i.authorization_id=t.authorization_id AND i.kind='implemented' WHERE t.authorization_id=ca.id AND t.kind='testing_validated' AND to_jsonb(t.id)<@ids AND to_jsonb(i.id)<@ids AND t.id>i.id)
  OR NOT psl_gl_keys(a,ARRAY['protocol','purpose','case_id','change','authorization','execution','report','signatures','attesting_actor_id','applicability'])
  OR a->>'protocol' IS DISTINCT FROM 'change-go-live-applicability-attestation/v1' OR a->>'purpose' IS DISTINCT FROM 'change_go_live_acceptance'
  OR a->'case_id'<>to_jsonb(cr.case_id::text) OR a->'attesting_actor_id'<>to_jsonb(r.actor_id)
  OR a->'change'<>jsonb_build_object('id',cr.id,'reference',cr.reference,'version_id',cv.id,'number',cv.number,'evidence',jsonb_build_object('id',ce.id,'version',ce.version,'sha256',ce.sha256))
  OR a->'authorization'<>jsonb_build_object('id',ca.id,'assessment_ids',ca.assessment_ids,'decision_ids',ca.decision_ids)
  OR a->'execution'<>executions OR a->'report'<>jsonb_build_object('document_id',v.document_id,'version_id',v.id,'number',v.number,'payload_sha256',v.payload_sha256,'receipt_id',rec.id)
  OR NOT psl_gl_keys(a->'signatures',CASE WHEN r.requirement='required' THEN ARRAY['PM','Client'] ELSE ARRAY['PM'] END) OR v.audience<>'client' OR rec.payload<>v.payload OR rec.payload_sha256<>v.payload_sha256
  OR NOT EXISTS(SELECT 1 FROM documents_document dd WHERE dd.id=v.document_id AND dd.case_id=cr.case_id AND dd.current_id=v.id)
  OR NOT psl_gl_keys(r.authority,ARRAY['D05.role_principal_assignments'])
  OR NOT psl_schedules_grants(cr.case_id,r.actor_id,ARRAY['case.read','change.manage'])
  OR NOT psl_schedules_authority_current(cr.case_id,r.authority)
  OR NOT psl_schedules_role_current(cr.case_id,r.actor_id,r.authority,'PM')
  OR length(btrim(r.note)) NOT BETWEEN 1 AND 4000
 THEN RETURN false; END IF;
 -- A captured decision/assessment may not silently represent a later revision.
 IF EXISTS(SELECT 1 FROM pmo_changeassessment x JOIN pmo_changeassessment later ON later.version_id=x.version_id AND later.contributor=x.contributor AND later.id>x.id WHERE x.version_id=cv.id AND ca.assessment_ids @> to_jsonb(x.id))
 OR EXISTS(SELECT 1 FROM pmo_changedecision x JOIN pmo_changedecision later ON later.version_id=x.version_id AND later.role=x.role AND later.id>x.id WHERE x.version_id=cv.id AND ca.decision_ids @> to_jsonb(x.id))
 THEN RETURN false; END IF;
 SELECT max(id) INTO prior FROM pmo_changeclosureapplicability WHERE authorization_id=ca.id AND id<r.id;
 IF r.previous_id IS DISTINCT FROM prior THEN RETURN false; END IF;
 SELECT * INTO closed FROM pmo_changeclosure WHERE authorization_id=ca.id;
 IF NOT psl_change_applicability_policy(r,cr.case_id,cv.id) THEN RETURN false; END IF;
 IF closed.id IS NOT NULL AND (closed.receipt_id<>r.receipt_id OR closed.pm_signature_id<>r.pm_signature_id OR closed.execution_ids<>r.execution_ids) THEN RETURN false; END IF;
 SELECT * INTO legacy FROM pmo_changeclosuresignaturebinding WHERE authorization_id=ca.id ORDER BY id DESC LIMIT 1;
 IF r.legacy_binding_id IS DISTINCT FROM legacy.id THEN RETURN false; END IF;
 IF prior IS NOT NULL THEN
  SELECT * INTO STRICT old FROM pmo_changeclosureapplicability WHERE id=prior;
  IF old.declaration->'signatures'->'PM'<>a->'signatures'->'PM' THEN RETURN false; END IF;
 ELSIF legacy.id IS NOT NULL AND legacy.declaration->'signatures'->'PM'<>a->'signatures'->'PM' THEN RETURN false;
 END IF;
 FOREACH role IN ARRAY CASE WHEN r.requirement='required' THEN ARRAY['PM','Client'] ELSE ARRAY['PM'] END LOOP
  s:=a->'signatures'->role;
  IF NOT psl_gl_keys(s,ARRAY['evidence','source_system','source_reference','decision_id','decision_version','signer_reference','purpose','signed_at']) OR s->>'purpose' IS DISTINCT FROM 'change_go_live_acceptance' THEN RETURN false; END IF;
  FOREACH k IN ARRAY ARRAY['source_system','source_reference','decision_id','decision_version','signer_reference'] LOOP
   IF jsonb_typeof(s->k)<>'string' OR (s->>k)!~'^[A-Za-z0-9][A-Za-z0-9._:/@+ -]{0,239}$' OR btrim(s->>k)<>s->>k THEN RETURN false; END IF;
  END LOOP;
  IF jsonb_typeof(s->'signed_at')<>'string' OR (s->>'signed_at')!~'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$' THEN RETURN false; END IF;
  signed:=(s->>'signed_at')::timestamptz;
  IF signed<=v.created_at OR signed>statement_timestamp() THEN RETURN false; END IF;
  IF closed.id IS NOT NULL AND (role='PM' OR r.client_signature_id=closed.client_signature_id) AND signed>closed.created_at THEN RETURN false; END IF;
  SELECT * INTO STRICT e FROM core_evidence WHERE id=CASE role WHEN 'PM' THEN r.pm_signature_id ELSE r.client_signature_id END AND case_id=cr.case_id AND kind='signature';
  IF s->'evidence'<>jsonb_build_object('id',e.id,'version',e.version,'sha256',e.sha256)
   OR EXISTS(SELECT 1 FROM pmo_gaterecord g WHERE g.evidence_id=e.id AND g.kind IN ('uat_product_manager','uat_product_owner','uat_client'))
   OR EXISTS(SELECT 1 FROM pmo_commercialsignaturepacket pp, LATERAL jsonb_each(pp.signatures) sig WHERE pp.case_id=cr.case_id AND sig.value->>'evidence_id'=e.id::text)
   OR EXISTS(SELECT 1 FROM pmo_changeclosure cc JOIN pmo_changeauthorization ac ON ac.id=cc.authorization_id JOIN pmo_changeversion vc ON vc.id=ac.version_id JOIN pmo_changerequest rc ON rc.id=vc.change_id WHERE rc.case_id=cr.case_id AND ac.id<>ca.id AND (cc.pm_signature_id=e.id OR cc.client_signature_id=e.id))
   OR EXISTS(SELECT 1 FROM pmo_changeclosuresignaturebinding used JOIN pmo_changeauthorization ac ON ac.id=used.authorization_id JOIN pmo_changeversion vc ON vc.id=ac.version_id JOIN pmo_changerequest rc ON rc.id=vc.change_id WHERE rc.case_id=cr.case_id AND ac.id<>ca.id AND (used.pm_signature_id=e.id OR used.client_signature_id=e.id OR EXISTS(SELECT 1 FROM jsonb_each(used.declaration->'signatures') sig WHERE sig.value->'source_system'=s->'source_system' AND sig.value->'source_reference'=s->'source_reference' AND sig.value->'decision_id'=s->'decision_id' AND sig.value->'decision_version'=s->'decision_version')))
   OR EXISTS(SELECT 1 FROM pmo_changeclosureapplicability used JOIN pmo_changeauthorization ac ON ac.id=used.authorization_id JOIN pmo_changeversion vc ON vc.id=ac.version_id JOIN pmo_changerequest rc ON rc.id=vc.change_id WHERE rc.case_id=cr.case_id AND ac.id<>ca.id AND (used.pm_signature_id=e.id OR used.client_signature_id=e.id OR EXISTS(SELECT 1 FROM jsonb_each(used.declaration->'signatures') sig WHERE sig.value->'source_system'=s->'source_system' AND sig.value->'source_reference'=s->'source_reference' AND sig.value->'decision_id'=s->'decision_id' AND sig.value->'decision_version'=s->'decision_version')))
   OR EXISTS(SELECT 1 FROM pmo_deliveryrecord used JOIN pmo_deliverydossier dd ON dd.id=used.dossier_id WHERE dd.case_id=cr.case_id AND used.kind IN ('go_live','go_live_reaffirmation') AND (used.data->>'pm_signature_id'=e.id::text OR used.data->>'client_signature_id'=e.id::text OR EXISTS(SELECT 1 FROM jsonb_each(used.data->'attestation'->'signatures') sig WHERE sig.value->'source_system'=s->'source_system' AND sig.value->'source_reference'=s->'source_reference' AND sig.value->'decision_id'=s->'decision_id' AND sig.value->'decision_version'=s->'decision_version')))
  THEN RETURN false; END IF;
 END LOOP;
 RETURN (r.requirement='required' AND r.client_signature_id IS NOT NULL AND r.pm_signature_id<>r.client_signature_id) OR (r.requirement='not_applicable' AND r.client_signature_id IS NULL);
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;

CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON pmo_changeclosureapplicability FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE FUNCTION psl_change_applicability_insert() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'Change applicability requires READ COMMITTED'; END IF;
 PERFORM 1 FROM core_case c JOIN pmo_changerequest cr ON cr.case_id=c.id JOIN pmo_changeversion cv ON cv.change_id=cr.id JOIN pmo_changeauthorization ca ON ca.version_id=cv.id WHERE ca.id=NEW.authorization_id FOR UPDATE OF c;
 IF EXISTS(SELECT 1 FROM pmo_changeclosureapplicability later WHERE later.authorization_id=NEW.authorization_id AND later.id>=NEW.id)
 OR psl_change_applicability_current(NEW) IS DISTINCT FROM true THEN RAISE EXCEPTION 'Exact current owner-backed applicability, PM signature and delivered change artifact required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_change_applicability_insert BEFORE INSERT ON pmo_changeclosureapplicability FOR EACH ROW EXECUTE FUNCTION psl_change_applicability_insert();
CREATE FUNCTION psl_change_closure_assurance_current(cc pmo_changeclosure) RETURNS boolean LANGUAGE plpgsql VOLATILE AS $$
DECLARE a pmo_changeclosureapplicability; s pmo_changeclosuresignaturebinding;
BEGIN
 SELECT * INTO a FROM pmo_changeclosureapplicability WHERE authorization_id=cc.authorization_id ORDER BY id DESC LIMIT 1;
 IF a.id IS NOT NULL THEN
  RETURN a.receipt_id=cc.receipt_id AND a.pm_signature_id=cc.pm_signature_id AND a.execution_ids=cc.execution_ids AND psl_change_applicability_current(a);
 END IF;
 SELECT * INTO s FROM pmo_changeclosuresignaturebinding WHERE authorization_id=cc.authorization_id ORDER BY id DESC LIMIT 1;
 RETURN COALESCE(s.receipt_id=cc.receipt_id AND s.pm_signature_id=cc.pm_signature_id AND s.client_signature_id=cc.client_signature_id AND s.execution_ids=cc.execution_ids AND psl_change_signature_current(s),false);
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;
-- Claim truth is separate from signature authenticity and release authority.
CREATE FUNCTION psl_change_assurance_claim(cc pmo_changeclosure, claim jsonb) RETURNS boolean LANGUAGE plpgsql VOLATILE AS $$
DECLARE assurance pmo_changeclosureapplicability; binding pmo_changeclosuresignaturebinding;
 aid bigint; client_id bigint; requirement text;
BEGIN
 IF psl_change_closure_assurance_current(cc) IS DISTINCT FROM true THEN RETURN false; END IF;
 SELECT * INTO assurance FROM pmo_changeclosureapplicability WHERE authorization_id=cc.authorization_id ORDER BY id DESC LIMIT 1;
 IF assurance.id IS NOT NULL THEN
  aid:=assurance.id; client_id:=assurance.client_signature_id; requirement:=assurance.requirement;
 ELSE
  SELECT * INTO binding FROM pmo_changeclosuresignaturebinding WHERE authorization_id=cc.authorization_id ORDER BY id DESC LIMIT 1;
  aid:=binding.id; client_id:=binding.client_signature_id; requirement:='required';
  -- Historical signed v1 observations need no invented new policy or assurance.
  IF NOT (claim ?| ARRAY['assurance_id','client_signature_requirement','client_signed','original_closure_client_signed','current_client_signature_id']) THEN
   RETURN COALESCE(claim->>'verification_scope'='native_controlled_change_delivery_and_human_signature_attestation'
    AND claim->'deployment_authorized'='false'::jsonb AND claim->'external_authenticity_verified'='false'::jsonb,false);
  END IF;
 END IF;
 RETURN COALESCE(claim->>'verification_scope'='native_controlled_change_delivery_and_human_acceptance_assurance'
  AND claim->'assurance_id'=to_jsonb(aid) AND claim->'client_signature_requirement'=to_jsonb(requirement)
  AND claim->'client_signed'=to_jsonb(client_id IS NOT NULL)
  AND claim->'original_closure_client_signed'=to_jsonb(cc.client_signature_id IS NOT NULL)
  AND claim->'current_client_signature_id'=COALESCE(to_jsonb(client_id),'null'::jsonb)
  AND claim->'deployment_authorized'='false'::jsonb AND claim->'external_authenticity_verified'='false'::jsonb,false);
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;
CREATE FUNCTION psl_change_observed_assurance_claim() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE workrow workflows_factorywork; activityrow workflows_factoryactivity;
BEGIN
 SELECT * INTO STRICT activityrow FROM workflows_factoryactivity WHERE id=NEW.activity_id;
 SELECT * INTO STRICT workrow FROM workflows_factorywork WHERE id=activityrow.work_id;
 IF workrow.definition='pmo-change/v1' AND activityrow.kind='ACT13' AND NEW.phase='observed' THEN
  PERFORM 1 FROM core_case WHERE id=workrow.case_id FOR UPDATE;
  IF NOT EXISTS(SELECT 1 FROM pmo_changeclosure cc
   JOIN documents_publicationreceipt rec ON rec.id=cc.receipt_id JOIN documents_publication pub ON pub.id=rec.publication_id
   WHERE pub.factory_work_id=workrow.id AND pub.factory_source_id=workrow.source_head_id
    AND NEW.result->'verified'='true'::jsonb AND NEW.result->'head'=to_jsonb(workrow.source_head_id)
    AND NEW.result->'closure'=to_jsonb(cc.id) AND NEW.result->'authorization'=to_jsonb(cc.authorization_id)
    AND NEW.result->'document_version'=to_jsonb(pub.version_id) AND NEW.result->'receipt_ids' @> to_jsonb(ARRAY[rec.id])
    AND psl_change_assurance_claim(cc,NEW.result))
  THEN RAISE EXCEPTION 'Observed change claims require exact current assurance and truthful original/current Client facts'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_change_observed_assurance_claim BEFORE INSERT ON workflows_factoryattempt FOR EACH ROW EXECUTE FUNCTION psl_change_observed_assurance_claim();
CREATE OR REPLACE FUNCTION psl_change_closure_insert() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a pmo_changeclosureapplicability;
BEGIN
 IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'Change closure requires READ COMMITTED'; END IF;
 PERFORM 1 FROM core_case c JOIN pmo_changerequest cr ON cr.case_id=c.id JOIN pmo_changeversion cv ON cv.change_id=cr.id JOIN pmo_changeauthorization ca ON ca.version_id=cv.id WHERE ca.id=NEW.authorization_id FOR UPDATE OF c;
 SELECT * INTO a FROM pmo_changeclosureapplicability WHERE authorization_id=NEW.authorization_id ORDER BY id DESC LIMIT 1;
 IF a.id IS NOT NULL THEN
  IF a.actor_id<>NEW.actor_id OR a.previous_id IS NOT NULL OR a.receipt_id<>NEW.receipt_id OR a.pm_signature_id<>NEW.pm_signature_id
   OR a.client_signature_id IS DISTINCT FROM NEW.client_signature_id OR a.execution_ids<>NEW.execution_ids
   OR psl_change_applicability_current(a) IS DISTINCT FROM true THEN RAISE EXCEPTION 'Initial closure requires exact current applicability proof'; END IF;
 ELSIF NOT EXISTS(SELECT 1 FROM pmo_changeclosuresignaturebinding r WHERE r.authorization_id=NEW.authorization_id AND r.receipt_id=NEW.receipt_id AND r.pm_signature_id=NEW.pm_signature_id AND r.client_signature_id=NEW.client_signature_id AND r.execution_ids=NEW.execution_ids AND r.actor_id=NEW.actor_id AND r.mode='fresh_signatures' AND psl_change_signature_current(r)) THEN
  RAISE EXCEPTION 'Initial closure requires exact current actual PM/Client source signature binding';
 END IF;
 RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION psl_change_signature_verified() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='UPDATE' AND OLD.status='verified' AND NEW.status='verified' AND NEW.source_head_id IS NOT DISTINCT FROM OLD.source_head_id AND NEW.request=OLD.request THEN RETURN NEW; END IF;
 IF NEW.definition='pmo-change/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_changeclosure cc JOIN documents_publicationreceipt rec ON rec.id=cc.receipt_id JOIN documents_publication p ON p.id=rec.publication_id
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND psl_change_closure_assurance_current(cc))
 THEN RAISE EXCEPTION 'Verified change requires current exact signature or applicability assurance'; END IF;
 RETURN NEW;
END $$;
-- Narrow replacement in the current terminal guard, not a historical migration import.
DO $$ DECLARE body text; target oid; matches integer;
 needle text:='cc.execution_ids=b.execution_ids AND cc.pm_signature_id<>cc.client_signature_id';
BEGIN
 SELECT count(*),min(p.oid::bigint)::oid INTO matches,target FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
 WHERE n.nspname=current_schema() AND p.prokind='f' AND position(needle in p.prosrc)>0;
 IF matches<>1 THEN RAISE EXCEPTION 'Expected one exact existing change terminal guard'; END IF;
 body:=pg_get_functiondef(target);
 IF (length(body)-length(replace(body,needle,'')))/length(needle)<>1 THEN RAISE EXCEPTION 'Change terminal guard marker is ambiguous'; END IF;
 EXECUTE replace(body,needle,'cc.execution_ids=b.execution_ids AND psl_change_assurance_claim(cc,a.result)');
END $$;
CREATE FUNCTION psl_change_signature_applicability_exclusions() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cid uuid; s jsonb;
BEGIN
 SELECT cr.case_id INTO STRICT cid FROM pmo_changeauthorization ca JOIN pmo_changeversion cv ON cv.id=ca.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id WHERE ca.id=NEW.authorization_id;
 PERFORM 1 FROM core_case WHERE id=cid FOR UPDATE;
 IF EXISTS(SELECT 1 FROM pmo_changeclosureapplicability WHERE authorization_id=NEW.authorization_id) THEN RAISE EXCEPTION 'Use applicability successor to retain explicit decision history'; END IF;
 FOR s IN SELECT value FROM jsonb_each(NEW.declaration->'signatures') LOOP
  IF EXISTS(SELECT 1 FROM pmo_changeclosureapplicability a JOIN pmo_changeauthorization ca ON ca.id=a.authorization_id JOIN pmo_changeversion cv ON cv.id=ca.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id WHERE cr.case_id=cid AND ca.id<>NEW.authorization_id AND
   (a.pm_signature_id IN (NEW.pm_signature_id,NEW.client_signature_id) OR a.client_signature_id IN (NEW.pm_signature_id,NEW.client_signature_id)
   OR EXISTS(SELECT 1 FROM jsonb_each(a.declaration->'signatures') prior_sig WHERE prior_sig.value->'source_system'=s->'source_system' AND prior_sig.value->'source_reference'=s->'source_reference' AND prior_sig.value->'decision_id'=s->'decision_id' AND prior_sig.value->'decision_version'=s->'decision_version')))
  THEN RAISE EXCEPTION 'Signature source already belongs to another applicability change'; END IF;
 END LOOP;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_change_signature_applicability_exclusions BEFORE INSERT ON pmo_changeclosuresignaturebinding FOR EACH ROW EXECUTE FUNCTION psl_change_signature_applicability_exclusions();

CREATE FUNCTION psl_change_applicability_followup() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cc pmo_changeclosure;
BEGIN
 SELECT * INTO STRICT cc FROM pmo_changeclosure WHERE id=NEW.closure_id;
 IF (cc.client_signature_id IS NULL OR EXISTS(SELECT 1 FROM pmo_changeclosureapplicability WHERE authorization_id=cc.authorization_id))
 AND psl_change_closure_assurance_current(cc) IS DISTINCT FROM true THEN RAISE EXCEPTION 'Current explicit applicability assurance required for follow-up completion'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_change_applicability_followup BEFORE INSERT ON pmo_emergencyfollowupcompletion FOR EACH ROW EXECUTE FUNCTION psl_change_applicability_followup();

"""

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_append_only_history'),
        ('documents', '0031_template_current_claims'),
        ('pmo', '0049_change_closure_signature_binding'),
        ('finance', '0073_workbook_reference'),
        ('policy', '0016_cash_operation_identity'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='changeclosure',
            name='client_signature',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.evidence'),
        ),
        migrations.CreateModel(
            name='ChangeClosureApplicability',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('requirement', models.CharField(choices=[('required', 'Required'), ('not_applicable', 'Not applicable')], max_length=20)),
                ('execution_ids', models.JSONField()),
                ('declaration', models.JSONField()),
                ('authority', models.JSONField()),
                ('operation_key', models.CharField(max_length=100)),
                ('note', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('authorization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='applicability_records', to='pmo.changeauthorization')),
                ('client_signature', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.evidence')),
                ('legacy_binding', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='pmo.changeclosuresignaturebinding')),
                ('pm_signature', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.evidence')),
                ('policy', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='policy.configuration')),
                ('previous', models.OneToOneField(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='successor', to='pmo.changeclosureapplicability')),
                ('receipt', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='documents.publicationreceipt')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('authorization', 'operation_key'), name='change_applicability_operation'), models.CheckConstraint(condition=models.Q(models.Q(('client_signature__isnull', False), ('requirement', 'required')), models.Q(('client_signature__isnull', True), ('requirement', 'not_applicable')), _connector='OR'), name='change_applicability_variant')],
            },
        ),
        migrations.RunSQL(SQL),  # Irreversible: never delete assurance/signature history.
    ]
