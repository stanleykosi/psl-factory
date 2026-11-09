from decimal import Decimal,localcontext
from django.core.exceptions import ValidationError,PermissionDenied
from apps.policy.services import reference_values
from .mapping import effective
from .rules import decimal,number,total,proportional

CATALOG='D10.report_category_effective_dates'
POOLS='D07.allocation_pool_rules'
ROUNDING='D07.rounding_residual_rule_id'
INPUTS='D07.authorized_input_refs'
JOIN='D07.join_overlap_rule_id'
MEMBERSHIP='D07.effective_membership_ref'

def headcount_weights(source,period,eligible,configs,actor=None):
    if any(k not in configs for k in [INPUTS,JOIN,MEMBERSHIP]):raise ValidationError('Configure authorized HR/Finance basis, effective membership and overlap/period treatment')
    basis=reference_values(configs[MEMBERSHIP])[0];join=reference_values(configs[JOIN])[0]
    if basis['entity']!=source.entity or basis['period']!=period:raise ValidationError('Allocation basis entity/period differs from the source')
    authorized=reference_values(configs[INPUTS])
    hr_basis='snapshot_id' in basis
    if hr_basis:
        if actor is None:raise ValidationError('HR basis requires the actual authorised Finance caller')
        if not any(x==basis for x in authorized):raise ValidationError('Exact HR snapshot is not an authorised allocation input')
        if join['weight_semantics']!='unit_per_subject':raise ValidationError('This HR interface supplies unit headcount only; FTE is not inferred')
        from .hrfinance import allocation_basis
        try:basis=allocation_basis(actor,source.case,basis)
        except PermissionDenied:raise ValidationError('Exact HR recipient access is unavailable; headcount pool held')
    if not hr_basis and not any(x['entity']==source.entity and x['period']==period and x['evidence_id']==basis['evidence_id'] for x in authorized):raise ValidationError('This exact basis evidence is not an authorized input')
    if basis['completeness']!='complete':raise ValidationError('Headcount inventory completeness remains unknown or partial')
    weights={key:Decimal(0) for key in eligible}
    for row in basis['rows']:
        if row['bu'] not in eligible:continue
        if row['weight'] is None:raise ValidationError('Unknown headcount/FTE weight; not zero')
        weight=decimal(row['weight'],nonnegative=True)
        if join['weight_semantics']=='unit_per_subject' and weight!=1:raise ValidationError('Headcount policy requires one unit per included subject')
        with localcontext() as context:
            context.prec=512;weights[row['bu']]+=weight
    lineage={'basis_evidence_id':basis.get('evidence_id'),'basis_as_of':basis['as_of'],'period_basis':join['period_basis'],
        'weights':{key:number(value) for key,value in weights.items()},'external_authenticity_verified':False}
    if hr_basis:lineage.update(hr_snapshot_id=basis['snapshot_id'],membership_bu_keys=sorted({r['bu'] for r in basis['rows']},key=str))
    return weights,lineage

def allocate_rows(parent,metrics,configs,actor=None):
    data=parent.result;period=data['period'];entity=data['entity'];source=parent.source
    catalog=effective(reference_values(configs[CATALOG]),entity,period) if CATALOG in configs else []
    bus=sorted(x['key'] for x in catalog)
    rules=effective(reference_values(configs[POOLS]),entity,period) if POOLS in configs else []
    rounding=reference_values(configs[ROUNDING])[0] if ROUNDING in configs else None
    output=[];findings=[];used=set()
    for row in data['rows']:
        if row['metric'] not in metrics:continue
        record=dict(row,allocations={},unallocated=row['amount'],residual=None,denominator=None,basis=None,status='held')
        try:
            if row['amount'] is None:raise ValidationError('Unknown source amount; allocation and conservation are unknown')
            amount=decimal(row['amount'])
            if row['treatment']=='company':
                record.update(status='company_only',unallocated='0',residual='0',company_only=number(amount));output.append(record);continue
            used.add(CATALOG)
            if not bus:raise ValidationError('No configured effective BU catalogue for this entity/period')
            if row['treatment']=='direct':
                if row['bu'] not in bus:raise ValidationError('Direct BU is not in the effective catalogue')
                record.update(status='allocated',allocations={row['bu']:number(amount)},unallocated='0',residual='0')
            elif row['treatment']=='pool':
                used.update([POOLS,ROUNDING]);matching=[r for r in rules if r['pool']==row['pool'] and r['metric']==row['metric']]
                if len(matching)!=1 or rounding is None:raise ValidationError('Configure exactly one effective pool rule and explicit rounding/residual treatment')
                rule=matching[0]
                if row['account'] in rule['excluded_accounts']:raise ValidationError('Account is explicitly excluded from this pool; it remains unallocated')
                eligible=[bu for bu in bus if bu not in rule['excluded_bu_keys']]
                if set(rule['excluded_bu_keys'])-set(bus):raise ValidationError('Pool exclusions reference unknown BUs')
                if rule['method']=='fixed_weights':
                    if any(x['bu'] not in eligible for x in rule['weights']):raise ValidationError('Fixed weights reference an unknown/excluded BU')
                    if 'weight_contract' in rule:
                        from apps.policy.allocation_coverage import checked_weights
                        record['weight_contract']=rule['weight_contract']
                        weights=checked_weights(rule['weights'],rule['weight_contract'])
                    else:weights={x['bu']:decimal(x['weight'],nonnegative=True) for x in rule['weights']}
                    basis={'method':'explicit_fixed_weights','weight_contract':rule.get('weight_contract'),'weight_semantics':'explicit_contract' if 'weight_contract' in rule else 'legacy_relative_v1','weights':{k:number(v) for k,v in weights.items()}}
                else:
                    used.update([INPUTS,JOIN,MEMBERSHIP]);weights,basis=headcount_weights(source,period,eligible,configs,actor)
                    unknown_bus=set(basis['membership_bu_keys'])-set(bus) if 'hr_snapshot_id' in basis else {x['bu'] for x in reference_values(configs[MEMBERSHIP])[0]['rows']}-set(bus)
                    if unknown_bus:raise ValidationError('Headcount snapshot contains unknown BU membership; resolve before denominator use')
                allocations,residual,denominator=proportional(amount,weights,rounding)
                record.update(status='allocated' if residual==0 else 'residual_held',allocations={k:number(v) for k,v in allocations.items()},
                    residual=number(residual),unallocated='0',denominator=number(denominator),basis=basis,pool_rule=rule['key'])
                if residual:findings.append(f"{row['source_line']}: residual held under configured policy")
            else:raise ValidationError('Missing attribution treatment')
        except ValidationError as exc:
            record['allocation_findings']=exc.messages;findings.extend(f"{row['source_line']}: {message}" for message in exc.messages)
        output.append(record)
    conservation={}
    with localcontext() as context:
        context.prec=512
        for metric in metrics:
            selected=[r for r in output if r['metric']==metric];source_total=total(r['amount'] for r in selected)
            if not selected:conservation[metric]={'source':None,'allocated':None,'unallocated':None,'residual':None,'company_only':None,'conserved':None};findings.append('No source population for selected metric '+metric);continue
            allocated=sum((Decimal(x) for r in selected for x in r['allocations'].values()),Decimal(0))
            unknown=any(r['amount'] is None for r in selected)
            unallocated=None if unknown else sum((Decimal(r['unallocated']) for r in selected),Decimal(0))
            residual=None if unknown else sum((Decimal(r['residual'] or '0') for r in selected),Decimal(0))
            company=sum((Decimal(r.get('company_only','0')) for r in selected),Decimal(0))
            conserved=None if unknown else source_total==allocated+unallocated+residual+company
            conservation[metric]={'source':number(source_total),'allocated':number(allocated),'unallocated':number(unallocated),'residual':number(residual),'company_only':number(company),'conserved':conserved}
    return {'status':'complete' if not findings and parent.result['status']=='complete' else 'needs_attention','rows':output,'findings':findings,'conservation':conservation,
        'bu_keys':bus,'metrics':metrics,'used_policy_components':sorted(used),'entity':entity,'period':period,'currency':data['currency'],
        'unit':'major_currency','source_evidence_ids':data['source_evidence_ids'],'ledger_posted':False}
