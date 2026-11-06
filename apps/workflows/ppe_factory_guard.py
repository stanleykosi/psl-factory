"""Additive PPE guard generator. Used by migration and explicitly labelled disposable diagnostics."""
FUNCTIONS=r"""
CREATE OR REPLACE FUNCTION psl_ppe_policy_current(cid uuid, pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c WHERE c.id=pid AND c.case_id=cid
  AND (SELECT state FROM policy_policystate WHERE configuration_id=c.id ORDER BY id DESC LIMIT 1)='active'
  AND (c.envelope->>'effective_from')::timestamptz<=CURRENT_TIMESTAMP
  AND (c.envelope->>'effective_until' IS NULL OR (c.envelope->>'effective_until')::timestamptz>CURRENT_TIMESTAMP));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_grants(cid uuid, uid bigint, actions text[]) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM auth_user WHERE id=uid AND is_active)
  AND NOT EXISTS(SELECT 1 FROM unnest(actions) required(action_name) WHERE NOT EXISTS(
   SELECT 1 FROM identity_grant g WHERE g.case_id=cid AND g.user_id=uid AND g.action=required.action_name AND g.active));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_authority_current(cid uuid, authority jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT NOT EXISTS(SELECT 1 FROM jsonb_each(authority) pin WHERE jsonb_typeof(pin.value)='number'
  AND pin.key<>'D05.decision_action_matrix' AND NOT psl_ppe_policy_current(cid,(pin.value::text)::bigint));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_role_current(cid uuid, uid bigint, authority jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c
  CROSS JOIN LATERAL jsonb_array_elements_text(c.envelope->'value') selection(ref)
  JOIN policy_registeredreference r ON r.case_id=c.case_id AND r.ref=selection.ref AND r.version=1
  WHERE c.id=(authority->>'D05.role_principal_assignments')::bigint AND psl_ppe_policy_current(cid,c.id)
   AND r.content->>'user_id'=uid::text AND r.content->>'role'='Finance'
   AND (NOT r.content ? 'eligibility' OR
    ((r.content->'eligibility'->>'valid_from')::timestamptz<=CURRENT_TIMESTAMP
     AND (r.content->'eligibility'->>'valid_until')::timestamptz>CURRENT_TIMESTAMP)));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_finance_review_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_financereview r WHERE r.id=rid AND r.verdict='approve'
  AND psl_ppe_grants(r.case_id,r.actor_id,ARRAY['finance.review'])
  AND psl_ppe_authority_current(r.case_id,r.authority)
  AND psl_ppe_role_current(r.case_id,r.actor_id,r.authority)
  AND EXISTS(SELECT 1 FROM policy_configuration c JOIN policy_registeredreference ref
   ON ref.case_id=c.case_id AND ref.ref=c.envelope->'value'->>'artifact_ref'
    AND ref.version=(c.envelope->'value'->>'artifact_version')::integer AND ref.sha256=c.envelope->'value'->>'sha256'
   WHERE c.case_id=r.case_id AND c.component='D05.decision_action_matrix' AND psl_ppe_policy_current(r.case_id,c.id)
    AND ref.content->'finance' @> jsonb_build_array(r.authority->'finance_review_rule'))
  AND r.id=(SELECT max(x.id) FROM finance_financereview x WHERE x.case_id=r.case_id AND x.purpose=r.purpose
   AND x.source_id IS NOT DISTINCT FROM r.source_id AND x.configuration_id IS NOT DISTINCT FROM r.configuration_id
   AND x.adjustment_id IS NOT DISTINCT FROM r.adjustment_id AND x.run_id IS NOT DISTINCT FROM r.run_id));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_mapping_current(nid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_financerun n JOIN finance_financesource src ON src.id=n.source_id
  WHERE n.id=nid AND n.kind='mapping' AND n.result->>'status'='complete' AND src.completeness='complete'
   AND psl_ppe_grants(n.case_id,n.actor_id,ARRAY['case.read','finance.read','finance.calculate'])
   AND psl_ppe_finance_review_current((n.snapshot->'source_review'->>'id')::bigint)
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(n.snapshot->'policies') pin
    WHERE pin.value->>'status'<>'ACTIVE' OR NOT psl_ppe_policy_current(n.case_id,(pin.value->>'id')::bigint))
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(n.snapshot->'reviews') pin
    WHERE pin.value->'valid'<>'true'::jsonb OR NOT psl_ppe_finance_review_current((pin.value->>'id')::bigint))
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(n.snapshot->'adjustments') pin
    WHERE NOT psl_ppe_finance_review_current((pin->'review'->>'id')::bigint)
     OR EXISTS(SELECT 1 FROM finance_financeadjustment old JOIN finance_financeadjustment newer
      ON newer.source_id=old.source_id AND newer.reference=old.reference AND newer.number>old.number
      WHERE old.id=(pin->>'id')::bigint)));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_review_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_schedulereview r JOIN finance_schedulework w ON w.id=r.work_id
  WHERE r.id=rid AND r.verdict='approve' AND r.snapshot=w.snapshot
   AND psl_ppe_grants(w.case_id,r.actor_id,ARRAY['case.read','finance.read','ppe.read','ppe.review'])
   AND psl_ppe_authority_current(w.case_id,r.authority)
   AND psl_ppe_role_current(w.case_id,r.actor_id,r.authority)
   AND r.id=(SELECT max(x.id) FROM finance_schedulereview x WHERE x.work_id=w.id AND x.authority->>'purpose'=r.authority->>'purpose'));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_schedule_current(sid bigint, depth integer DEFAULT 0) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE s finance_schedulework; r finance_schedulework; basis bigint; prior_id bigint; pin jsonb;
BEGIN
 IF depth>36 THEN RETURN false; END IF;
 SELECT * INTO s FROM finance_schedulework WHERE id=sid AND kind='ppe_schedule';
 IF NOT FOUND OR s.result->>'status'<>'ready' THEN RETURN false; END IF;
 SELECT * INTO r FROM finance_schedulework WHERE id=(s.payload->>'register_id')::bigint AND case_id=s.case_id AND kind='ppe_register';
 IF NOT FOUND THEN RETURN false; END IF;
 IF NOT psl_ppe_grants(s.case_id,s.actor_id,ARRAY['case.read','finance.read','ppe.read','ppe.prepare'])
  OR NOT psl_ppe_grants(r.case_id,r.actor_id,ARRAY['case.read','finance.read','ppe.read','ppe.capture'])
  OR NOT psl_ppe_review_current((s.snapshot->>'register_review')::bigint)
  OR s.snapshot->'register'<>jsonb_build_array(r.id,r.sha256)
  OR EXISTS(SELECT 1 FROM finance_schedulework newer WHERE newer.case_id=s.case_id
   AND ((newer.kind=s.kind AND newer.reference=s.reference AND newer.version>s.version)
    OR (newer.kind=r.kind AND newer.reference=r.reference AND newer.version>r.version))) THEN RETURN false; END IF;
 SELECT max(id) INTO basis FROM finance_schedulereview WHERE work_id=r.id AND authority->>'purpose'='basis';
 IF basis IS DISTINCT FROM (s.snapshot->>'basis_review')::bigint
  OR (s.snapshot->>'basis_approved')::boolean IS DISTINCT FROM psl_ppe_review_current(basis)
  OR (r.result->'date_basis_ambiguous'='true'::jsonb AND NOT psl_ppe_review_current(basis)) THEN RETURN false; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_each(s.snapshot->'policies') p WHERE p.value->>'status'<>'ACTIVE'
   OR NOT psl_ppe_policy_current(s.case_id,(p.value->>'id')::bigint)) THEN RETURN false; END IF;
 IF s.parent_id IS NOT NULL AND NOT psl_ppe_mapping_current(s.parent_id) THEN RETURN false; END IF;
 prior_id=(s.payload->>'prior_id')::bigint;
 IF prior_id IS NOT NULL AND (NOT psl_ppe_schedule_current(prior_id,depth+1)
  OR NOT psl_ppe_review_current((s.snapshot->'prior'->>2)::bigint)) THEN RETURN false; END IF;
 IF s.snapshot->'owner_validation'->'valid'='true'::jsonb THEN
  FOR pin IN SELECT value FROM jsonb_array_elements(s.snapshot->'owner_validation'->'reviews') LOOP
   IF NOT EXISTS(SELECT 1 FROM documents_validationreview vr JOIN documents_validationpackage vp ON vp.id=vr.package_id
    WHERE vr.id=(pin::text)::bigint AND vr.package_id=(s.snapshot->'owner_validation'->>'id')::bigint
     AND vr.verdict='approve' AND psl_ppe_authority_current(s.case_id,vr.authority)
     AND vr.id=(SELECT max(id) FROM documents_validationreview WHERE package_id=vr.package_id AND kind=vr.kind)) THEN RETURN false; END IF;
  END LOOP;
 END IF;
 RETURN true;
END $$;
"""

SOURCE=r"""
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
"""
VERIFIED=r"""
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
"""
def extend(previous):
    marker="'delivery-go-live/v1','finance-accounts/v1','rfp-response/v1'"
    assert previous.count(marker)==1
    sql=previous.replace(marker,marker+",'finance-ppe/v1'")
    marker="WHEN 'delivery-go-live/v1' THEN 'OPS.factory_go_live_execution'"
    assert sql.count(marker)==1
    sql=sql.replace(marker,marker+" WHEN 'finance-ppe/v1' THEN 'OPS.factory_ppe_execution'")
    marker=" IF NEW.status='verified' THEN"
    assert sql.count(marker)==1 and sql.count(' RETURN NEW;')==1
    return FUNCTIONS+sql.replace(marker,SOURCE+marker).replace(' RETURN NEW;',VERIFIED+' RETURN NEW;')
