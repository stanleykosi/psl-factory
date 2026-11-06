"""Native acknowledgement and exact source-owned disposition readback. No transport/write."""
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate,digest
from apps.finance import receipt_followup as source
from apps.finance.models import FinanceReceiptFollowup as Request,FinanceReceiptFollowupDecision as Decision
from apps.core.models import Case
from adapters import native_finance as native
from .finance_readback_database import provider

VERSION='psl.native-finance-followup-readback/v1'

def read(mapping,projection,rules,expected_binding):
    validate(source.PROJECTION,projection)
    if any(projection[k]!=mapping.payload[v] for k,v in [('source_case_id','source_case_id'),('source_invoice_id','source_invoice_id'),('source_correction_id','source_correction_id'),('variant','variant')]):
        raise ValidationError('Exact reviewed invoice/correction mapping required')
    public,(registry,args,secret)=native.binding(mapping)
    if public!=expected_binding:raise ValidationError('Current reviewed provider binding changed')
    with provider(args,rules) as db:
        native.session_identity(db.connection,registry)
        if db.connection.execute("SELECT to_regclass('public.psl_native_finance_identity')").fetchone()[0] is None:raise ValidationError('Fresh current Finance marker required')
        marker=db.connection.execute('SELECT reference,secret_sha256,contract_version FROM public.psl_native_finance_identity').fetchall()
        if marker!=[(registry['identity_ref'],native.n.digest(secret),native.VERSION)]:raise ValidationError('Current Finance marker differs')
        result=snapshot(projection,rules,mapping.plan.case.synthetic)
    return {**result,'format':VERSION,'provider_binding_sha256':digest(public),'classification':'native_postgres_finance_followup',
        'fixture_scope':'synthetic' if mapping.plan.case.synthetic else 'operational','direct_native_verification':True,'direct_vendor_verification':False,
        'password_authentication_proven':False,'execution_authorized':False,'financial_effect_verified':False,'debt_waived':False,'business_jobs_reenacted':False}

def snapshot(projection,rules,expected_synthetic):
    """Runs in the read-only source compartment; returns metadata and hashes only."""
    from django.db import connections
    from .finance_readback_database import ACTIVE
    db=connections[ACTIVE.get()];key=digest(projection);case=projection['source_case_id']
    result={'request_sha256':key,'outcome':'unknown','request_ref':None,'request_row_sha256':None,'decision_ref':None,'decision_sha256':None,
        'disposition':'absent','verdict':None,'hold_code':'request_not_observed','current_authority_verified':False}
    source_case=Case.objects.only('id','kind','synthetic').filter(pk=case).first()
    if source_case is None:return result
    if source_case.synthetic!=expected_synthetic:raise ValidationError('Actual source case and reviewed readback classification differ')
    with db.cursor() as cursor:
        cursor.execute("""SELECT id,sha256,request_key,octet_length(projection::text),
          encode(sha256(convert_to(to_jsonb(r)::text,'UTF8')),'hex') FROM finance_financereceiptfollowup r
          WHERE case_id=%s AND (request_key=%s OR projection->>'publication_operation'=%s) ORDER BY id LIMIT 3""",[case,key,projection['publication_operation']])
        rows=cursor.fetchall()
        if not rows:return result
        result.update(outcome='conflict',hold_code='request_projection_conflict')
        if len(rows)!=1:return result
        pk,sha,stored,size,row_sha=rows[0]
        if size>rules['max_payload_bytes']:raise ValidationError('Source request exceeds readback byte budget')
        if sha!=key or stored!=key:return result
        # Cap policy history/reference data before the authoritative source evaluator reads it.
        # Only authority references are relevant; unrelated Finance policy history cannot consume this budget.
        components="c.component IN ('OPS.finance_receipt_followup','D05.role_principal_assignments')"
        references=f"""r.case_id=scope.case_id AND EXISTS(SELECT 1 FROM policy_configuration c WHERE c.case_id=scope.case_id AND {components} AND
          ((r.version=1 AND c.envelope->'value' @> jsonb_build_array(r.ref)) OR
           (c.envelope->'value'->>'artifact_ref'=r.ref AND c.envelope->'value'->>'artifact_version'=r.version::text)))"""
        cursor.execute(f"""SELECT
          (SELECT count(*) FROM policy_configuration c WHERE c.case_id=scope.case_id AND {components})+
          (SELECT count(*) FROM policy_policystate s JOIN policy_configuration c ON c.id=s.configuration_id WHERE c.case_id=scope.case_id AND {components})+
          (SELECT count(*) FROM policy_registeredreference r WHERE {references}),
          (SELECT coalesce(max(octet_length(c.envelope::text)),0) FROM policy_configuration c WHERE c.case_id=scope.case_id AND {components}),
          (SELECT coalesce(max(octet_length(r.content::text)),0) FROM policy_registeredreference r WHERE {references})
          FROM (SELECT %s::uuid case_id) scope""",[case])
        records,envelope_bytes,reference_bytes=cursor.fetchone()
        if records>rules['max_records']:raise ValidationError('Source authority history exceeds configured readback budget')
        if max(envelope_bytes,reference_bytes)>rules['max_payload_bytes']:raise ValidationError('Source authority policy/reference exceeds readback byte budget')
        cursor.execute("""SELECT d.id,octet_length(d.pin::text)+coalesce(octet_length(j.intent::text),0),
          encode(sha256(convert_to(to_jsonb(d)::text,'UTF8')),'hex') FROM finance_financereceiptfollowupdecision d
          LEFT JOIN finance_invoicejob j ON j.id=d.job_id WHERE d.followup_id=%s ORDER BY d.id DESC LIMIT 1""",[pk])
        decision=cursor.fetchone()
        if decision and decision[1]>rules['max_payload_bytes']:raise ValidationError('Source disposition exceeds readback byte budget')
    r=Request.objects.only('id','case_id','request_key','sha256','projection','created_at').get(pk=pk)
    if r.projection!=projection or digest(r.projection)!=r.sha256:return result
    r.case=source_case
    latest=None
    if decision:
        from django.contrib.auth import get_user_model
        latest=Decision.objects.defer('note').get(pk=decision[0],followup=r)
        latest.actor=get_user_model().objects.only('id','is_active').get(pk=latest.actor_id)
    evaluation=source.disposition(r,latest)
    return {**result,'outcome':'acknowledged','request_ref':str(pk),'request_row_sha256':row_sha,'decision_ref':str(latest.pk) if latest else None,
        'decision_sha256':decision[2] if decision else None,'disposition':evaluation['status'],'hold_code':evaluation['hold_code'],
        'verdict':latest.verdict if latest else None,'current_authority_verified':evaluation['status']=='current'}
