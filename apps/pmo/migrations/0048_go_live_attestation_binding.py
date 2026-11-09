"""Exact P33 purpose/subject/time declarations and serialised signature reuse.

No data rewrite, new record kind or external-authenticity claim. Irreversible:
removing this safety guard is not a supported rollback of already bound facts.
"""
from importlib import import_module
import hashlib
from django.db import migrations

OLD = import_module('apps.pmo.migrations.0042_go_live_reaffirmation').SQL
OLD_FUNCTION = OLD[:OLD.index('CREATE TRIGGER')]
assert hashlib.sha256(OLD_FUNCTION.encode()).hexdigest()=='0b8f616cd57bf581c027b037a3743b91ed5b2e1d198358fe866295f93773e4e9'
OLD_BODY = OLD_FUNCTION.split(' AS $$',1)[1].rsplit('$$;',1)[0]
REPLACEMENTS = [('CREATE FUNCTION psl_go_live_reaffirmation()', 'CREATE OR REPLACE FUNCTION psl_go_live_reaffirmation()'), ("OR NEW.data-ARRAY['receipt_id','pm_signature_id','client_signature_id','note','previous_acceptance_id','authority']<>'{}'::jsonb", "OR NEW.data-ARRAY['receipt_id','pm_signature_id','client_signature_id','note','previous_acceptance_id','authority','attestation','mode']<>'{}'::jsonb"), ('IF EXISTS(SELECT 1 FROM pmo_deliveryrecord used', "IF NEW.data->>'mode'<>'metadata_binding' AND EXISTS(SELECT 1 FROM pmo_deliveryrecord used")]
REVISED_FUNCTION = OLD_FUNCTION
for old,new in REPLACEMENTS:
    assert REVISED_FUNCTION.count(old)==1,old
    REVISED_FUNCTION=REVISED_FUNCTION.replace(old,new)

ASSERT_PREDECESSOR = """
DO $assert0042$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
  JOIN pg_language l ON l.oid=p.prolang WHERE n.nspname='public'
   AND p.proname='psl_go_live_reaffirmation' AND p.pronargs=0 AND p.prorettype='trigger'::regtype
   AND p.provolatile='v' AND l.lanname='plpgsql' AND p.prosrc=$old0042$"""+OLD_BODY+"""$old0042$)
 THEN RAISE EXCEPTION 'Actual0048 requires the exact unchanged accepted0042 reaffirmation body'; END IF;
END $assert0042$;
"""

TYPED_SQL = r"""
-- Immutable0048 typed go-live binding; no backfill or new record kind.
CREATE FUNCTION psl_gl_keys(v jsonb, keys text[]) RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
 SELECT jsonb_typeof(v)='object' AND v ?& keys AND v-keys='{}'::jsonb;
$$;
CREATE FUNCTION psl_gl_integer(v jsonb) RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
 SELECT jsonb_typeof(v)='number' AND v::text ~ '^[1-9][0-9]{0,18}$' AND (v::text)::numeric<=9223372036854775807;
$$;
CREATE FUNCTION psl_gl_attestation(r pmo_deliveryrecord) RETURNS boolean LANGUAGE plpgsql VOLATILE AS $$
DECLARE a jsonb:=r.data->'attestation'; d pmo_deliverydossier; c pmo_deliverycandidate;
 req core_evidence; rel pmo_deliveryrecord; rec documents_publicationreceipt;
 v documents_version; b pmo_deliverydocumentbinding; old pmo_deliveryrecord;
 s jsonb; e core_evidence; role text; k text; mode text:=COALESCE(r.data->>'mode','fresh_signatures');
 allowed bigint[]:=ARRAY[r.id]; previous_id bigint; released timestamptz; signed timestamptz;
BEGIN
 IF r.kind NOT IN ('go_live','go_live_reaffirmation') OR a IS NULL THEN RETURN false; END IF;
 IF NOT psl_gl_keys(r.data,CASE WHEN r.kind='go_live' THEN
  ARRAY['receipt_id','pm_signature_id','client_signature_id','note','authority','attestation'] ELSE
  ARRAY['receipt_id','pm_signature_id','client_signature_id','note','authority','attestation','mode','previous_acceptance_id'] END)
  OR jsonb_typeof(r.data->'note')<>'string' OR length(btrim(r.data->>'note')) NOT BETWEEN 1 AND 4000
  OR NOT psl_gl_keys(a,ARRAY['protocol','purpose','case_id','dossier_id','candidate','release','report','signatures','attesting_actor_id'])
  OR a->>'protocol'<>'go-live-attestation/v1' OR a->>'purpose'<>'go_live_business_acceptance'
  OR NOT psl_gl_keys(a->'signatures',ARRAY['PM','Client']) OR mode NOT IN ('fresh_signatures','metadata_binding')
 THEN RETURN false; END IF;
 FOREACH k IN ARRAY ARRAY['receipt_id','pm_signature_id','client_signature_id'] LOOP
  IF NOT psl_gl_integer(r.data->k) THEN RETURN false; END IF;
 END LOOP;
 FOREACH k IN ARRAY ARRAY['dossier_id','attesting_actor_id'] LOOP
  IF NOT psl_gl_integer(a->k) THEN RETURN false; END IF;
 END LOOP;
 IF NOT psl_gl_integer(a->'candidate'->'id') OR NOT psl_gl_integer(a->'release'->'id')
  OR NOT psl_gl_integer(a->'candidate'->'requirements'->'id') OR NOT psl_gl_integer(a->'candidate'->'requirements'->'version') THEN RETURN false; END IF;
 FOREACH k IN ARRAY ARRAY['document_id','version_id','number','receipt_id'] LOOP
  IF NOT psl_gl_integer(a->'report'->k) THEN RETURN false; END IF;
 END LOOP;
 SELECT * INTO STRICT d FROM pmo_deliverydossier WHERE id=r.dossier_id;
 SELECT * INTO STRICT c FROM pmo_deliverycandidate WHERE id=d.candidate_id AND case_id=d.case_id;
 SELECT * INTO STRICT req FROM core_evidence WHERE id=c.requirements_id AND case_id=d.case_id;
 SELECT * INTO STRICT rel FROM pmo_deliveryrecord WHERE dossier_id=d.id AND kind='release_outcome';
 SELECT rr.* INTO STRICT rec FROM documents_publicationreceipt rr WHERE rr.id=(r.data->>'receipt_id')::bigint;
 SELECT vv.* INTO STRICT v FROM documents_version vv JOIN documents_publication p ON p.version_id=vv.id WHERE p.id=rec.publication_id;
 SELECT * INTO STRICT b FROM pmo_deliverydocumentbinding WHERE version_id=v.id AND dossier_id=d.id AND purpose='go_live';
 IF a->'case_id'<>to_jsonb(d.case_id::text) OR a->'dossier_id'<>to_jsonb(d.id) OR a->'attesting_actor_id'<>to_jsonb(r.actor_id)
  OR a->'candidate'<>jsonb_build_object('id',c.id,'reference',c.reference,'requirements',jsonb_build_object('id',req.id,'version',req.version,'sha256',req.sha256))
  OR a->'release'<>jsonb_build_object('id',rel.id,'external_ref',rel.data->'external_ref','released_at',rel.data->'released_at')
  OR a->'report'<>jsonb_build_object('document_id',v.document_id,'version_id',v.id,'number',v.number,'payload_sha256',v.payload_sha256,'receipt_id',rec.id)
  OR b.snapshot<>r.snapshot OR r.snapshot->>'outcome_id'<>rel.id::text OR v.audience<>'client'
  OR rec.payload_sha256<>v.payload_sha256 OR rec.payload<>v.payload
  OR NOT EXISTS(SELECT 1 FROM documents_document dd WHERE dd.id=v.document_id AND dd.case_id=d.case_id AND dd.current_id=v.id)
  OR NOT psl_schedules_grants(d.case_id,r.actor_id,ARRAY['case.read','delivery.manage'])
  OR NOT psl_schedules_authority_current(d.case_id,r.data->'authority')
  OR NOT psl_schedules_role_current(d.case_id,r.actor_id,r.data->'authority','PM')
 THEN RETURN false; END IF;
 IF r.kind='go_live' THEN
  IF r.parent_id IS DISTINCT FROM rel.id OR NOT psl_gl_keys(r.data->'authority',ARRAY['D05.role_principal_assignments']) THEN RETURN false; END IF;
 ELSE
  IF NOT psl_gl_keys(r.data->'authority',ARRAY['D05.role_principal_assignments','D05.decision_action_matrix'])
   OR NOT psl_schedules_policy_current(d.case_id,(r.data->'authority'->>'D05.decision_action_matrix')::bigint)
   OR NOT EXISTS(SELECT 1 FROM psl_reporting_refs((r.data->'authority'->>'D05.decision_action_matrix')::bigint) ref,
       LATERAL jsonb_array_elements(ref->'rules') rule WHERE rule->>'role'='PM' AND rule->'actions' ? 'reaffirm_go_live')
  THEN RETURN false; END IF;
  SELECT * INTO STRICT old FROM pmo_deliveryrecord WHERE id=r.parent_id AND dossier_id=d.id AND kind IN ('go_live','go_live_reaffirmation');
  IF r.data->'previous_acceptance_id'<>to_jsonb(old.id) OR r.id<=old.id OR r.created_at<old.created_at
   OR EXISTS(SELECT 1 FROM pmo_deliveryrecord later WHERE later.dossier_id=d.id AND later.kind IN ('go_live','go_live_reaffirmation') AND later.id>old.id AND later.id<r.id)
  THEN RETURN false; END IF;
 END IF;
 IF EXISTS(SELECT 1 FROM pmo_deliveryrecord closed WHERE closed.dossier_id=d.id AND closed.kind='closure' AND closed.id<r.id) THEN RETURN false; END IF;
 IF mode='metadata_binding' THEN
  IF r.kind<>'go_live_reaffirmation' OR (old.data->'receipt_id') IS DISTINCT FROM (r.data->'receipt_id')
   OR (old.data->'pm_signature_id') IS DISTINCT FROM (r.data->'pm_signature_id')
   OR (old.data->'client_signature_id') IS DISTINCT FROM (r.data->'client_signature_id') OR old.snapshot<>r.snapshot
   OR (old.data ? 'attestation' AND ((old.data->'attestation')-'attesting_actor_id')<>(a-'attesting_actor_id')) THEN RETURN false; END IF;
  IF EXISTS(SELECT 1 FROM jsonb_each(a->'signatures') sig WHERE (sig.value->>'signed_at')::timestamptz>old.created_at) THEN RETURN false; END IF;
  previous_id:=old.id;
  WHILE previous_id IS NOT NULL LOOP
   SELECT * INTO STRICT old FROM pmo_deliveryrecord WHERE id=previous_id;
   EXIT WHEN old.kind NOT IN ('go_live','go_live_reaffirmation');
   allowed:=array_append(allowed,old.id); previous_id:=old.parent_id;
  END LOOP;
 END IF;
 released:=(a->'release'->>'released_at')::timestamptz;
 FOREACH role IN ARRAY ARRAY['PM','Client'] LOOP
  s:=a->'signatures'->role;
  IF NOT psl_gl_keys(s,ARRAY['evidence','source_system','source_reference','decision_id','decision_version','signer_reference','purpose','signed_at'])
   OR s->>'purpose'<>'go_live_business_acceptance' THEN RETURN false; END IF;
  FOREACH k IN ARRAY ARRAY['source_system','source_reference','decision_id','decision_version','signer_reference'] LOOP
   IF jsonb_typeof(s->k)<>'string' OR (s->>k)!~'^[A-Za-z0-9][A-Za-z0-9._:/@+ -]{0,239}$' OR btrim(s->>k)<>s->>k THEN RETURN false; END IF;
  END LOOP;
  IF jsonb_typeof(s->'signed_at')<>'string' OR (s->>'signed_at')!~'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$' THEN RETURN false; END IF;
  signed:=(s->>'signed_at')::timestamptz;
  IF signed<=released OR signed>statement_timestamp() THEN RETURN false; END IF;
  IF NOT psl_gl_integer(s->'evidence'->'id') OR NOT psl_gl_integer(s->'evidence'->'version') THEN RETURN false; END IF;
  SELECT * INTO STRICT e FROM core_evidence WHERE id=(r.data->>(CASE role WHEN 'PM' THEN 'pm_signature_id' ELSE 'client_signature_id' END))::bigint AND case_id=d.case_id AND kind='signature';
  IF s->'evidence'<>jsonb_build_object('id',e.id,'version',e.version,'sha256',e.sha256)
   OR EXISTS(SELECT 1 FROM pmo_gaterecord g WHERE g.evidence_id=e.id AND g.kind IN ('uat_product_manager','uat_product_owner','uat_client'))
   OR EXISTS(SELECT 1 FROM pmo_deliveryrecord used JOIN pmo_deliverydossier dd ON dd.id=used.dossier_id
       WHERE dd.case_id=d.case_id AND used.kind IN ('go_live','go_live_reaffirmation') AND NOT (used.id=ANY(allowed))
       AND (used.data->>'pm_signature_id'=e.id::text OR used.data->>'client_signature_id'=e.id::text
        OR EXISTS(SELECT 1 FROM jsonb_each(used.data->'attestation'->'signatures') sig WHERE
          sig.value->'source_system'=s->'source_system' AND sig.value->'source_reference'=s->'source_reference'
          AND sig.value->'decision_id'=s->'decision_id' AND sig.value->'decision_version'=s->'decision_version')))
  THEN RETURN false; END IF;
 END LOOP;
 RETURN r.evidence_id=(r.data->>'pm_signature_id')::bigint AND r.data->>'pm_signature_id'<>r.data->>'client_signature_id';
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;
CREATE FUNCTION psl_gl_attestation_insert() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NEW.kind NOT IN ('go_live','go_live_reaffirmation') THEN RETURN NEW; END IF;
 -- The case lock covers evidence/decision reuse across dossiers. A volatile
 -- predicate takes a fresh command snapshot after a competing insert commits.
 -- Nondefault snapshot isolation cannot refresh that view and fails closed.
 IF current_setting('transaction_isolation')<>'read committed'
 THEN RAISE EXCEPTION 'Go-live attestation inserts require READ COMMITTED transaction isolation'; END IF;
 PERFORM 1 FROM core_case c JOIN pmo_deliverydossier d ON d.case_id=c.id
  WHERE d.id=NEW.dossier_id FOR UPDATE OF c;
 IF NOT psl_gl_attestation(NEW)
 THEN RAISE EXCEPTION 'Exact typed post-release go-live attestation required; UAT and legacy unbound evidence are not acceptance'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_gl_attestation_insert BEFORE INSERT ON pmo_deliveryrecord FOR EACH ROW EXECUTE FUNCTION psl_gl_attestation_insert();
CREATE FUNCTION psl_gl_verified_factory() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='UPDATE' AND OLD.status='verified' AND NEW.status='verified' AND NEW.source_head_id IS NOT DISTINCT FROM OLD.source_head_id AND NEW.request=OLD.request THEN RETURN NEW; END IF;
 IF NEW.definition IN ('delivery-go-live/v1','delivery-hypercare/v1','delivery-archive/v1','delivery-handover/v1','delivery-closure/v1') AND NEW.status='verified'
  AND NOT EXISTS(SELECT 1 FROM pmo_deliveryrecord r WHERE r.dossier_id=(NEW.request->>'dossier')::bigint
   AND r.id=(SELECT max(head.id) FROM pmo_deliveryrecord head WHERE head.dossier_id=r.dossier_id AND head.kind IN ('go_live','go_live_reaffirmation'))
   AND psl_gl_attestation(r))
 THEN RAISE EXCEPTION 'Verified delivery transition requires current typed go-live attestation'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_gl_verified_factory BEFORE INSERT OR UPDATE ON workflows_factorywork FOR EACH ROW EXECUTE FUNCTION psl_gl_verified_factory();
"""
SQL = ASSERT_PREDECESSOR + TYPED_SQL + REVISED_FUNCTION

class Migration(migrations.Migration):
    dependencies=[('pmo','0047_ui_artifact_binding')]
    operations=[migrations.RunSQL(SQL)]
