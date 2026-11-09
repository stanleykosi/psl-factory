"""Narrow forward repair: SQL aliases must not collide with trigger OLD records.

0075 is retained byte-for-byte: it was genuinely applied during779a.
Reverse SQL is intentionally a no-op, not a supported reversible downgrade.
"""
from django.db import migrations

FORWARD_SQL = r"""
CREATE OR REPLACE FUNCTION psl_obligation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ns finance_obligationnamespace; cl finance_obligationclaim; i finance_invoice;
 b finance_obligationbinding; k finance_obligationlocalkey; e core_evidence; a finance_obligationalias;
 j finance_invoicejob; marker finance_obligationlegacyattempt; cfg jsonb; valid boolean;
BEGIN
 IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'Obligation identity writes require READ COMMITTED isolation'; END IF;
 IF TG_TABLE_NAME='finance_obligationlegacyattempt' THEN RAISE EXCEPTION 'Legacy attempt registry is frozen at migration'; END IF;
 IF TG_TABLE_NAME='finance_obligationnamespace' THEN
  IF NOT EXISTS(SELECT 1 FROM policy_scopeversion s JOIN policy_configuration p ON p.id=s.configuration_id
   JOIN core_case c ON c.id=p.case_id WHERE s.id=NEW.source_id AND s.kind='organization' AND s.ref=NEW.tenant
   AND c.tenant=NEW.tenant AND c.synthetic=NEW.synthetic AND p.component='D08.obligation_namespace'
   AND psl_obligation_policy(p.id)->>'namespace'=NEW.name AND psl_obligation_policy(p.id)->'key_contract'=NEW.key_contract
   AND (SELECT state FROM policy_scopestate WHERE source_id=s.id ORDER BY id DESC LIMIT 1)='active'
   AND (SELECT state FROM policy_policystate WHERE configuration_id=p.id ORDER BY id DESC LIMIT 1)='validated'
   AND psl_schedules_envelope_current(p.id)
   AND (p.envelope->>'effective_from')::timestamptz<=clock_timestamp()
   AND ((p.envelope->>'effective_until') IS NULL OR (p.envelope->>'effective_until')::timestamptz>clock_timestamp())
   AND EXISTS(SELECT 1 FROM policy_scopestate activated WHERE activated.id=(SELECT max(id) FROM policy_scopestate WHERE source_id=s.id AND state='active')
    AND psl_schedules_grants(c.id,activated.actor_id,ARRAY['case.read','policy.activate']))
   AND NOT EXISTS(SELECT 1 FROM policy_scopeversion newer JOIN policy_configuration newer_config ON newer_config.id=newer.configuration_id
    WHERE newer_config.case_id=c.id AND newer_config.component=p.component AND newer.kind=s.kind AND newer.ref=s.ref AND newer.revision>s.revision
    AND EXISTS(SELECT 1 FROM policy_scopestate activated WHERE activated.source_id=newer.id AND activated.state IN ('active','revoked'))))
  THEN RAISE EXCEPTION 'Explicit organisation namespace source required'; END IF;
  RETURN NEW;
 END IF;
 IF TG_TABLE_NAME IN ('finance_obligationclaim','finance_obligationalias') THEN
  SELECT * INTO ns FROM finance_obligationnamespace WHERE id=NEW.namespace_id FOR UPDATE;
  SELECT * INTO e FROM core_evidence WHERE id=NEW.evidence_id;
  IF NOT EXISTS(SELECT 1 FROM core_case c WHERE c.id=NEW.case_id AND c.tenant=ns.tenant AND c.synthetic=ns.synthetic)
   OR e.case_id IS DISTINCT FROM NEW.case_id OR NEW.key !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'
  THEN RAISE EXCEPTION 'Exact namespace, case and identity evidence required'; END IF;
  IF TG_TABLE_NAME='finance_obligationclaim' THEN
   SELECT * INTO i FROM finance_invoice WHERE id=(e.body::jsonb->>'invoice_id')::bigint;
   IF e.kind IS DISTINCT FROM 'invoice_identity' OR i.case_id IS DISTINCT FROM NEW.case_id
    OR e.body::jsonb->>'key' IS DISTINCT FROM NEW.key OR e.body::jsonb->>'namespace' IS DISTINCT FROM ns.name
    OR e.body::jsonb->>'invoice_sha256' IS DISTINCT FROM i.sha256
    OR NOT psl_schedules_grants(NEW.case_id,NEW.actor_id,ARRAY['case.read','finance.read','finance.invoice.draft'])
    OR NOT EXISTS(SELECT 1 FROM policy_configuration config WHERE config.case_id=NEW.case_id
     AND config.component='D08.obligation_namespace' AND psl_obligation_namespace_policy(ns.id,config.id,NEW.case_id))
    OR EXISTS(SELECT 1 FROM finance_obligationalias WHERE namespace_id=ns.id AND key=NEW.key)
   THEN RAISE EXCEPTION 'Exact canonical identity evidence required; existing identities cannot be reassigned'; END IF;
  ELSE
   SELECT * INTO cl FROM finance_obligationclaim WHERE id=NEW.claim_id;
   cfg:=psl_obligation_policy(NEW.policy_id);
   IF cl.namespace_id IS DISTINCT FROM ns.id OR e.kind IS DISTINCT FROM 'invoice_identity_alias'
    OR NEW.version<>COALESCE((SELECT max(version) FROM finance_obligationalias WHERE namespace_id=ns.id AND key=NEW.key),0)+1
    OR EXISTS(SELECT 1 FROM finance_obligationalias WHERE namespace_id=ns.id AND key=NEW.key AND claim_id<>cl.id)
    OR NOT psl_obligation_namespace_policy(ns.id,NEW.policy_id,NEW.case_id)
    OR NOT psl_schedules_grants(NEW.case_id,NEW.actor_id,ARRAY['case.read','finance.read','finance.invoice.review'])
    OR NOT psl_schedules_grants(cl.case_id,NEW.actor_id,ARRAY['case.read','finance.read'])
    OR NOT (cfg->'resolver_ids' @> to_jsonb(NEW.actor_id))
    OR NOT psl_schedules_role_current(NEW.case_id,NEW.actor_id,NEW.authority,cfg->>'resolver_role')
    OR NOT psl_schedules_authority_current(NEW.case_id,NEW.authority)
    OR e.body::jsonb IS DISTINCT FROM jsonb_build_object('namespace',ns.name,'key',NEW.key,
      'canonical_claim_id',cl.id,'canonical_key',cl.key,'canonical_case_id',cl.case_id::text)
    OR EXISTS(SELECT 1 FROM finance_obligationclaim WHERE namespace_id=ns.id AND key=NEW.key)
   THEN RAISE EXCEPTION 'Exact accessible configured alias resolution required; claims cannot merge'; END IF;
  END IF;
  RETURN NEW;
 END IF;
 IF TG_TABLE_NAME='finance_obligationlocalkey' THEN
  SELECT * INTO cl FROM finance_obligationclaim WHERE id=NEW.claim_id;
  IF cl.case_id IS DISTINCT FROM NEW.case_id OR NEW.legacy_key !~ '^[a-f0-9]{64}$'
  THEN RAISE EXCEPTION 'Canonical claim ownership must match local identity'; END IF;
  RETURN NEW;
 END IF;
 IF TG_TABLE_NAME='finance_obligationbinding' THEN
  SELECT * INTO i FROM finance_invoice WHERE id=NEW.invoice_id;
  SELECT * INTO k FROM finance_obligationlocalkey WHERE id=NEW.local_key_id;
  SELECT * INTO cl FROM finance_obligationclaim WHERE id=k.claim_id;
  SELECT * INTO ns FROM finance_obligationnamespace WHERE id=cl.namespace_id FOR UPDATE;
  SELECT * INTO e FROM core_evidence WHERE id=NEW.evidence_id;
  SELECT * INTO a FROM finance_obligationalias WHERE id=NEW.alias_id;
  IF i.case_id IS DISTINCT FROM k.case_id OR i.obligation_key IS DISTINCT FROM k.legacy_key
   OR e.case_id IS DISTINCT FROM i.case_id OR e.kind IS DISTINCT FROM 'invoice_identity'
   OR NOT psl_obligation_namespace_policy(ns.id,NEW.policy_id,i.case_id)
   OR NOT psl_schedules_grants(i.case_id,NEW.actor_id,ARRAY['case.read','finance.read','finance.invoice.draft'])
   OR (NEW.alias_id IS NOT NULL AND (a.claim_id IS DISTINCT FROM cl.id OR a.namespace_id IS DISTINCT FROM ns.id
     OR a.id IS DISTINCT FROM (SELECT id FROM finance_obligationalias WHERE namespace_id=a.namespace_id AND key=a.key ORDER BY version DESC LIMIT 1)
     OR NOT psl_obligation_namespace_policy(ns.id,a.policy_id,a.case_id)
     OR NOT psl_schedules_grants(a.case_id,a.actor_id,ARRAY['case.read','finance.read','finance.invoice.review'])
     OR NOT psl_schedules_grants(cl.case_id,a.actor_id,ARRAY['case.read','finance.read'])
     OR NOT (psl_obligation_policy(a.policy_id)->'resolver_ids' @> to_jsonb(a.actor_id))
     OR NOT psl_schedules_role_current(a.case_id,a.actor_id,a.authority,psl_obligation_policy(a.policy_id)->>'resolver_role')
     OR NOT psl_schedules_authority_current(a.case_id,a.authority)))
   OR e.body::jsonb IS DISTINCT FROM jsonb_build_object('invoice_id',i.id,'invoice_sha256',i.sha256,
    'preparation_id',i.preparation_id,'legacy_key',i.obligation_key,'namespace',ns.name,
    'key',COALESCE(a.key,cl.key),'predecessor_binding_id',NEW.predecessor_id)
   OR (NEW.predecessor_id IS NULL AND EXISTS(SELECT 1 FROM finance_obligationbinding prior_record
    JOIN finance_obligationlocalkey oldkey ON oldkey.id=prior_record.local_key_id
    WHERE oldkey.claim_id=cl.id AND oldkey.id<>k.id))
   OR (NEW.predecessor_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_obligationbinding prior_record
    JOIN finance_obligationlocalkey oldkey ON oldkey.id=prior_record.local_key_id
    WHERE prior_record.id=NEW.predecessor_id AND oldkey.claim_id=cl.id AND oldkey.case_id=i.case_id))
  THEN RAISE EXCEPTION 'Exact current canonical identity binding required'; END IF;
  RETURN NEW;
 END IF;
 IF TG_TABLE_NAME='finance_obligationeffect' THEN
  SELECT * INTO j FROM finance_invoicejob WHERE id=NEW.job_id;
  SELECT * INTO b FROM finance_obligationbinding WHERE id=NEW.binding_id;
  SELECT * INTO k FROM finance_obligationlocalkey WHERE id=b.local_key_id;
  PERFORM 1 FROM finance_obligationclaim WHERE id=k.claim_id FOR UPDATE;
  IF j.kind IS DISTINCT FROM 'issue' OR j.invoice_id IS DISTINCT FROM NEW.invoice_id OR b.invoice_id IS DISTINCT FROM NEW.invoice_id
   OR k.claim_id IS DISTINCT FROM NEW.claim_id OR j.intent->'obligation_identity' IS DISTINCT FROM psl_obligation_pin(b.id)
   OR j.attempts<1 OR j.status IS DISTINCT FROM 'leased'
   OR NOT psl_obligation_binding_current(b.id)
  THEN RAISE EXCEPTION 'Exact attempted canonical effect required'; END IF;
  RETURN NEW;
 END IF;
 IF TG_TABLE_NAME='finance_obligationlegacyobservation' THEN
  SELECT * INTO marker FROM finance_obligationlegacyattempt WHERE id=NEW.attempt_id;
  SELECT * INTO j FROM finance_invoicejob WHERE id=marker.job_id;
  SELECT * INTO i FROM finance_invoice WHERE id=j.invoice_id;
  IF NOT (SELECT synthetic FROM core_case WHERE id=i.case_id) OR j.kind IS DISTINCT FROM 'issue'
   OR j.intent IS DISTINCT FROM marker.snapshot->'intent' OR j.operation_key IS DISTINCT FROM marker.snapshot->>'operation_key'
   OR i.id IS DISTINCT FROM (marker.snapshot->>'invoice')::bigint OR i.payload IS DISTINCT FROM marker.snapshot->'payload'
   OR i.sha256 IS DISTINCT FROM marker.snapshot->>'sha256' OR j.actor_id IS DISTINCT FROM (marker.snapshot->>'actor')::bigint
   OR j.attempts<(marker.snapshot->>'attempts')::int OR j.fence<>NEW.fence OR j.status<>'leased'
   OR NEW.proof IS DISTINCT FROM jsonb_build_object('environment','synthetic_mock','operation_key',j.operation_key,
    'payload',i.payload,'destination',j.intent->'adapter'->'recipient_id',
    'fingerprint',psl_usage_hash(jsonb_build_object('payload',i.payload,'destination',j.intent->'adapter'->'recipient_id','target',i.id,'intent',j.intent)))
  THEN RAISE EXCEPTION 'Exact frozen original synthetic proof required'; END IF;
  RETURN NEW;
 END IF;
 RAISE EXCEPTION 'Unsupported obligation identity record';
END $$;
CREATE OR REPLACE FUNCTION psl_obligation_invoice_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE b finance_obligationbinding; k finance_obligationlocalkey; cl finance_obligationclaim; j finance_invoicejob; i finance_invoice;
BEGIN
 IF TG_TABLE_NAME='finance_invoiceissue' THEN
  IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'Obligation issue transitions require READ COMMITTED isolation'; END IF;
 ELSIF NEW.kind='issue' THEN
  IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'Obligation issue transitions require READ COMMITTED isolation'; END IF;
 END IF;
 IF TG_TABLE_NAME='finance_invoicejob' THEN
  IF TG_OP='UPDATE' THEN
   IF ROW(NEW.invoice_id,NEW.kind,NEW.generation,NEW.operation_key,NEW.actor_id,NEW.intent)
      IS DISTINCT FROM ROW(OLD.invoice_id,OLD.kind,OLD.generation,OLD.operation_key,OLD.actor_id,OLD.intent)
   THEN RAISE EXCEPTION 'Original invoice request identity is immutable; reconcile before explicit successor'; END IF;
   IF NEW.fence<OLD.fence THEN RAISE EXCEPTION 'Invoice attempt fence is monotonic'; END IF;
   RETURN NEW;
  END IF;
  IF NEW.kind<>'issue' THEN RETURN NEW; END IF;
  SELECT * INTO b FROM finance_obligationbinding WHERE id=(NEW.intent->'obligation_identity'->>'binding')::bigint;
  SELECT * INTO k FROM finance_obligationlocalkey WHERE id=b.local_key_id;
  SELECT * INTO cl FROM finance_obligationclaim WHERE id=k.claim_id FOR UPDATE;
  SELECT * INTO i FROM finance_invoice WHERE id=NEW.invoice_id;
  IF b.id IS NULL OR b.invoice_id IS DISTINCT FROM NEW.invoice_id OR NEW.intent->'obligation_identity' IS DISTINCT FROM psl_obligation_pin(b.id)
   OR b.id IS DISTINCT FROM (SELECT id FROM finance_obligationbinding WHERE invoice_id=i.id ORDER BY id DESC LIMIT 1)
   OR NOT psl_obligation_binding_current(b.id)
   OR NOT psl_schedules_grants(i.case_id,NEW.actor_id,ARRAY['finance.invoice.issue'])
   OR EXISTS(SELECT 1 FROM finance_obligationlegacyattempt marker
    JOIN finance_invoicejob attempted ON attempted.id=marker.job_id
    JOIN finance_invoice original ON original.id=attempted.invoice_id
    JOIN finance_obligationlocalkey lk ON lk.case_id=original.case_id AND lk.legacy_key=original.obligation_key
    WHERE lk.claim_id=cl.id AND NOT EXISTS(SELECT 1 FROM finance_invoiceissue proof WHERE proof.invoice_id=original.id))
   OR EXISTS(SELECT 1 FROM finance_obligationeffect WHERE claim_id=cl.id)
   OR EXISTS(SELECT 1 FROM finance_invoicejob other WHERE other.kind='issue' AND other.invoice_id<>i.id
    AND other.intent->'obligation_identity'->>'claim'=cl.id::text AND (other.status NOT IN ('cancelled','replaced') OR other.attempts>0))
   OR EXISTS(SELECT 1 FROM finance_invoiceissue ii JOIN finance_obligationbinding prior_record ON prior_record.invoice_id=ii.invoice_id
    JOIN finance_obligationlocalkey ok ON ok.id=prior_record.local_key_id WHERE ok.claim_id=cl.id AND ii.invoice_id<>i.id)
  THEN RAISE EXCEPTION 'Exact current unconflicted identity required before new invoice reservation'; END IF;
 ELSE
  SELECT * INTO j FROM finance_invoicejob WHERE id=NEW.job_id;
  SELECT * INTO i FROM finance_invoice WHERE id=NEW.invoice_id;
  IF j.kind IS DISTINCT FROM 'issue' OR j.invoice_id IS DISTINCT FROM i.id OR NEW.payload IS DISTINCT FROM i.payload
   OR NEW.sha256 IS DISTINCT FROM i.sha256 OR NEW.obligation_key IS DISTINCT FROM i.obligation_key
   OR NEW.operation_key IS DISTINCT FROM 'obligation:'||i.obligation_key
  THEN RAISE EXCEPTION 'Exact reserved invoice receipt required'; END IF;
  IF j.intent ? 'obligation_identity' THEN
   IF NOT EXISTS(SELECT 1 FROM finance_obligationeffect fx WHERE fx.invoice_id=i.id AND fx.job_id=j.id
    AND fx.claim_id=(j.intent->'obligation_identity'->>'claim')::bigint)
    OR j.intent->'obligation_identity' IS DISTINCT FROM psl_obligation_pin((j.intent->'obligation_identity'->>'binding')::bigint)
   THEN RAISE EXCEPTION 'Exact permanent canonical effect receipt required'; END IF;
  ELSIF NOT EXISTS(SELECT 1 FROM finance_obligationlegacyattempt prior_record JOIN finance_obligationlegacyobservation obs ON obs.attempt_id=prior_record.id
   WHERE prior_record.job_id=j.id AND prior_record.snapshot->'intent'=j.intent AND prior_record.snapshot->'payload'=NEW.payload
   AND prior_record.snapshot->>'operation_key'=j.operation_key AND prior_record.snapshot->>'sha256'=NEW.sha256) THEN
   RAISE EXCEPTION 'Unbound legacy invoice requires frozen original-effect proof; no new issuance is allowed';
  END IF;
 END IF;
 RETURN NEW;
END $$;
"""

class Migration(migrations.Migration):
    dependencies = [('finance', '0075_cross_case_obligation_identity')]
    operations = [migrations.RunSQL(FORWARD_SQL, migrations.RunSQL.noop)]
