"""Immutable additive PPE terminal guard on the accepted forecast migration."""
from importlib import import_module
from django.db import migrations
PREVIOUS=import_module('apps.workflows.migrations.0067_factory_forecast').SQL
FUNCTIONS=r"""
CREATE OR REPLACE FUNCTION psl_ppe_policy_people_current(pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c WHERE c.id=pid AND
  CASE WHEN c.component IN ('F07.review_authority','AF13.owner_validation_rules') THEN
   EXISTS(SELECT 1 FROM policy_registeredreference r WHERE r.case_id=c.case_id
    AND r.ref=c.envelope->'value'->>'artifact_ref' AND r.version=(c.envelope->'value'->>'artifact_version')::integer
    AND r.sha256=c.envelope->'value'->>'sha256'
    AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(r.content->'assignments') assignment
     WHERE NOT EXISTS(SELECT 1 FROM auth_user u WHERE u.id=(assignment->>'user_id')::bigint AND u.is_active)))
  WHEN c.component='D05.role_principal_assignments' THEN
   NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(c.envelope->'value') selection(ref)
    LEFT JOIN policy_registeredreference r ON r.case_id=c.case_id AND r.ref=selection.ref AND r.version=1
    LEFT JOIN auth_user u ON u.id=(r.content->>'user_id')::bigint
    WHERE r.id IS NULL OR u.id IS NULL OR NOT u.is_active)
  ELSE true END);
$$;
CREATE OR REPLACE FUNCTION psl_ppe_policy_current(cid uuid, pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c JOIN core_case target_case ON target_case.id=c.case_id
  WHERE c.id=pid AND c.case_id=cid AND psl_ppe_policy_people_current(c.id)
  AND c.envelope->'subject_scope'=jsonb_build_object('kind',CASE WHEN target_case.kind='project' THEN 'project' ELSE 'service' END,'ref',c.case_id::text)
  AND (c.envelope->>'fixture_scope'='synthetic_test')=target_case.synthetic
  AND (SELECT state FROM policy_policystate WHERE configuration_id=c.id ORDER BY id DESC LIMIT 1)='active'
  AND (c.envelope->>'effective_from')::timestamptz<=clock_timestamp()
  AND (c.envelope->>'effective_until' IS NULL OR (c.envelope->>'effective_until')::timestamptz>clock_timestamp())
  AND NOT EXISTS(SELECT 1 FROM policy_scopeapplication ap
   JOIN policy_scopeversion sv ON sv.id=ap.source_id JOIN policy_configuration origin ON origin.id=sv.configuration_id
   JOIN core_case origin_case ON origin_case.id=origin.case_id
   WHERE ap.configuration_id=c.id AND (
    NOT psl_ppe_policy_people_current(origin.id) OR target_case.tenant<>origin_case.tenant OR target_case.synthetic<>origin_case.synthetic
    OR c.component<>origin.component OR (sv.kind<>'organization' AND c.case_id<>origin.case_id)
    OR NOT ((sv.kind='organization' AND sv.ref=origin_case.tenant)
     OR (sv.kind='project' AND origin_case.kind='project' AND sv.ref=origin.case_id::text)
     OR (sv.kind='service' AND origin_case.kind='support' AND sv.ref=origin.case_id::text)
     OR (sv.kind='contract' AND EXISTS(SELECT 1 FROM core_evidence e WHERE e.case_id=origin.case_id AND e.kind='sow' AND sv.ref='evidence:'||e.id::text)))
    OR sv.id IS DISTINCT FROM (SELECT family.id FROM policy_scopeversion family
     JOIN policy_configuration fc ON fc.id=family.configuration_id
     WHERE fc.case_id=origin.case_id AND fc.component=origin.component AND family.kind=sv.kind AND family.ref=sv.ref
      AND EXISTS(SELECT 1 FROM policy_scopestate fs WHERE fs.source_id=family.id AND fs.state IN ('active','revoked'))
     ORDER BY family.revision DESC LIMIT 1)
    OR EXISTS(SELECT 1 FROM unnest(ARRAY['effective_from','effective_until','implementation_id','implementation_version','reviewed_implementation_ref','component_schema_ref','schema_version','fixture_scope']) k
     WHERE c.envelope->k IS DISTINCT FROM origin.envelope->k)
    OR origin.envelope->'subject_scope'<>jsonb_build_object('kind',CASE WHEN origin_case.kind='project' THEN 'project' ELSE 'service' END,'ref',origin.case_id::text)
    OR (origin.envelope->>'fixture_scope'='synthetic_test')<>origin_case.synthetic
    OR (SELECT state FROM policy_scopestate WHERE source_id=sv.id ORDER BY id DESC LIMIT 1)<>'active'
    OR (SELECT state FROM policy_policystate WHERE configuration_id=origin.id ORDER BY id DESC LIMIT 1)<>'validated'
    OR NOT EXISTS(SELECT 1 FROM auth_user u WHERE u.id=ap.actor_id AND u.is_active)
    OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE user_id=ap.actor_id AND case_id=c.case_id AND action='case.read' AND active)
    OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE user_id=ap.actor_id AND case_id=c.case_id AND action='policy.configure' AND active)
    OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE user_id=ap.actor_id AND case_id=origin.case_id AND action='case.read' AND active)
    OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE user_id=ap.actor_id AND case_id=origin.case_id AND action='policy.read' AND active)
    OR NOT EXISTS(SELECT 1 FROM policy_scopestate activation JOIN auth_user u ON u.id=activation.actor_id
     WHERE activation.id=(SELECT max(id) FROM policy_scopestate WHERE source_id=sv.id AND state='active')
      AND u.is_active AND EXISTS(SELECT 1 FROM identity_grant WHERE user_id=u.id AND case_id=origin.case_id AND action='case.read' AND active)
      AND EXISTS(SELECT 1 FROM identity_grant WHERE user_id=u.id AND case_id=origin.case_id AND action='policy.activate' AND active)))));

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
    ((r.content->'eligibility'->>'valid_from')::timestamptz<=clock_timestamp()
     AND (r.content->'eligibility'->>'valid_until')::timestamptz>clock_timestamp())));
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
 IF NOT EXISTS(SELECT 1 FROM policy_configuration c JOIN policy_registeredreference ref
   ON ref.case_id=c.case_id AND ref.ref=c.envelope->'value'->>'artifact_ref'
    AND ref.version=(c.envelope->'value'->>'artifact_version')::integer AND ref.sha256=c.envelope->'value'->>'sha256'
   WHERE c.id=(s.snapshot->'policies'->'F07.source_rules'->>'id')::bigint
    AND EXTRACT(EPOCH FROM (clock_timestamp()-(r.payload->>'extracted_at')::timestamptz))<=(ref.content->>'max_age_seconds')::numeric)
 THEN RETURN false; END IF;
 prior_id=(s.payload->>'prior_id')::bigint;
 IF prior_id IS NOT NULL AND (NOT psl_ppe_schedule_current(prior_id,depth+1)
  OR NOT psl_ppe_review_current((s.snapshot->'prior'->>2)::bigint)) THEN RETURN false; END IF;
 IF s.snapshot->'owner_validation'->'valid'='true'::jsonb THEN
  FOR pin IN SELECT value FROM jsonb_array_elements(s.snapshot->'owner_validation'->'reviews') LOOP
   IF NOT EXISTS(SELECT 1 FROM documents_validationreview vr JOIN documents_validationpackage vp ON vp.id=vr.package_id
    WHERE vr.id=(pin::text)::bigint AND vr.package_id=(s.snapshot->'owner_validation'->>'id')::bigint
     AND vr.verdict='approve' AND psl_ppe_authority_current(s.case_id,vr.authority)
     AND psl_ppe_grants(s.case_id,vr.actor_id,ARRAY['case.read','validation.read',CASE WHEN vr.kind='acceptance' THEN 'validation.accept' ELSE 'validation.review' END])
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
    result=FUNCTIONS+sql.replace(marker,SOURCE+marker).replace(' RETURN NEW;',VERIFIED+' RETURN NEW;')
    restored=result.removeprefix(FUNCTIONS).replace(SOURCE,'',1).replace(VERIFIED,'',1)
    restored=restored.replace(",'finance-ppe/v1'",'',1).replace(" WHEN 'finance-ppe/v1' THEN 'OPS.factory_ppe_execution'",'',1)
    assert restored==previous
    return result

SQL=extend(PREVIOUS)

class Migration(migrations.Migration):
    dependencies=[('workflows','0067_factory_forecast')]
    operations=[migrations.RunSQL(SQL,PREVIOUS)]
