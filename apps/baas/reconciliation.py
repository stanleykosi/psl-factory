"""Evidence comparison; findings are scoped supplied-source statements, never funds authority."""
import json,re
from decimal import Decimal,localcontext
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.identity.models import Grant
from apps.pmo.services import subject
from apps.policy.services import resolve,active_component,reference_values,decision_authority
from apps.finance.analysis import digest,note
from apps.finance.rules import decimal,number
from adapters.reconciliation import batch as parse_batch,at
from .models import ReconciliationBatch,ReconciliationAttestation,ReconciliationRun

CONTRACT='D09.reconciliation_contract_ref'
COMMANDS='D09.queue_state_command_map'

def locked(actor,case_id,action,expected):
    c=lock_case(actor,case_id,action,expected);list(Grant.objects.select_for_update().filter(case=c).order_by('pk'));require(actor,c,'baas.read');return c

def exact(case,model,pk):
    r=model.objects.filter(case=case,pk=pk).first()
    if not r:raise ValidationError('Select the exact BaaS subject on this case')
    return r

def current_batch(batch):
    if ReconciliationBatch.objects.filter(case=batch.case,reference=batch.reference,version__gt=batch.version).exists():raise ValidationError('A newer source batch revision exists')

def precise(value,rule):
    if value is None:return
    with localcontext() as ctx:
        ctx.prec=512;n=decimal(value)
        if n!=n.quantize(Decimal(1).scaleb(-rule['decimal_places'])):raise ValidationError('Reconciliation amount exceeds configured precision; no implicit rounding')

@transaction.atomic
def capture(actor,case_id,reference,evidence_id,expected):
    case=locked(actor,case_id,'baas.reconciliation.capture',expected)
    if not isinstance(reference,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',reference):raise ValidationError('Supply a bounded source family reference')
    e=subject(case,evidence_id,'reconciliation_input');v=parse_batch(e.body)
    old=ReconciliationBatch.objects.filter(case=case,reference=reference,evidence=e).first()
    if old:return old
    previous=ReconciliationBatch.objects.filter(case=case,reference=reference).order_by('-version').first()
    if previous and (previous.kind!=v['kind'] or previous.payload['source']!=v['source']):raise ValidationError('Source family revisions preserve kind and source identity')
    r=ReconciliationBatch.objects.create(case=case,reference=reference,version=previous.version+1 if previous else 1,kind=v['kind'],evidence=e,payload=v,actor=actor)
    event(actor,case,'baas.source_captured',batch=r.pk,kind=r.kind);bump(case);return r

@transaction.atomic
def attest(actor,case_id,batch_id,role,evidence_id,expected):
    case=locked(actor,case_id,'baas.reconciliation.attest',expected);b=exact(case,ReconciliationBatch,batch_id);current_batch(b)
    c=active_component(CONTRACT,case);m=reference_values(c)[0]
    if role not in m['attester_roles']:raise PermissionDenied('Configured source attester role required')
    e=subject(case,evidence_id,'reconciliation_attestation')
    try:value=json.loads(e.body)
    except (ValueError,TypeError):raise ValidationError('Attestation requires exact source hash and declared source')
    if value!={'batch_sha256':b.evidence.sha256,'source':b.payload['source']}:raise ValidationError('Attestation does not identify exact source evidence')
    auth=dict(decision_authority(actor,case,role),**{CONTRACT:c.pk,'role':role})
    r=ReconciliationAttestation.objects.create(batch=b,evidence=e,authority=auth,actor=actor);event(actor,case,'baas.source_attested',attestation=r.pk,batch=b.pk);bump(case);return r

def attested(batch,c,m):
    if batch.kind not in m['attestation_kinds']:return True,None
    r=ReconciliationAttestation.objects.filter(batch=batch).order_by('-pk').first()
    if not r:return False,None
    try:
        require(r.actor,batch.case,'baas.reconciliation.attest');require(r.actor,batch.case,'baas.read')
        now=dict(decision_authority(r.actor,batch.case,r.authority['role']),**{CONTRACT:c.pk,'role':r.authority['role']})
        return now==r.authority,r.pk
    except (ValidationError,PermissionDenied):return False,r.pk

def compare(case,selections):
    chosen={k:exact(case,ReconciliationBatch,pk) for k,pk in selections.items() if pk is not None}
    for kind,b in chosen.items():
        if b.kind!=kind:raise ValidationError('Selected source batch has a different kind')
        current_batch(b)
    resolution=resolve(CONTRACT,case);c=resolution.configuration;m=reference_values(c)[0] if resolution.status=='ACTIVE' else None
    manifest={'implementation':'baas-reconciliation/v1','date':timezone.localdate().isoformat(),'contract':{'status':resolution.status,'id':c.pk if c else None},
        'captured_batches':list(ReconciliationBatch.objects.filter(case=case).order_by('pk').values_list('pk','evidence__sha256')),'selected':{k:b.pk for k,b in chosen.items()},'sources':{}}
    findings=[];indexes={};ready={}
    for kind in ['ledger','settlement','queue']:
        b=chosen.get(kind);index={};ok=False
        if b:
            ok=True;problems=[];attestation=None
            if m:
                if b.payload['source']!=m['sources'][kind]:problems.append('Source differs from configured declared '+kind)
                if (timezone.now()-at(b.payload['as_of'])).total_seconds()>m['max_age_seconds']:problems.append(kind+' source is stale')
                certified,attestation=attested(b,c,m)
                if not certified:problems.append(kind+' needs configured exact source attestation')
            else:problems.append('Configure '+CONTRACT+': '+resolution.status)
            if b.payload['completeness']!='complete':findings.append(kind+' coverage is '+b.payload['completeness'])
            for row in b.payload['rows']:
                key=(row['partner'],row['transaction']);index.setdefault(key,[]).append(row)
                if m:precise(row['amount'],m)
            ok=not problems;findings+=problems
            manifest['sources'][kind]={'batch':b.pk,'sha256':b.evidence.sha256,'attestation':attestation,'ready':ok}
        else:findings.append('No selected '+kind+' source; only dependent checks are unavailable')
        indexes[kind]=index;ready[kind]=ok
    keys=sorted(set().union(*(set(i) for i in indexes.values())));rows=[]
    def fresh(row):return bool(m and row and (timezone.now()-at(row['observed_at'])).total_seconds()<=m['max_age_seconds'])
    for key in keys:
        groups={k:indexes[k].get(key,[]) for k in indexes};problems=[];finding='ambiguous';delta=None
        ledger=groups['ledger'][0] if len(groups['ledger'])==1 else None
        settlement=groups['settlement'][0] if len(groups['settlement'])==1 else None
        queue=groups['queue'][0] if len(groups['queue'])==1 else None
        if any(len(v)>1 for v in groups.values()):problems.append('Duplicate transaction rows; no arbitrary winner selected')
        if ledger and settlement and ready['ledger'] and ready['settlement'] and fresh(ledger) and fresh(settlement):
            if any(ledger[k]!=settlement[k] for k in ['customer','currency']):problems.append('Customer/currency dimensions conflict; no implicit match or FX')
            elif ledger['amount'] is None or settlement['amount'] is None:problems.append('Settlement or ledger amount is unknown')
            else:
                with localcontext() as ctx:
                    ctx.prec=512;delta=abs(decimal(ledger['amount'])-decimal(settlement['amount']))
                status=settlement['status']
                if status in m['statuses']['settled'] and delta<=decimal(m['amount_tolerance']):finding='settlement_confirmed'
                elif status in m['statuses']['pending']+m['statuses']['failed']:finding='not_confirmed'
                else:problems.append('Unknown settlement status or amount outside configured tolerance')
        else:problems.append('Missing, duplicate, stale or unattested comparison evidence')
        if queue and ledger and any(queue[k]!=ledger[k] for k in ['customer','currency']):problems.append('Queue dimensions conflict');queue=None
        queue_ready=bool(queue and ready['queue'] and fresh(queue))
        aged=bool(queue_ready and m and queue['queue_state'] in m['pending_queue_states'] and (timezone.now()-at(queue['observed_at'])).total_seconds()>m['pending_after_seconds'])
        rows.append({'partner':key[0],'transaction':key[1],'finding':finding,'amount_difference':number(delta),'ledger':ledger,'settlement':settlement,'queue':queue,'queue_ready':queue_ready,'queue_age_threshold_exceeded':aged,'issues':problems})
    if not rows:findings.append('No captured transactions in selected inventory')
    if any(r['issues'] for r in rows):findings.append('Transaction evidence gaps or discrepancies remain')
    result={'status':'held' if not m else 'partial' if findings else 'ready','scope':'selected_case_supplied_sources_only','full_reconciliation':False,'source_assurance':'declared_sources_and_configured_human_attestation_only',
        'rows':rows,'findings':findings,'business_queue_mutated':False,'financial_execution_authorized':False}
    return manifest,result

@transaction.atomic
def investigate(actor,case_id,ledger_id,settlement_id,queue_id,expected):
    case=locked(actor,case_id,'baas.reconciliation.calculate',expected);selections={'ledger':ledger_id,'settlement':settlement_id,'queue':queue_id}
    manifest,result=compare(case,selections);h=digest({'manifest':manifest,'result':result});old=ReconciliationRun.objects.filter(case=case,sha256=h).first()
    if old:return old
    r=ReconciliationRun.objects.create(case=case,selections=selections,manifest=manifest,result=result,sha256=h,actor=actor);event(actor,case,'baas.reconciliation_calculated',run=r.pk,status=result['status']);bump(case);return r

def ensure_current(run):
    require(run.actor,run.case,'baas.reconciliation.calculate');require(run.actor,run.case,'baas.read')
    manifest,result=compare(run.case,run.selections)
    if digest({'manifest':manifest,'result':result})!=run.sha256:raise ValidationError('Reconciliation evidence, policy, attestation or freshness changed; calculate current evidence')
