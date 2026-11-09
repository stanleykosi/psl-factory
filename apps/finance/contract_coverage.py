"""F31/F45 deterministic, permissioned contract obligations and invoice coverage.

Only explicit, evidenced dates are supported. No recurrence, amount, proration,
source precedence or real owner is inferred. Existing registers remain authoritative.
"""
import hashlib
import json
from datetime import date
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case, event, bump
from apps.core.models import Evidence
from apps.documents.contracts import validate
from apps.identity.services import require
from .billing import digest, coverage_current, ensure_current
from .models import (BillingCoverage, BillingPreparation, CoverageAccess, CoverageSource,
    CoverageTerms, CoverageTermsEvent, CoverageInvoiceReference, CoverageAssessment,
    CoveragePreparationRequest, CoveragePreparationReceipt, CoveragePreparationRoute, CoverageEvidenceScope, InvoiceIssue)

TEXT = {'type':'string','minLength':1,'maxLength':100}
NULLTEXT = {'anyOf':[TEXT,{'type':'null'}]}
DATE = {'type':'string','pattern':r'^\d{4}-\d{2}-\d{2}$'}
def obj(fields, required=None):
    return {'type':'object','properties':fields,'required':list(fields) if required is None else required,'additionalProperties':False}
PERIOD = obj({'start':DATE,'end':DATE,'bill_on':DATE})
NONBILLING_PERIOD = obj({'start':DATE,'end':DATE})
SOURCE = obj({'system':TEXT,'external_id':TEXT,'external_version':TEXT,'customer':TEXT,'service':TEXT,'contract':TEXT,
    'status':{'enum':['current','withdrawn','unknown']},'cadence':{'enum':['monthly','annual','explicit','unknown']},
    'service_state':{'enum':['active','suspended','terminated','free','unknown']},
    'state_changed_on':{'anyOf':[DATE,{'type':'null'}]},
    'start':{'anyOf':[DATE,{'type':'null'}]},'end':{'anyOf':[DATE,{'type':'null'}]},
    'schedule':{'type':'array','maxItems':120,'items':PERIOD},
    'nonbilling_periods':{'type':'array','maxItems':120,'items':NONBILLING_PERIOD},
    'state_treatment':{'enum':['bill_exact_schedule','no_billing_for_explicit_periods','explicit_mixed_periods','unknown']},
    'invoice_reference':NULLTEXT,'invoice_status':{'enum':['issued','void','unknown']},
    'invoice_period':{'anyOf':[PERIOD,{'type':'null'}]},
    'verification_method':{'enum':['supplied_readonly_invoice_v1','native_invoice_v1','not_applicable']}},
    ['system','external_id','external_version','customer','service','contract','status'])
TERMS = obj({'implementation':{'enum':['explicit-contract-schedule/v1']},
    'review_requirement':{'enum':['none','required','unknown']},
    'reviewer_id':{'anyOf':[{'type':'integer','minimum':1},{'type':'null'}]},
    'owner_id':{'anyOf':[{'type':'integer','minimum':1},{'type':'null'}]},
    'schedule_interpretation':obj({'mode':{'enum':['standard_periods','explicit_source_exception','explicit_no_billing_periods','explicit_mixed_periods','unknown']},
        'attestation':{'enum':['source_schedule_matches_cadence','source_explicitly_specifies_exception','source_explicitly_specifies_no_billing','source_explicitly_specifies_mixed_periods','unknown']},
        'evidence_id':{'anyOf':[{'type':'integer','minimum':1},{'type':'null'}]}}),
    'invoice_verification':obj({'method':{'enum':['supplied_readonly_invoice_v1','native_invoice_v1','unknown']},
        'verifier_id':{'anyOf':[{'type':'integer','minimum':1},{'type':'null'}]},
        'distinct_capture_actor':{'anyOf':[{'type':'boolean'},{'type':'null'}]}})},
    ['implementation','review_requirement','reviewer_id','owner_id'])
PERMISSIONS = ['read','capture','configure','activate','verify','prepare','receive','investigate']
ACTIONS = {'read':'coverage.read','capture':'coverage.capture','configure':'coverage.configure',
    'activate':'coverage.activate','verify':'coverage.invoice.verify','prepare':'coverage.prepare',
    'receive':'coverage.receive','investigate':'agent.coverage'}


def evidence(case, pk, kind, references=None, purpose=None):
    e = Evidence.objects.filter(case=case, pk=pk, kind=kind).first()
    if not e or e.sha256 != hashlib.sha256(e.body.encode()).hexdigest():
        raise ValidationError('Exact intact private coverage evidence is required')
    if purpose is not None:
        scope=CoverageEvidenceScope.objects.filter(case=case,evidence=e).first()
        if scope:
            validate({'type':'array','minItems':1,'maxItems':20,'uniqueItems':True,'items':TEXT},scope.references)
            validate({'type':'array','minItems':1,'maxItems':6,'uniqueItems':True,'items':{'enum':list(EVIDENCE_PURPOSES)}},scope.purposes)
        if not scope or purpose not in scope.purposes or not set(references or [])<=set(scope.references):
            raise ValidationError('Evidence purpose or exact source-reference scope differs')
    return e


def supplied_json(proof):
    try:return json.loads(proof.body)
    except (TypeError,ValueError):raise ValidationError('Exact typed JSON source evidence required')


def access(actor, case, reference, permission='read'):
    # Refresh active-account state rather than trusting a stale in-memory user.
    user = get_user_model().objects.get(pk=actor.pk)
    require(user, case, ACTIONS[permission])
    grant = CoverageAccess.objects.filter(case=case, reference=reference, principal=user).order_by('-pk').first()
    if not grant or permission not in grant.permissions:
        raise PermissionDenied('Current exact source-reference permission is required')
    require(grant.actor, case, 'coverage.access')
    return grant


def source_access(actor, source, permission='read', *, current=True):
    grant = access(actor, source.case, source.reference, permission)
    validate(SOURCE,source.payload)
    if source.kind not in ['register','contract','invoice']:raise ValidationError('Unsupported source kind')
    if digest(source.payload) != source.sha256:
        raise ValidationError('Source content changed')
    proof=evidence(source.case, source.evidence_id, 'coverage_source',[source.reference],'capture')
    if supplied_json(proof)!=source.payload:raise ValidationError('Source differs from exact evidence body')
    if current:
        if source.kind in ['register','contract'] and CoverageSource.objects.filter(case=source.case,kind=source.kind,payload__system=source.payload['system'],payload__external_id=source.payload['external_id']).exclude(reference=source.reference).exists():
            raise ValidationError('Conflicting aliases for the same supplied source identity require reconciliation')
        if CoverageSource.objects.filter(case=source.case, reference=source.reference, version__gt=source.version).exists():
            raise ValidationError('A newer authoritative source reference exists')
        if source.payload['status'] != 'current': raise ValidationError('Source is withdrawn or unknown')
        access(source.actor, source.case, source.reference, 'capture')
    return grant


@transaction.atomic
def grant_access(actor, case_id, reference, principal_id, permissions, evidence_id, expected):
    case = lock_case(actor, case_id, 'coverage.access', expected)
    validate(TEXT, reference)
    validate({'type':'array','uniqueItems':True,'maxItems':len(PERMISSIONS),'items':{'enum':PERMISSIONS}}, permissions)
    principal = get_user_model().objects.get(pk=principal_id)
    if permissions: require(principal, case, 'case.read')
    proof = evidence(case, evidence_id, 'coverage_access',[reference],'access')
    record = CoverageAccess.objects.create(case=case,reference=reference,principal=principal,
        permissions=permissions,evidence=proof,actor=actor)
    event(actor,case,'coverage.access_changed',record=record.pk);bump(case)
    return record


@transaction.atomic
def capture_source(actor, case_id, reference, kind, payload, evidence_id, expected):
    case = lock_case(actor,case_id,'coverage.capture',expected)
    access(actor,case,reference,'capture');validate(TEXT,reference);validate(SOURCE,payload)
    if kind not in ['register','contract','invoice']: raise ValidationError('Explicit source kind required')
    if kind in ['register','contract'] and CoverageSource.objects.filter(case=case,kind=kind,payload__system=payload['system'],payload__external_id=payload['external_id']).exclude(reference=reference).exists():
        raise ValidationError('This supplied source identity already has another reference in this case; reconcile aliases without creating a second obligation')
    proof = evidence(case,evidence_id,'coverage_source',[reference],'capture')
    try: body=json.loads(proof.body)
    except (TypeError,ValueError): raise ValidationError('Source evidence must contain the exact supplied JSON record')
    if body != payload: raise ValidationError('Source payload differs from supplied evidence')
    prior = CoverageSource.objects.filter(case=case,reference=reference).order_by('-version').first()
    if prior:
        if prior.kind != kind: raise ValidationError('Source reference kind cannot change')
        for key in ['system','external_id','customer','service','contract']:
            if prior.payload[key] != payload[key]: raise ValidationError('Stable source identity cannot be repurposed')
        if prior.sha256 == digest(payload):
            try:access(prior.actor,case,reference,'capture')
            except PermissionDenied:pass  # Explicit same-source re-attestation by a currently authorised contributor.
            else:return prior
        elif prior.payload['external_version'] == payload['external_version']:
            raise ValidationError('Conflicting content for the same external version; obtain a corrected authoritative version')
    record=CoverageSource.objects.create(case=case,reference=reference,version=prior.version+1 if prior else 1,
        kind=kind,payload=payload,sha256=digest(payload),evidence=proof,actor=actor)
    event(actor,case,'coverage.source_captured',record=record.pk,same_source_reaffirmation=bool(prior and prior.sha256==record.sha256));bump(case);return record


def exact(case, model, pk):
    key='terms__case' if model is CoverageAssessment else 'assessment__terms__case' if model is CoveragePreparationRequest else 'case'
    record=model.objects.filter(**{key:case},pk=pk).first()
    if not record: raise ValidationError('Exact same-case coverage record required')
    return record


def terms_access(actor, terms, permission='read', current=True):
    validate(TERMS,terms.payload)
    if terms.coverage.case_id!=terms.case_id or any(source.case_id!=terms.case_id for source in [terms.register,terms.contract]):
        raise ValidationError('Same-case coverage and sources required')
    if (terms.register.kind,terms.contract.kind)!=('register','contract'):
        raise ValidationError('Exact register and contract source kinds required')
    for source in [terms.register,terms.contract]: source_access(actor,source,permission,current=current)
    if digest(terms.payload)!=terms.sha256: raise ValidationError('Terms content changed')
    proof=evidence(terms.case,terms.evidence_id,'coverage_terms',[terms.register.reference,terms.contract.reference],'configure')
    if supplied_json(proof)!={'coverage_id':terms.coverage_id,'register_id':terms.register_id,'contract_id':terms.contract_id,'terms':terms.payload}:
        raise ValidationError('Terms differ from exact evidenced source binding')


@transaction.atomic
def draft_terms(actor, case_id, coverage_id, register_id, contract_id, payload, evidence_id, expected):
    case=lock_case(actor,case_id,'coverage.configure',expected);validate(TERMS,payload)
    cov=exact(case,BillingCoverage,coverage_id)
    register=exact(case,CoverageSource,register_id);contract=exact(case,CoverageSource,contract_id)
    if (register.kind,contract.kind)!=('register','contract'):raise ValidationError('Existing register and contract references required')
    for source in [register,contract]: source_access(actor,source,'configure',current=False)
    proof=evidence(case,evidence_id,'coverage_terms',[register.reference,contract.reference],'configure')
    try: declaration=json.loads(proof.body)
    except ValueError: raise ValidationError('Terms declaration must be supplied as JSON evidence')
    expected_proof={'coverage_id':cov.pk,'register_id':register.pk,'contract_id':contract.pk,'terms':payload}
    if declaration!=expected_proof:raise ValidationError('Terms declaration does not pin exact source versions and configuration')
    previous=CoverageTerms.objects.filter(coverage=cov).order_by('-version').first()
    if previous and previous.sha256==digest(payload) and previous.register_id==register.pk and previous.contract_id==contract.pk:
        try:terms_access(previous.actor,previous,'configure',current=False)
        except PermissionDenied:pass  # Explicit current contributor may re-attest unchanged interpretation; lifecycle review runs again.
        else:return previous
    terms=CoverageTerms.objects.create(case=case,coverage=cov,register=register,contract=contract,
        payload=payload,sha256=digest(payload),evidence=proof,actor=actor,version=previous.version+1 if previous else 1)
    CoverageTermsEvent.objects.create(terms=terms,state='draft',evidence=proof,actor=actor)
    event(actor,case,'coverage.terms_drafted',terms=terms.pk);bump(case);return terms


def validation_findings(actor, terms):
    findings=[]
    try:
        terms_access(actor,terms)
        terms_access(terms.actor,terms,'configure')
    except (ValidationError,PermissionDenied):findings.append('Exact current source versions or source permissions require reconciliation')
    cov=terms.coverage;r=terms.register.payload;c=terms.contract.payload
    if not coverage_current(cov):findings.append('Billing coverage has a newer version')
    identity={k:getattr(cov,k) for k in ['customer','service','contract']}
    if any(any(p[k]!=v for k,v in identity.items()) for p in [r,c]):findings.append('Register, contract and billing coverage identities conflict')
    for key in ['start','end']:
        if r.get(key) is not None and r[key]!=c.get(key):findings.append('Register and contract '+key+' dates conflict')
    if r.get('schedule') and r['schedule']!=c.get('schedule'):
        findings.append('Register and contract explicit schedules conflict')
    no_bill=c.get('state_treatment')=='no_billing_for_explicit_periods'
    mixed=c.get('state_treatment')=='explicit_mixed_periods'
    cadence=c.get('cadence','unknown')
    if cadence=='unknown' and not no_bill:findings.append('Contract cadence is unknown; ask the source owner for the billing rule')
    if r.get('cadence','unknown')!='unknown' and cadence!='unknown' and r['cadence']!=cadence:
        findings.append('Register and contract cadence conflict; owner resolution required, no precedence inferred')
    if c.get('service_state','unknown')=='unknown':findings.append('Contract service state is unknown')
    if r.get('service_state','unknown')!='unknown' and r['service_state']!=c.get('service_state'):
        findings.append('Register and contract service states conflict')
    if c.get('service_state')!='active' and c.get('state_treatment') not in ['bill_exact_schedule','no_billing_for_explicit_periods','explicit_mixed_periods']:
        findings.append('Suspended/free/terminated service billing treatment is unresolved; no proration assumed')
    if r.get('state_treatment','unknown')!='unknown' and c.get('state_treatment','unknown')!='unknown' and r['state_treatment']!=c['state_treatment']:
        findings.append('Register and contract billing treatments conflict')
    if no_bill and r.get('schedule'):
        findings.append('Register billing dates conflict with the explicit no-billing period declaration')
    if r.get('nonbilling_periods') and r['nonbilling_periods']!=c.get('nonbilling_periods'):
        findings.append('Register and contract no-billing periods conflict')
    if terms.payload['review_requirement']=='unknown':findings.append('Source interpretation review requirement is unknown')
    if terms.payload['review_requirement']=='required' and not terms.payload['reviewer_id']:
        findings.append('Configured interpretation reviewer is missing')
    interpretation=terms.payload.get('schedule_interpretation') or {}
    mode=interpretation.get('mode')
    expected_attestation={'standard_periods':'source_schedule_matches_cadence','explicit_source_exception':'source_explicitly_specifies_exception','explicit_no_billing_periods':'source_explicitly_specifies_no_billing','explicit_mixed_periods':'source_explicitly_specifies_mixed_periods'}.get(mode)
    if mixed != (mode=='explicit_mixed_periods'):
        findings.append('Mixed intervals require their exact evidenced interpretation')
    if no_bill and mode!='explicit_no_billing_periods' or not no_bill and mode=='explicit_no_billing_periods':
        findings.append('No-billing treatment requires its exact explicit interpretation, not an implied zero charge')
    if not expected_attestation or interpretation.get('attestation')!=expected_attestation or not interpretation.get('evidence_id'):
        findings.append('Explicit evidenced cadence-to-schedule interpretation is missing')
    else:
        try:
            proof=evidence(terms.case,interpretation['evidence_id'],'coverage_schedule_interpretation',[terms.contract.reference],'configure');decl=supplied_json(proof)
            if not isinstance(decl,dict) or set(decl)!={'contract_source_id','contract_source_hash','mode','attestation','reason'} or not isinstance(decl['reason'],str) or not decl['reason'].strip() or len(decl['reason'])>1000 or any(decl[k]!=v for k,v in {'contract_source_id':terms.contract_id,'contract_source_hash':terms.contract.sha256,'mode':mode,'attestation':expected_attestation}.items()):
                raise ValidationError('Exact supplied interpretation proof required')
        except (ValidationError,ValueError,TypeError):findings.append('Cadence-to-schedule interpretation proof differs or is unavailable')
    try:
        start=date.fromisoformat(c['start']);end=date.fromisoformat(c['end'])
        if end<start:raise ValueError
        schedule=c.get('nonbilling_periods',[]) if no_bill else c.get('schedule',[])
        if not mixed and (no_bill and c.get('schedule') or not no_bill and c.get('nonbilling_periods')):
            findings.append('Mixed billed and no-billing intervals are not supported by this interpretation; no amounts or proration inferred')
        if mixed:
            if not c.get('schedule') or not c.get('nonbilling_periods'):raise ValueError
            schedule=c['schedule']+c['nonbilling_periods']
        if not schedule:raise ValueError
        periods=[]
        for row in schedule:
            begin=date.fromisoformat(row['start']);finish=date.fromisoformat(row['end'])
            if not no_bill and row in c.get('schedule',[]):date.fromisoformat(row['bill_on'])
            if not start<=begin<=finish<=end:raise ValueError
            if any(begin<=b and a<=finish for a,b in periods):raise ValueError
            periods.append((begin,finish))
            duration=(finish-begin).days+1
            if mode=='standard_periods' and ((cadence=='annual' and duration not in [365,366]) or (cadence=='monthly' and not 28<=duration<=31)):
                findings.append('Cadence and supplied period lengths conflict; explicit source-backed exception interpretation required')
    except (KeyError,TypeError,ValueError):findings.append('Explicit valid nonoverlapping contractual periods within start/end and applicable bill dates are required')
    return findings


@transaction.atomic
def transition(actor, case_id, terms_id, state, evidence_id, expected):
    action='coverage.configure' if state=='validated' else 'coverage.activate'
    case=lock_case(actor,case_id,action,expected);terms=exact(case,CoverageTerms,terms_id)
    terms_access(actor,terms,'configure' if state=='validated' else 'activate',current=state!='revoked')
    proof=evidence(case,evidence_id,'coverage_decision',[terms.register.reference,terms.contract.reference],'configure' if state=='validated' else 'activate')
    last=terms.events.order_by('-pk').first()
    allowed={'draft':['validated'],'validated':['active','revoked'],'active':['revoked'],'revoked':[]}
    if state not in allowed.get(last.state,[]):raise ValidationError('Invalid terms lifecycle transition')
    findings=validation_findings(actor,terms) if state!='revoked' else []
    if state=='active':
        if findings:raise ValidationError(findings)
        if terms.payload['review_requirement']=='required' and actor.pk!=terms.payload['reviewer_id']:
            raise PermissionDenied('Exact explicitly configured human reviewer required')
        if not actor.is_active:raise PermissionDenied('Active human principal required')
    record=CoverageTermsEvent.objects.create(terms=terms,state=state,findings=findings,evidence=proof,actor=actor)
    event(actor,case,'coverage.terms_transition',record=record.pk,state=state);bump(case);return record


def active_findings(actor,terms):
    findings=validation_findings(actor,terms);last=terms.events.order_by('-pk').first()
    if CoverageTermsEvent.objects.filter(terms__coverage=terms.coverage,terms__version__gt=terms.version,state='active').exists():
        findings.append('A later activated terms version supersedes this interpretation')
    if not last or last.state!='active':findings.append('Exact terms version is not active')
    else:
        if terms.payload['review_requirement']=='required' and last.actor_id!=terms.payload['reviewer_id']:
            findings.append('Activation lacks the exact configured human interpretation reviewer')
        try:terms_access(last.actor,terms,'activate')
        except (ValidationError,PermissionDenied):findings.append('Terms activation authority or source access was withdrawn')
    return findings


def source_pin(source):
    validate(SOURCE,source.payload)
    return {**{k:source.payload[k] for k in ['system','external_id','external_version']},'sha256':source.sha256}


def obligation(terms, row):
    return digest({'case':str(terms.case_id),'register':source_pin(terms.register),'contract':source_pin(terms.contract),
        'implementation':terms.payload['implementation'],'customer':terms.coverage.customer,'service':terms.coverage.service,
        'contract_reference':terms.coverage.contract,'period':row})


def invoice_current(actor, ref):
    if ref.source.case_id!=ref.case_id or ref.source.kind!='invoice':raise ValidationError('Same-case invoice source required')
    source_access(actor,ref.source)
    source_access(ref.actor,ref.source,'verify')
    proof=evidence(ref.case,ref.evidence_id,'coverage_verification',[ref.source.reference],'verify')
    if supplied_json(proof)!=ref.payload:raise ValidationError('Invoice verification differs from exact evidence')
    terms=exact(ref.case,CoverageTerms,ref.payload.get('terms_id'))
    verification_authority(ref.actor,terms,ref.source,ref.native_issue_id is not None)
    if digest(ref.payload)!=ref.sha256:raise ValidationError('Invoice verification changed')
    p=ref.source.payload
    if p.get('invoice_status')!='issued' or not p.get('invoice_reference') or not p.get('invoice_period'):
        raise ValidationError('Invoice is not an exact currently issued period reference')
    try:
        for key in ['start','end','bill_on']:date.fromisoformat(p['invoice_period'][key])
        if p['invoice_period']['start']>p['invoice_period']['end']:raise ValueError
    except (ValueError,TypeError):raise ValidationError('Invoice source dates are not a valid exact period')
    expected={'terms_id':terms.pk,'source_id':ref.source_id,'source_sha256':ref.source.sha256,
        'native_issue_id':ref.native_issue_id,'verification':'matched_exact_source_record',
        'invoice_reference':p['invoice_reference'],'period':p['invoice_period']}
    if ref.payload!=expected or p.get('verification_method')!=('native_invoice_v1' if ref.native_issue_id else 'supplied_readonly_invoice_v1'):
        raise ValidationError('Invoice verification proof differs from the exact source/native binding')
    if ref.native_issue_id:
        from .models import InvoiceCorrectionAcceptance
        i=ref.native_issue.invoice
        require(actor,ref.case,'finance.read')
        if ref.native_issue.payload!=i.payload or ref.native_issue.sha256!=i.sha256 or i.sha256!=digest(i.payload):
            raise ValidationError('Immutable native invoice and issued receipt differ')
        if ref.native_issue.job.invoice_id!=i.pk or ref.native_issue.job.kind!='issue' or ref.native_issue.obligation_key!=i.obligation_key:
            raise ValidationError('Native issued receipt identity differs')
        if InvoiceCorrectionAcceptance.objects.filter(correction__issue=ref.native_issue,correction__kind='void').exists():
            raise ValidationError('Native issued invoice has an accepted void; reconcile exact replacement evidence')
        if i.case_id!=ref.case_id or ref.native_issue.sha256!=digest(ref.native_issue.payload):
            raise ValidationError('Native invoice issue proof differs')
        cov=i.preparation.coverage
        if any(p[k]!=getattr(cov,k) for k in ['customer','service','contract']) or p['invoice_reference']!=i.reference:
            raise ValidationError('Native invoice identity differs from source correlation')
        if i.preparation.kind == 'fixed_contract':
            from .fixed_charge import recovered, obligation as native_obligation
            recovered(actor, i.preparation)
            if i.payload.get('contract_period') != p['invoice_period'] or i.obligation_key != native_obligation(i.preparation.fixed_charge):
                raise ValidationError('Native fixed-contract invoice period or obligation differs')
        elif i.preparation.kind != 'usage':
            raise ValidationError('Native stage invoices lack a supported exact service-period binding')
        if i.preparation.kind=='usage':
            months={row['period'] for row in i.preparation.usage.rows}
            period=p['invoice_period']
            if months!={period['start'][:7]} or period['start'][:7]!=period['end'][:7]:
                raise ValidationError('Native usage invoice period differs from source correlation')
    return ref


def verification_authority(actor,terms,source,native):
    terms_access(actor,terms,'verify')
    if active_findings(actor,terms):raise ValidationError('Current active interpretation required for invoice verification')
    if any(source.payload[k]!=getattr(terms.coverage,k) for k in ['customer','service','contract']):
        raise ValidationError('Invoice source differs from exact terms identity')
    rule=terms.payload.get('invoice_verification') or {}
    if rule.get('method')!=('native_invoice_v1' if native else 'supplied_readonly_invoice_v1') or rule.get('verifier_id') is None or type(rule.get('distinct_capture_actor')) is not bool:
        raise ValidationError('Invoice verification method, principal and separation rule are unconfigured')
    if actor.pk!=rule['verifier_id']:raise PermissionDenied('Exact configured invoice verifier required')
    if rule['distinct_capture_actor'] and actor.pk==source.actor_id:
        raise PermissionDenied('This explicit verification rule requires a distinct capture actor')
    return rule


@transaction.atomic
def verify_invoice(actor, case_id, source_id, proof_id, native_issue_id, expected, terms_id=None):
    case=lock_case(actor,case_id,'coverage.invoice.verify',expected);source=exact(case,CoverageSource,source_id)
    source_access(actor,source,'verify');p=source.payload
    if source.kind!='invoice' or not p.get('invoice_reference') or not p.get('invoice_period') or p.get('invoice_status')!='issued':
        raise ValidationError('Typed issued invoice reference and exact contractual period required')
    try:
        for key in ['start','end','bill_on']:date.fromisoformat(p['invoice_period'][key])
    except (ValueError,TypeError):raise ValidationError('Valid explicit invoice period dates required')
    if p['invoice_period']['end']<p['invoice_period']['start']:raise ValidationError('Invalid invoice period')
    proof=evidence(case,proof_id,'coverage_verification',[source.reference],'verify')
    terms=exact(case,CoverageTerms,terms_id)
    verification_authority(actor,terms,source,native_issue_id is not None)
    value={'terms_id':terms.pk,'source_id':source.pk,'source_sha256':source.sha256,'native_issue_id':native_issue_id,
        'verification':'matched_exact_source_record','invoice_reference':p['invoice_reference'],'period':p['invoice_period']}
    try: supplied=json.loads(proof.body)
    except ValueError:raise ValidationError('Exact typed verification evidence required')
    if supplied!=value:raise ValidationError('Verification evidence does not match exact invoice source and period')
    native=InvoiceIssue.objects.filter(pk=native_issue_id,invoice__case=case).first() if native_issue_id else None
    if native_issue_id and not native:raise ValidationError('Exact native issued invoice required')
    if p.get('verification_method')!=('native_invoice_v1' if native else 'supplied_readonly_invoice_v1'):
        raise ValidationError('Supported read-only invoice verification boundary required')
    old=CoverageInvoiceReference.objects.filter(source=source,sha256=digest(value)).first()
    if old:invoice_current(actor,old);return old
    ref=CoverageInvoiceReference.objects.create(case=case,source=source,native_issue=native,payload=value,sha256=digest(value),evidence=proof,actor=actor)
    invoice_current(actor,ref)
    event(actor,case,'coverage.invoice_verified',record=ref.pk);bump(case);return ref


def projection(actor,terms,as_of):
    terms_access(actor,terms,current=False)
    if type(as_of) is not date:raise ValidationError('Explicit assessment date required')
    findings=active_findings(actor,terms)
    snapshot={'implementation':'contract-coverage/v1','terms':terms.pk,'terms_hash':terms.sha256,
        'register':terms.register_id,'register_hash':terms.register.sha256,'contract':terms.contract_id,'contract_hash':terms.contract.sha256,
        'lifecycle':terms.events.order_by('-pk').values_list('pk',flat=True).first(),'as_of':as_of.isoformat(),'invoices':[]}
    obligations=[];nonbilling=[]
    # Do not expose inaccessible source identities or claim completeness over them.
    candidates=[];unknown=False;seen_sources=set()
    for ref in CoverageInvoiceReference.objects.filter(case=terms.case).select_related('source','native_issue__invoice').order_by('-pk'):
        if ref.source_id in seen_sources:continue
        seen_sources.add(ref.source_id)
        if CoverageSource.objects.filter(case=terms.case,reference=ref.source.reference,version__gt=ref.source.version).exists():continue
        p=ref.source.payload
        if any(p[k]!=getattr(terms.coverage,k) for k in ['customer','service','contract']):continue
        try:invoice_current(actor,ref)
        except (PermissionDenied,ValidationError):unknown=True;continue
        candidates.append(ref);snapshot['invoices'].append({'id':ref.pk,'source':ref.source_id,'hash':ref.sha256})
    # Captured but not independently verified invoice evidence is an explicit unknown.
    for src in CoverageSource.objects.filter(case=terms.case,kind='invoice'):
        if any(src.payload[k]!=getattr(terms.coverage,k) for k in ['customer','service','contract']):continue
        if CoverageSource.objects.filter(case=terms.case,reference=src.reference,version__gt=src.version).exists():continue
        if not any(r.source_id==src.pk for r in candidates):unknown=True
    if unknown:findings.append('One or more relevant invoice sources are unverified, stale, withdrawn or inaccessible; coverage is incomplete')
    if not active_findings(actor,terms):
        for row in sorted(terms.contract.payload.get('schedule',[]),key=lambda v:(v['bill_on'],v['start'])):
            matches=[r for r in candidates if r.source.payload['invoice_period']==row]
            identities={(r.source.payload['system'],r.source.payload['invoice_reference']) for r in matches}
            status='not_due' if date.fromisoformat(row['bill_on'])>as_of else 'missing_invoice'
            if len(matches)==1 and len(identities)==1:status='covered'
            elif len(matches)>1:status='conflict'
            if unknown:status='indeterminate'
            obligations.append(dict(row,key=obligation(terms,row),status=status,invoice_refs=[r.pk for r in matches]))
        if terms.contract.payload.get('state_treatment') in ['no_billing_for_explicit_periods','explicit_mixed_periods']:
            for row in terms.contract.payload.get('nonbilling_periods',[]):
                matches=[r for r in candidates if r.source.payload['invoice_period']['start']<=row['end'] and row['start']<=r.source.payload['invoice_period']['end']]
                status='indeterminate' if unknown else 'conflict' if matches else 'no_billing_obligation'
                nonbilling.append(dict(row,status=status,invoice_refs=[r.pk for r in matches]))
                if matches:findings.append('An issued invoice overlaps an explicit no-billing period; reconcile the contradiction without waiving existing debt')
    result={'status':'indeterminate' if findings or any(x['status'] in ['conflict','indeterminate'] for x in obligations+nonbilling) else 'assessed',
        'findings':findings,'obligations':obligations,'nonbilling_periods':nonbilling,'debt_waived':False,'owner_id':terms.payload['owner_id'],'scope':'exact supplied service and schedule only','basis':'as_of_projection',
        'coverage_basis':'verified issued invoice reference, not amount or tax correctness',
        'deduplication_scope':'case and supplied source contract only; no global invoice claim',
        'invoice_issued':False,'paid':False,'ledger_posted':False,'recognition_recorded':False,'external_authenticity_verified':False}
    return snapshot,result


@transaction.atomic
def assess(actor,case_id,terms_id,as_of,expected):
    case=lock_case(actor,case_id,'coverage.assess',expected);terms=exact(case,CoverageTerms,terms_id)
    snapshot,result=projection(actor,terms,as_of);key=digest({'snapshot':snapshot,'result':result,'actor':actor.pk})
    old=CoverageAssessment.objects.filter(operation_key=key).first()
    if old:return old
    record=CoverageAssessment.objects.create(terms=terms,as_of=as_of,snapshot=snapshot,result=result,operation_key=key,actor=actor)
    event(actor,case,'coverage.assessed',assessment=record.pk);bump(case);return record


def current_assessment(actor,assessment):
    snapshot,result=projection(actor,assessment.terms,assessment.as_of)
    if snapshot!=assessment.snapshot or result!=assessment.result:raise ValidationError('Coverage assessment is stale; reassess exact sources')
    if result['status']!='assessed':raise ValidationError('Resolve coverage findings before preparation handoff')
    return result


@transaction.atomic
def request_preparation(actor,case_id,assessment_id,obligation_key,recipient_id,expected):
    case=lock_case(actor,case_id,'coverage.prepare',expected);assessment=exact(case,CoverageAssessment,assessment_id)
    terms_access(actor,assessment.terms,'prepare');result=current_assessment(actor,assessment)
    rows=[r for r in result['obligations'] if r['key']==obligation_key and r['status']=='missing_invoice']
    if len(rows)!=1:raise ValidationError('Only an exact due uncovered obligation can enter preparation')
    if date.fromisoformat(rows[0]['bill_on'])>timezone.localdate():
        raise ValidationError('This future planning obligation is not currently due in the configured business time zone; no due-work handoff was created')
    recipient=get_user_model().objects.get(pk=recipient_id)
    terms_access(recipient,assessment.terms,'receive');require(recipient,case,'finance.billing.prepare')
    key=digest({'obligation':obligation_key})
    old=CoveragePreparationRequest.objects.filter(operation_key=key).first()
    if old:
        original_receipt=CoveragePreparationReceipt.objects.filter(request=old).first()
        if original_receipt:receipt_identity(original_receipt);return old
        route=preparation_route(old)
        if route['recipient'].pk!=recipient.pk or route['assessment'].pk!=assessment.pk or route['state']!='ready':
            raise ValidationError('Obligation already routed; explicitly revalidate or cancel the original request')
        return old
    record=CoveragePreparationRequest.objects.create(assessment=assessment,obligation_key=obligation_key,recipient=recipient,
        operation_key=key,payload={'terms':assessment.terms_id,'assessment':assessment.pk,'obligation':rows[0],
        'scope':'internal Finance preparation only; no invoice creation or delivery','invoice_issued':False},actor=actor)
    from apps.workflows.models import HumanTask,TaskEvent
    task=HumanTask.objects.create(case=case,kind='factory_information',factory_key='coverage:'+key,
        context={'purpose':'coverage_preparation','request':record.pk},required_role='Finance preparation',created_by=actor)
    TaskEvent.objects.create(task=task,actor=actor,action='requested',data={'request':record.pk})
    event(actor,case,'coverage.preparation_requested',request=record.pk);bump(case);return record


def request_identity(request):
    assessment=request.assessment;terms=assessment.terms
    validate({'type':'object','properties':{'obligations':{'type':'array','maxItems':120,'items':{'type':'object'}}},'required':['obligations']},assessment.result)
    rows=[r for r in assessment.result.get('obligations',[]) if r.get('key')==request.obligation_key and r.get('status')=='missing_invoice']
    if len(rows)!=1:raise ValidationError('Exact original obligation required')
    period={k:rows[0].get(k) for k in ['start','end','bill_on']};validate(PERIOD,period)
    if obligation(terms,period)!=request.obligation_key:
        raise ValidationError('Original request lacks an exact source-backed obligation')
    expected={'terms':terms.pk,'assessment':assessment.pk,'obligation':rows[0],
        'scope':'internal Finance preparation only; no invoice creation or delivery','invoice_issued':False}
    if request.payload!=expected or request.operation_key!=digest({'obligation':request.obligation_key}):
        raise ValidationError('Original preparation request identity or packet differs')


def receipt_identity(receipt):
    request=receipt.request;request_identity(request)
    ident={'type':'integer','minimum':1};nullable={'anyOf':[ident,{'type':'null'}]}
    validate(obj({'request':ident,'operation_key':TEXT,'received_by':ident,'route_id':nullable,'assessment_id':ident,
        'preparation_id':nullable,'status':{'enum':['received_for_preparation']},'invoice_issued':{'enum':[False]}}),receipt.payload)
    route_id=receipt.payload.get('route_id')
    route=request.routes.filter(pk=route_id).first() if route_id else None
    if route_id and (not route or route.state!='ready'):raise ValidationError('Receipt does not bind an executable original route')
    assessment=route.assessment if route else request.assessment
    recipient_id=route.recipient_id if route else request.recipient_id
    expected={'request':request.pk,'operation_key':request.operation_key,'received_by':recipient_id,
        'route_id':route_id,'assessment_id':assessment.pk,'preparation_id':receipt.preparation_id,
        'status':'received_for_preparation','invoice_issued':False}
    if receipt.actor_id!=recipient_id or receipt.payload!=expected:
        raise ValidationError('Original receipt identity or packet differs')
    if receipt.preparation_id and receipt.preparation.coverage_id!=assessment.terms.coverage_id:
        raise ValidationError('Original receipt preparation coverage differs')
    return receipt


def preparation_route(request):
    request_identity(request)
    latest=request.routes.order_by('-pk').first()
    if latest:
        if latest.assessment.terms.case_id!=request.assessment.terms.case_id or latest.state not in ['ready','cancelled']:
            raise ValidationError('Exact same-case routing state required')
        rows=[r for r in latest.assessment.result.get('obligations',[]) if r.get('key')==request.obligation_key]
        if len(rows)!=1:raise ValidationError('Route assessment differs from original obligation')
    return {'assessment':latest.assessment if latest else request.assessment,
        'recipient':latest.recipient if latest else request.recipient,
        'actor':latest.actor if latest else request.actor,'state':latest.state if latest else 'ready',
        'id':latest.pk if latest else None}


@transaction.atomic
def route_preparation(actor,case_id,request_id,assessment_id,recipient_id,state,evidence_id,expected):
    case=lock_case(actor,case_id,'coverage.prepare',expected);request=exact(case,CoveragePreparationRequest,request_id)
    terms_access(actor,request.assessment.terms,'prepare',current=False)
    proof=evidence(case,evidence_id,'coverage_decision',[request.assessment.terms.register.reference,request.assessment.terms.contract.reference],'prepare')
    if state not in ['ready','cancelled']:raise ValidationError('Explicit revalidation or cancellation required')
    old=CoveragePreparationReceipt.objects.filter(request=request).first()
    if old:return receipt_identity(old)  # Reconcile committed receipt, never reroute/reinvoice it.
    assessment=exact(case,CoverageAssessment,assessment_id)
    recipient=get_user_model().objects.get(pk=recipient_id)
    if state=='ready':
        terms_access(actor,assessment.terms,'prepare');result=current_assessment(actor,assessment)
        rows=[r for r in result['obligations'] if r['key']==request.obligation_key and r['status']=='missing_invoice']
        if len(rows)!=1:raise ValidationError('Revalidation must preserve exact source-backed obligation identity')
        if date.fromisoformat(rows[0]['bill_on'])>timezone.localdate():
            raise ValidationError('Future planning projection does not establish a currently due obligation')
        terms_access(recipient,assessment.terms,'receive');require(recipient,case,'finance.billing.prepare')
    elif assessment.pk!=preparation_route(request)['assessment'].pk or recipient.pk!=preparation_route(request)['recipient'].pk:
        raise ValidationError('Cancel the exact current route assessment and recipient')
    previous=request.routes.order_by('-pk').first()
    if previous and (previous.assessment_id,previous.recipient_id,previous.state)==(assessment.pk,recipient.pk,state):return previous
    route=CoveragePreparationRoute.objects.create(request=request,assessment=assessment,recipient=recipient,
        state=state,evidence=proof,actor=actor)
    from apps.workflows.models import HumanTask,TaskEvent
    task=HumanTask.objects.select_for_update().get(factory_key='coverage:'+request.operation_key)
    task.status='open' if state=='ready' else 'cancelled';task.claimed_by=recipient;task.revision+=1
    task.save(update_fields=['status','claimed_by','revision'])
    TaskEvent.objects.create(task=task,actor=actor,action='revalidated' if state=='ready' else 'cancelled',data={'route':route.pk})
    event(actor,case,'coverage.preparation_routed',route=route.pk,state=state);bump(case);return route


@transaction.atomic
def receive_preparation(actor,case_id,request_id,preparation_id,expected):
    case=lock_case(actor,case_id,'coverage.receive',expected);request=exact(case,CoveragePreparationRequest,request_id)
    route=preparation_route(request);terms=route['assessment'].terms
    terms_access(actor,terms,'receive',current=False)
    require(actor,case,'finance.billing.prepare')
    old=CoveragePreparationReceipt.objects.filter(request=request).first()
    if old:
        receipt_identity(old)
        if old.actor_id!=actor.pk:raise PermissionDenied('Only the recorded recipient can replay this receipt operation')
        if old.preparation_id!=preparation_id:raise ValidationError('Receipt is immutable; recover the original acknowledged result')
        return old
    if actor.pk!=route['recipient'].pk:raise PermissionDenied('Exact current internal Finance recipient required')
    if route['state']!='ready':raise ValidationError('Preparation request is cancelled; explicit revalidation is required')
    terms_access(actor,terms,'receive');terms_access(route['actor'],terms,'prepare')
    current_assessment(actor,route['assessment'])
    prep=exact(case,BillingPreparation,preparation_id) if preparation_id else None
    if prep:
        ensure_current(prep)
        if prep.coverage_id!=terms.coverage_id:raise ValidationError('Native preparation belongs to another coverage version')
        row=next(r for r in route['assessment'].result['obligations'] if r['key']==request.obligation_key)
        if not prep.usage_id or {r['period'] for r in prep.usage.rows}!={row['start'][:7]} or row['start'][:7]!=row['end'][:7]:
            raise ValidationError('Exact native usage-period preparation required; other preparation kinds remain separate')
    receipt=CoveragePreparationReceipt.objects.create(request=request,preparation=prep,
        payload={'request':request.pk,'operation_key':request.operation_key,'received_by':actor.pk,
            'route_id':route['id'],'assessment_id':route['assessment'].pk,
            'preparation_id':prep.pk if prep else None,'status':'received_for_preparation','invoice_issued':False},actor=actor)
    from apps.workflows.models import HumanTask,TaskEvent
    task=HumanTask.objects.select_for_update().get(factory_key='coverage:'+request.operation_key)
    task.status='completed';task.revision+=1;task.save(update_fields=['status','revision'])
    TaskEvent.objects.create(task=task,actor=actor,action='received',data={'receipt':receipt.pk})
    event(actor,case,'coverage.preparation_received',receipt=receipt.pk);bump(case);return receipt


EVIDENCE_PURPOSES = {
    'access': ['coverage_access'],
    'capture': ['coverage_source'],
    'configure': ['coverage_terms','coverage_schedule_interpretation','coverage_decision','coverage_fixed_charge'],
    'activate': ['coverage_decision'],
    'verify': ['coverage_verification'],
    'prepare': ['coverage_decision','coverage_continuation'],
}

@transaction.atomic
def supply_evidence(actor,case_id,references,purposes,kind,body,source,expected):
    case=lock_case(actor,case_id,'evidence.add',expected)
    validate({'type':'array','minItems':1,'maxItems':20,'uniqueItems':True,'items':TEXT},references)
    validate({'type':'array','minItems':1,'maxItems':6,'uniqueItems':True,'items':{'enum':list(EVIDENCE_PURPOSES)}},purposes)
    for purpose in purposes:
        if kind not in EVIDENCE_PURPOSES[purpose]:raise ValidationError('Evidence kind is not supported for this purpose')
        if purpose=='access':require(actor,case,'coverage.access')
        else:
            for reference in references:access(actor,case,reference,purpose)
    from apps.core.services import add_evidence
    proof=add_evidence(actor,case.pk,kind,body,source,expected=case.revision)
    CoverageEvidenceScope.objects.create(case=case,evidence=proof,references=sorted(references),purposes=sorted(purposes),actor=actor)
    event(actor,case,'coverage.evidence_supplied',evidence=proof.pk)
    return proof
