"""Finance-owned previews and human review. No ledger, invoice or payment effects."""
import hashlib,json,re
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.policy.models import Configuration
from apps.policy.services import active_component,reference_values,decision_authority,resolve
from apps.pmo.services import subject
from .models import FinancialImport,FinanceSource,FinanceAdjustment,FinanceRun,FinanceReview
from .rules import decimal,number,total

MAP_COMPONENTS=['D06.source_schema_ref','D06.unit_sign_currency_period','D06.account_bu_maps']
ALLOCATION_COMPONENTS=['D10.report_category_effective_dates','D07.allocation_pool_rules','D07.rounding_residual_rule_id',
    'D07.authorized_input_refs','D07.join_overlap_rule_id','D07.effective_membership_ref']
PURPOSE={'D06.account_bu_maps':'mapping','D10.report_category_effective_dates':'mapping','D06.rule_oracle_refs':'formula',
    'D07.allocation_pool_rules':'allocation','D07.rounding_residual_rule_id':'allocation'}

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def note(value):
    if not isinstance(value,str) or not value.strip() or len(value)>4000:raise ValidationError('An evidenced explanation of at most 4000 characters is required')

def source_for(case,pk):
    s=FinanceSource.objects.select_related('batch__evidence','case').filter(case=case,pk=pk).first()
    if not s or s.batch.contexts.order_by('-pk').first().pk!=s.pk:raise ValidationError('Select this case current source context for the exact import')
    return s

@transaction.atomic
def capture_source(actor,case_id,batch_id,entity,accounting_basis,extracted_at,completeness,control_total,evidence_id,expected):
    case=lock_case(actor,case_id,'finance.source',expected)
    batch=FinancialImport.objects.filter(case=case,pk=batch_id).first()
    if not batch or not isinstance(entity,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',entity):raise ValidationError('Select this case import and explicit entity identifier')
    if not isinstance(accounting_basis,str) or not accounting_basis.strip() or len(accounting_basis)>100:raise ValidationError('State the actual accounting basis')
    if not extracted_at or timezone.is_naive(extracted_at) or extracted_at>timezone.now():raise ValidationError('Actual aware extraction/as-of time must not be in the future')
    if completeness not in ['complete','partial','unknown']:raise ValidationError('Declare source completeness explicitly')
    amount=None if control_total is None else number(decimal(control_total))
    s=FinanceSource.objects.create(case=case,batch=batch,entity=entity,accounting_basis=accounting_basis,extracted_at=extracted_at,
        completeness=completeness,control_total=amount,evidence=subject(case,evidence_id,'finance_source'),actor=actor)
    event(actor,case,'finance.source_context',source=s.pk,batch=batch.pk);bump(case);return s

def review_authority(actor,case,purpose,role,verdict,preparer_id,*,delegated=False,invoice=None):
    if type(delegated) is not bool:raise ValidationError('Delegated Finance authority mode must be boolean')
    matrix=active_component('D05.decision_action_matrix',case)
    matches=[x for x in reference_values(matrix)[0].get('finance',[]) if x['purpose']==purpose and x['role']==role and verdict in x['actions']]
    if len(matches)!=1:raise PermissionDenied('Configure Finance review authority for '+purpose+' / '+verdict)
    entry=matches[0]
    if actor.pk==preparer_id and not entry['allow_preparer_review']:raise PermissionDenied('Current Finance policy requires a different reviewer')
    context=None
    if delegated:
        if purpose!='invoice' or invoice is None or invoice.case_id!=case.pk or invoice.actor_id!=preparer_id:
            raise ValidationError('Delegated Finance review requires its exact native invoice')
        from .invoices import current
        current(invoice)
        context={'decision_type':'finance.invoice.review','case_ref':str(case.pk),'action':verdict,
            'currency':invoice.currency,'amount':invoice.payload['amount']}
    authority=dict(decision_authority(actor,case,role,delegated=delegated,delegation_context=context),**{matrix.component:matrix.pk,'finance_review_rule':entry})
    if purpose=='invoice' and invoice is not None:
        from apps.workflows.factory_routing import availability_authority
        availability=availability_authority(invoice,actor)
        if availability is not None:authority['factory_reviewer_availability']=availability
    if purpose=='source':
        for key in ['D06.source_schema_ref','D06.unit_sign_currency_period']:authority[key]=active_component(key,case).pk
    return authority

def current_review(case,purpose,**target):
    r=FinanceReview.objects.filter(case=case,purpose=purpose,**target).order_by('-pk').first()
    if not r:return {'id':None,'verdict':'missing','valid':False}
    valid=False;finding=''
    try:
        require(r.actor,case,'finance.review')
        item=r.source or r.configuration or r.adjustment or r.run
        preparer=item.created_by_id if r.configuration_id else item.actor_id
        current=review_authority(r.actor,case,purpose,r.role,r.verdict,preparer)
        # Unrelated D05 namespaces can change without manufacturing a new Finance decision.
        strip=lambda v:{k:x for k,x in v.items() if k!='D05.decision_action_matrix'}
        valid=r.verdict=='approve' and strip(current)==strip(r.authority)
    except (ValidationError,PermissionDenied) as exc:finding=str(exc)
    return {'id':r.pk,'verdict':r.verdict,'valid':valid,'finding':finding}

def config_snapshot(case,components):
    states={};configs={}
    for key in components:
        resolved=resolve(key,case);c=resolved.configuration
        states[key]={'status':resolved.status,'id':c.pk if c else None,'revision':c.revision if c else None}
        if c:configs[key]=c
    reviews={key:current_review(case,PURPOSE[key],configuration=c) for key,c in configs.items() if key in PURPOSE}
    return states,configs,reviews

def _stage_components(source,kind,parent,request):
    components=MAP_COMPONENTS if kind=='mapping' else ['D06.rule_oracle_refs']
    if kind=='allocation':
        from .mapping import effective
        selected=[r for r in parent.result['rows'] if r['metric'] in request['metrics'] and r['treatment']!='company']
        components=['D10.report_category_effective_dates'] if selected else []
        pools={r['pool'] for r in selected if r['treatment']=='pool'}
        if pools:
            components+=['D07.allocation_pool_rules','D07.rounding_residual_rule_id']
            resolved=resolve('D07.allocation_pool_rules',source.case)
            if resolved.configuration and any(r['pool'] in pools and r['method']=='headcount_weighted' for r in effective(reference_values(resolved.configuration),source.entity,parent.result['period'])):
                components+=['D07.authorized_input_refs','D07.join_overlap_rule_id','D07.effective_membership_ref']
    return components

def stage_policy_components(actor,source,kind,parent,request):
    """Authorised policy identifiers only; no calculation or private HR basis access."""
    source_for(source.case,source.pk);require(actor,source.case,'case.read');require(actor,source.case,'finance.read')
    if parent:ensure_current(parent)
    if kind not in ['mapping','allocation','formula']:raise ValidationError('Known Finance preparation stage required')
    return _stage_components(source,kind,parent,request)

def stage_snapshot(actor,source,kind,parent,request):
    source_for(source.case,source.pk);require(actor,source.case,'finance.calculate')
    if parent:ensure_current(parent)
    components=_stage_components(source,kind,parent,request)
    states,configs,reviews=config_snapshot(source.case,components)
    hr_basis_access=None
    if kind=='allocation' and 'D07.effective_membership_ref' in configs:
        v=reference_values(configs['D07.effective_membership_ref'])[0]
        if 'snapshot_id' in v:
            from .hrfinance import allocation_basis
            try:
                b=allocation_basis(actor,source.case,v);hr_basis_access={'snapshot_id':b['snapshot_id'],'receipt_id':b['receipt_id'],'status':'available'}
            except (ValidationError,PermissionDenied):hr_basis_access={'snapshot_id':v['snapshot_id'],'status':'held'}
    adjustments=[]
    if kind=='mapping':
        for pk in request['adjustment_ids']:
            adj=FinanceAdjustment.objects.filter(source=source,pk=pk).first()
            if not adj or FinanceAdjustment.objects.filter(source=source,reference=adj.reference).order_by('-number').first().pk!=adj.pk:raise ValidationError('Select only current adjustments from this source context')
            decision=current_review(source.case,'adjustment',adjustment=adj)
            if not decision['valid']:raise ValidationError('Selected reporting adjustment needs current configured human review')
            adjustments.append({'id':adj.pk,'review':decision})
    return {'source':source.pk,'source_hash':source.batch.source_sha256,'source_evidence':source.evidence_id,
        'parent':{'id':parent.pk,'key':parent.operation_key} if parent else None,'policies':states,'reviews':reviews,
        'source_review':current_review(source.case,'source',source=source),'adjustments':adjustments,
        **({'formula_result_implementation':'finance-note-lineage/v1'} if kind=='formula' else {}),**({'hr_basis_access':hr_basis_access} if hr_basis_access else {})},configs

def ensure_current(run):
    parent=run.parent
    snapshot,_=stage_snapshot(run.actor,run.source,run.kind,parent,run.request)
    if snapshot!=run.snapshot:raise ValidationError('Source, policy, review or authority changed; rebuild the exact Finance preview')
    return run

def store(actor,case,source,kind,parent,request,snapshot,result):
    key=digest({'actor':actor.pk,'case':str(case.pk),'source':source.pk,'kind':kind,'parent':parent.pk if parent else None,'request':request,'snapshot':snapshot})
    old=FinanceRun.objects.filter(operation_key=key).first()
    if old:return old
    run=FinanceRun.objects.create(case=case,source=source,parent=parent,kind=kind,request=request,snapshot=snapshot,result=result,operation_key=key,actor=actor)
    event(actor,case,'finance.preview_created',run=run.pk,kind=kind,operation_key=key,status=result['status']);bump(case);return run

@transaction.atomic
def map_source(actor,case_id,source_id,adjustment_ids,expected):
    case=lock_case(actor,case_id,'finance.calculate',expected);s=source_for(case,source_id)
    if not isinstance(adjustment_ids,list) or len(adjustment_ids)>100 or any(type(pk) is not int for pk in adjustment_ids) or len(set(adjustment_ids))!=len(adjustment_ids):raise ValidationError('Select a unique bounded adjustment inventory')
    request={'adjustment_ids':sorted(adjustment_ids)};snapshot,configs=stage_snapshot(actor,s,'mapping',None,request)
    for component in MAP_COMPONENTS:
        if component not in configs:active_component(component,case)
    from adapters.finance_analysis import LocalFinanceSourceAdapter
    from .mapping import map_rows
    result=map_rows(s,LocalFinanceSourceAdapter().read(s),configs,adjustment_ids)
    return store(actor,case,s,'mapping',None,request,snapshot,result)

@transaction.atomic
def allocate(actor,case_id,parent_id,metrics,expected):
    case=lock_case(actor,case_id,'finance.calculate',expected);parent=FinanceRun.objects.filter(case=case,pk=parent_id,kind='mapping').first()
    if not parent:raise ValidationError('Select this case exact mapping preview')
    if not isinstance(metrics,list) or not metrics or any(x not in ['revenue','direct_cost','staff_cost','opex','other'] for x in metrics) or len(set(metrics))!=len(metrics):raise ValidationError('Select explicit unique BU metric scope')
    request={'metrics':sorted(metrics)};snapshot,configs=stage_snapshot(actor,parent.source,'allocation',parent,request)
    from .allocation import allocate_rows
    result=allocate_rows(parent,metrics,configs,actor)
    return store(actor,case,parent.source,'allocation',parent,request,snapshot,result)

@transaction.atomic
def calculate(actor,case_id,parent_id,expected):
    case=lock_case(actor,case_id,'finance.calculate',expected);parent=FinanceRun.objects.filter(case=case,pk=parent_id,kind__in=['mapping','allocation']).first()
    if not parent:raise ValidationError('Select an exact mapping or allocation preview')
    request={};snapshot,configs=stage_snapshot(actor,parent.source,'formula',parent,request)
    if 'D06.rule_oracle_refs' not in configs:active_component('D06.rule_oracle_refs',case)
    from .mapping import calculate_formulas
    result=calculate_formulas(parent,configs['D06.rule_oracle_refs'])
    return store(actor,case,parent.source,'formula',parent,request,snapshot,result)

@transaction.atomic
def adjustment(actor,case_id,source_id,reference,kind,lines,evidence_id,note_text,expected):
    case=lock_case(actor,case_id,'finance.adjust',expected);s=source_for(case,source_id);note(note_text)
    if not isinstance(reference,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',reference) or kind not in ['additive','reclassification']:raise ValidationError('Select an explicit reporting-adjustment reference and kind')
    if not isinstance(lines,list) or not 1<=len(lines)<=100:raise ValidationError('Select 1–100 exact account adjustments')
    for row in lines:
        if not isinstance(row,dict) or set(row)!={'account','amount'} or not isinstance(row['account'],str) or not row['account'].strip():raise ValidationError('Each reporting adjustment needs an account and exact amount')
        decimal(row['amount'])
    if kind=='reclassification' and total(x['amount'] for x in lines)!=0:raise ValidationError('A reporting reclassification must conserve the source total')
    a=FinanceAdjustment.objects.create(source=s,reference=reference,number=FinanceAdjustment.objects.filter(source=s,reference=reference).count()+1,kind=kind,lines=lines,
        evidence=subject(case,evidence_id,'finance_adjustment'),note=note_text,actor=actor)
    event(actor,case,'finance.reporting_adjustment',adjustment=a.pk,ledger_posted=False);bump(case);return a

def certification_findings(run):
    ensure_current(run);findings=[];cursor=run
    while cursor:
        if cursor.result['status']!='complete':findings.append(f'{cursor.kind} #{cursor.pk} contains unknowns, unallocated values or source exceptions')
        if not cursor.snapshot['source_review']['valid']:findings.append('Current Finance source acceptance is missing')
        for key,review in cursor.snapshot['reviews'].items():
            # Headcount policy is independently captured/authorized; rule approvals cover calculations.
            if cursor.kind=='allocation' and key not in cursor.result.get('used_policy_components',[]):continue
            if not review['valid']:findings.append('Current Finance rule review missing: '+key)
        cursor=cursor.parent
    if run.source.completeness!='complete':findings.append('Source inventory completeness is not explicitly complete')
    mapping=run
    while mapping.parent_id:mapping=mapping.parent
    c=active_component('D06.unit_sign_currency_period',run.case);controls=reference_values(c)[0].get('report_controls')
    if not controls:findings.append('Configure explicit report source-total requirement and tolerance (source conventions v2)')
    else:
        difference=mapping.result['source_control']['difference']
        if mapping.source.control_total is None and controls['require_source_total']:findings.append('Required source control total is unknown')
        if difference is not None and abs(decimal(difference))>decimal(controls['tolerance'],nonnegative=True):findings.append('Source control-total difference exceeds configured tolerance')
    if controls and run.result.get('by_bu'):
        tolerance=controls.get('bu_tolerance')
        if tolerance is None:findings.append('Configure the BU/company comparison tolerance')
        else:
            for key,comparison in run.result.get('bu_comparison',{}).items():
                if comparison['difference'] is None or abs(decimal(comparison['difference']))>decimal(tolerance,nonnegative=True):findings.append('BU/company comparison fails for '+key)
    return findings

@transaction.atomic
def review(actor,case_id,purpose,target_id,role,verdict,evidence_id,note_text,expected):
    case=lock_case(actor,case_id,'finance.review',expected);note(note_text)
    if purpose not in ['source','mapping','formula','allocation','adjustment','output'] or verdict not in ['approve','return','reject']:raise ValidationError('Select a typed Finance review purpose and verdict')
    if purpose=='source':item=source_for(case,target_id);target={'source':item}
    elif purpose=='adjustment':
        item=FinanceAdjustment.objects.filter(pk=target_id,source__case=case).first();target={'adjustment':item}
        if item:
            source_for(case,item.source_id)
            if FinanceAdjustment.objects.filter(source=item.source,reference=item.reference).order_by('-number').first().pk!=item.pk:raise ValidationError('Select the latest adjustment revision')
    elif purpose=='output':
        item=FinanceRun.objects.filter(case=case,pk=target_id,kind='formula').first();target={'run':item}
        if item:
            ensure_current(item)
            if verdict=='approve':
                findings=certification_findings(item)
                if findings:raise ValidationError(findings)
    else:
        item=Configuration.objects.filter(case=case,pk=target_id,component__in=[k for k,v in PURPOSE.items() if v==purpose]).first();target={'configuration':item}
        if item and active_component(item.component,case).pk!=item.pk:raise ValidationError('Review the exact active Finance configuration version')
    if item is None:raise ValidationError('Review target must match this case and Finance purpose')
    preparer=item.created_by_id if 'configuration' in target else item.actor_id
    authority=review_authority(actor,case,purpose,role,verdict,preparer)
    result=FinanceReview.objects.create(case=case,purpose=purpose,role=role,verdict=verdict,authority=authority,evidence=subject(case,evidence_id,'finance_review'),note=note_text,actor=actor,**target)
    event(actor,case,'finance.review_recorded',review=result.pk,purpose=purpose,verdict=verdict);bump(case);return result
