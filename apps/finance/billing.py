import hashlib,json,re
from decimal import Decimal,localcontext
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.pmo.services import subject
from apps.policy.services import resolve,reference_values
from apps.documents.contracts import validate
from django.utils import timezone
from datetime import datetime,date
from adapters.billing_usage import preview,KEY,PERIOD
from .models import BillingCoverage,BillingUsage,BillingPreparation,Handoff
from .billing_math import price
from .rules import number


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def exact(case,model,pk):
    obj=model.objects.filter(**({'coverage__case':case} if model is BillingUsage else {'case':case}),pk=pk).first()
    if not obj:raise ValidationError('Billing record is outside this case')
    return obj

def coverage_current(cov):
    return not BillingCoverage.objects.filter(case=cov.case,reference=cov.reference,version__gt=cov.version).exists()

@transaction.atomic
def register_coverage(actor,case_id,reference,customer,service,contract,currency,amount_basis,from_period,to_period,completeness,evidence_id,expected):
    case=lock_case(actor,case_id,'finance.billing.register',expected)
    for value in [reference,customer,service,contract,amount_basis]:
        if not isinstance(value,str) or not KEY.fullmatch(value):raise ValidationError('Use explicit bounded billing identifiers')
    if not re.fullmatch('[A-Z]{3}',currency) or not PERIOD.fullmatch(from_period) or not PERIOD.fullmatch(to_period) or to_period<from_period:raise ValidationError('Invalid coverage currency or period interval')
    try:
        start=date.fromisoformat(from_period+'-01');end=date.fromisoformat(to_period+'-01')
        if (end.year-start.year)*12+end.month-start.month>=120:raise ValueError
    except ValueError:raise ValidationError('Coverage requires valid months spanning at most 120 months')
    if completeness not in ['complete','partial','unknown']:raise ValidationError('Explicit coverage completeness required')
    evidence=subject(case,evidence_id,'billing_coverage')
    previous=BillingCoverage.objects.filter(case=case,reference=reference).order_by('-version').first()
    cov=BillingCoverage.objects.create(case=case,reference=reference,version=previous.version+1 if previous else 1,customer=customer,service=service,contract=contract,
        currency=currency,amount_basis=amount_basis,from_period=from_period,to_period=to_period,completeness=completeness,evidence=evidence,actor=actor)
    event(actor,case,'billing.coverage_registered',coverage=cov.pk,predecessor=previous.pk if previous else None);bump(case);return cov

@transaction.atomic
def capture_usage(actor,case_id,coverage_id,evidence_id,expected,source_context=None):
    case=lock_case(actor,case_id,'finance.billing.capture',expected);cov=exact(case,BillingCoverage,coverage_id)
    context=source_context if source_context is not None else {'provider_ref':None,'extracted_at':None,'completeness':'unknown'}
    validate({'type':'object','properties':{'provider_ref':{'anyOf':[{'type':'string','minLength':1,'maxLength':100},{'type':'null'}]},
        'extracted_at':{'anyOf':[{'type':'string'},{'type':'null'}]},'completeness':{'enum':['complete','partial','unknown']}},
        'required':['provider_ref','extracted_at','completeness'],'additionalProperties':False},context)
    if context['extracted_at'] is not None:
        try:
            at=datetime.fromisoformat(context['extracted_at'])
            if at.utcoffset() is None or at>timezone.now():raise ValueError
        except (TypeError,ValueError):raise ValidationError('Extraction timestamp must be actual and timezone aware')
    evidence=subject(case,evidence_id,'billing_usage');rows,findings=preview(evidence.body)
    if BillingUsage.objects.filter(coverage=cov,source_sha256=evidence.sha256).exists():raise ValidationError('Exact usage content already captured; use original batch')
    previous=set()
    for batch in BillingUsage.objects.filter(coverage__case=case):
        previous.update((r['customer'],r['service'],r['contract'],r['transaction_id']) for r in batch.rows)
    for r in rows:
        if (r['customer'],r['service'],r['contract'])!=(cov.customer,cov.service,cov.contract):findings.append(f"Line {r['line']}: customer/service/contract differs from coverage")
        if not cov.from_period<=r['period']<=cov.to_period:findings.append(f"Line {r['line']}: period outside coverage")
        if (r['customer'],r['service'],r['contract'],r['transaction_id']) in previous:findings.append(f"Line {r['line']}: previously captured transaction; reconcile correction before pricing")
    batch=BillingUsage.objects.create(coverage=cov,evidence=evidence,source_sha256=evidence.sha256,rows=rows,findings=findings,source_context=context,actor=actor)
    event(actor,case,'billing.usage_captured',usage=batch.pk,findings=len(findings));bump(case);return batch

def policies(case,keys):
    snapshot={};values={};findings=[]
    for key in keys:
        r=resolve(key,case);c=r.configuration
        snapshot[key]={'status':r.status,'id':c.pk if c else None,'revision':c.revision if c else None}
        if r.status=='ACTIVE':values[key]=reference_values(c)
        else:findings.append(key+': '+r.status)
    return snapshot,values,findings

def inputs(cov,kind,usage=None,handoff=None):
    keys=['D08.effective_price_rule_refs','D08.tax_tier_rounding_rules'] if kind=='usage' else ['D12.contract_version_ref','D12.currency_amount_basis','D12.stage_terms']
    if kind in ['uat','completion']:keys+=['D12.'+kind+'_billing_predicate_ref']
    states,values,findings=policies(cov.case,keys)
    if not coverage_current(cov):findings.append('Coverage has a newer immutable version')
    snapshot={'implementation':'billing-preparation/v1','coverage':cov.pk,'coverage_version':cov.version,'coverage_evidence_hash':cov.evidence.sha256,
        'policies':states,'usage':usage.pk if usage else None,'usage_hash':usage.source_sha256 if usage else None,'usage_context':usage.source_context if usage else None,
        'handoff':handoff.pk if handoff else None,'handoff_payload_hash':digest(handoff.payload) if handoff else None}
    if usage:
        from apps.baas.models import PartnerBillingImport
        if PartnerBillingImport.objects.filter(usage=usage).exists():
            from apps.baas.partner_operations import meter_origin
            try:snapshot['partner_meter_origin']=meter_origin(usage)
            except (ValidationError,PermissionDenied) as exc:
                snapshot['partner_meter_origin']={'status':'held'};findings.append('Partner meter source requires reconciliation: '+str(exc))
    if kind!='usage':
        from apps.pmo.models import Baseline
        b=Baseline.objects.filter(case=cov.case).first()
        snapshot['signed_baseline']=b.signed_id if b else None
    return snapshot,values,findings

def calculate(cov,kind,usage,handoff,values,findings):
    lines=[];due=None
    if kind=='usage':
        findings+=list(usage.findings)
        method=values.get('D08.tax_tier_rounding_rules',[None])[0]
        rules=values.get('D08.effective_price_rule_refs',[])
        for row in usage.rows:
            matches=[r for r in rules if r['coverage_id']==cov.pk and r['unit']==row['unit'] and r['from_period']<=row['period']<=r['to_period']]
            r=matches[0] if len(matches)==1 else None
            figures=price(row['quantity'],r['rate'],method) if r and method else {'net':None,'tax':None,'total':None,'raw_net':None}
            if row['quantity'] is None:findings.append(f"Line {row['line']}: quantity unknown")
            if not r:findings.append(f"Line {row['line']}: exact price rule missing or ambiguous")
            lines.append(dict(figures,transaction_id=row['transaction_id'],period=row['period'],quantity=row['quantity'],unit=row['unit'],
                rule=r['key'] if r else None,rate=r['rate'] if r else None))
    else:
        terms=[v for v in values.get('D12.stage_terms',[]) if v['coverage_id']==cov.pk and v['stage']==kind]
        term=terms[0] if len(terms)==1 else None
        if not term:findings.append('Exact contract stage terms missing')
        amount=term['amount'] if term else None;due=term['due_date'] if term else None
        if amount is None:findings.append('Stage amount unknown')
        if due is None:findings.append('Stage due date unknown')
        for key in ['D12.contract_version_ref','D12.currency_amount_basis']:
            v=values.get(key,[None])[0]
            if v and v['coverage_id']!=cov.pk:findings.append(key+': belongs to different contract coverage version')
        basis=values.get('D12.currency_amount_basis',[None])[0]
        if basis and amount is not None:
            with localcontext() as ctx:
                ctx.prec=512
                if Decimal(amount)!=Decimal(amount).quantize(Decimal(1).scaleb(-basis['decimal_places'])):findings.append('Stage amount exceeds configured precision')
        if kind!='signed_sow':
            predicate=values.get('D12.'+kind+'_billing_predicate_ref',[None])[0]
            if not handoff:findings.append('Exact PMO completion handoff required')
            elif not predicate or predicate['coverage_id']!=cov.pk or handoff.milestone.name!=predicate['milestone_name']:findings.append('PMO milestone does not satisfy configured stage predicate')
        elif handoff:findings.append('Opening stage uses exact signed baseline, not a substitute milestone')
        lines=[{'stage':kind,'total':amount}]
    with localcontext() as ctx:
        ctx.prec=512
        total=None if findings or any(x['total'] is None for x in lines) else number(sum((Decimal(x['total']) for x in lines),Decimal(0)))
    return {'status':'held' if findings else 'prepared','findings':findings,'lines':lines,'total':total,'currency':cov.currency,'amount_basis':cov.amount_basis,
        'coverage_completeness':cov.completeness,'usage_completeness':(usage.source_context or {}).get('completeness','unknown') if usage else None,'due_date':due,'invoice_issued':False,'ledger_posted':False,'cash_received':False,'release_authorized':False}

@transaction.atomic
def prepare(actor,case_id,coverage_id,kind,usage_id,handoff_id,expected):
    case=lock_case(actor,case_id,'finance.billing.prepare',expected);require(actor,case,'finance.read')
    if kind not in ['usage','signed_sow','uat','completion']:raise ValidationError('Unknown billing preparation kind')
    cov=exact(case,BillingCoverage,coverage_id);usage=exact(case,BillingUsage,usage_id) if usage_id else None;handoff=exact(case,Handoff,handoff_id) if handoff_id else None
    if (kind=='usage')!=(usage is not None) or usage and usage.coverage_id!=cov.pk or kind=='usage' and handoff:raise ValidationError('Select only exact usage for usage preparation, and optional exact PMO handoff for a stage')
    snapshot,values,findings=inputs(cov,kind,usage,handoff)
    result=calculate(cov,kind,usage,handoff,values,findings)
    operation_key=digest({'case':str(case.pk),'kind':kind,'snapshot':snapshot})
    old=BillingPreparation.objects.filter(operation_key=operation_key).first()
    if old:return old
    record=BillingPreparation.objects.create(case=case,coverage=cov,usage=usage,handoff=handoff,kind=kind,snapshot=snapshot,result=result,operation_key=operation_key,actor=actor)
    event(actor,case,'billing.prepared',preparation=record.pk,status=result['status']);bump(case);return record

def ensure_current(record):
    require(record.actor,record.case,'finance.billing.prepare');require(record.actor,record.case,'finance.read')
    snapshot,values,findings=inputs(record.coverage,record.kind,record.usage,record.handoff)
    if snapshot!=record.snapshot or calculate(record.coverage,record.kind,record.usage,record.handoff,values,findings)!=record.result:raise ValidationError('Billing preparation is stale; rebuild against current exact evidence and policy')
    if record.result['status']!='prepared':raise ValidationError(record.result['findings'])


def coverage_inventory(cov):
    """Expected periods versus usable usage evidence; never labels them invoiced/paid."""
    year,month=map(int,cov.from_period.split('-'));periods=[]
    for _ in range(120):
        p=f'{year:04d}-{month:02d}'
        if p>cov.to_period:break
        periods.append({'period':p,'usage_batches':[],'status':'missing_usage'})
        year,month=(year+1,1) if month==12 else (year,month+1)
    by={p['period']:p for p in periods}
    for batch in BillingUsage.objects.filter(coverage=cov).order_by('pk'):
        valid=not batch.findings and all(r['quantity'] is not None for r in batch.rows)
        for period in {r['period'] for r in batch.rows}:
            if period not in by:continue
            item=by[period];item['usage_batches'].append(batch.pk)
            if valid:item['status']='usage_present_'+(batch.source_context or {}).get('completeness','unknown')
            elif item['status']=='missing_usage':item['status']='usage_exceptions'
    return periods
