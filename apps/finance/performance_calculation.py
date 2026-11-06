from decimal import Decimal,localcontext
from .rules import number,total,ROUNDING
from .performance_math import compare


def calculate(method,request,periods,prior,budget,snapshot):
    expected=method['periods'][:method['periods'].index(request['cutoff'])+1]
    findings=[];currency=None;basis=None;contracts={};compatible={'actual':True,'prior':True}
    for name,items in [('actual',periods),('prior',prior)]:
        month_ids=[p.manifest['period'] for p in items]
        if len(set(month_ids))!=len(month_ids):findings.append(name+': duplicate reporting month')
        if name=='actual' and sorted(month_ids)!=expected:findings.append('Actual included-month inventory differs from the explicit fiscal prefix')
        if name=='prior' and (items or method['prior_required']) and len(items)!=len(expected):findings.append('Explicit prior comparison inventory needs the same number of months')
        if name=='prior' and items and max(month_ids)>=expected[0]:findings.append('Prior comparison periods must precede the actual reporting window')
        for period in items:
            m=period.manifest
            if m['entity']!=method['entity']:findings.append(name+': entity mismatch');compatible[name]=False
            if currency is None:currency=m['currency']
            elif currency!=m['currency']:findings.append(name+': currency mismatch; no conversion');compatible[name]=False
            if basis is None:basis=period.run.source.accounting_basis
            elif basis!=period.run.source.accounting_basis:findings.append(name+': accounting basis mismatch; no conversion');compatible[name]=False
            for metric in method['metrics']:
                contract=m['metric_contracts'].get(metric['key'])
                old=contracts.setdefault(metric['key'],contract)
                if contract is None or contract!=old:findings.append('Incompatible/missing formula definition for '+metric['key'])
    if not periods:findings.append('No actual monthly inventory selected')
    if budget is None:findings.append('No explicit budget version selected')
    elif not snapshot['budget_review']['valid']:findings.append('Budget is incomplete, superseded or lacks current configured review')
    budget_basis_valid=budget is not None and budget.accounting_basis is not None and budget.accounting_basis==basis
    if not budget_basis_valid:findings.append('Budget accounting basis is unknown or incompatible; no conversion')
    if budget and (budget.cadence=='monthly')!=(method['budget_method']=='monthly_exact'):findings.append('Budget cadence and approved method disagree')
    scopes=([('company',None)] if method['include_company'] else [])+[('bu',key) for key in method['bu_keys']]
    company={};by_bu={key:{} for key in method['bu_keys']};chart=[]
    ordered=sorted(periods,key=lambda p:p.manifest['period'])
    prior_ordered=sorted(prior,key=lambda p:p.manifest['period'])
    with localcontext() as context:
        context.prec=512
        for scope,bu in scopes:
            target=company if scope=='company' else by_bu[bu]
            for metric in method['metrics']:
                key=metric['key'];unit=metric['unit'];line_findings=[]
                def actual_values(items,required_months):
                    values=[]
                    for period in items:
                        data=period.manifest['result']['company'] if scope=='company' else period.manifest['result']['by_bu'].get(bu,{})
                        value=data.get(key)
                        if not value or value['unit']!=unit:line_findings.append('Missing metric/BU or incompatible unit');values.append(None)
                        else:values.append(value['value'])
                    if len(values)!=required_months or any(v is None for v in values):return None
                    return number(total(values)) if metric['aggregation']=='sum' else values[-1]
                actual=actual_values(ordered,len(expected)) if compatible['actual'] and sorted(p.manifest['period'] for p in ordered)==expected else None
                previous=actual_values(prior_ordered,len(expected)) if compatible['prior'] and len(prior_ordered)==len(expected) else None
                selected_budget=[]
                for month in expected:
                    matches=[] if budget is None else [r for r in budget.rows if r['entity']==method['entity'] and r['scope']==scope and r['bu']==(bu or '') and r['metric']==key and r['period']==(month if budget.cadence=='monthly' else method['year_key'])]
                    if len(matches)!=1 or matches[0]['amount'] is None or matches[0]['currency']!=currency or matches[0]['unit']!=unit:
                        selected_budget.append(None);line_findings.append('Missing/duplicate/incompatible budget dimension');continue
                    amount=Decimal(matches[0]['amount'])
                    if budget.cadence=='annual':
                        if metric['aggregation']=='last_period':
                            selected_budget.append(None);line_findings.append('Annual stock budget needs a separately approved closing-period method');continue
                        weight=next(r['weight'] for r in method['annual_weights'] if r['period']==month)
                        amount*=Decimal(weight)
                    selected_budget.append(number(amount))
                comparable=None if not budget_basis_valid or not selected_budget or any(x is None for x in selected_budget) else number(total(selected_budget)) if metric['aggregation']=='sum' else selected_budget[-1]
                if comparable is not None:comparable=number(Decimal(comparable).quantize(Decimal(1).scaleb(-method['decimal_places']),rounding=ROUNDING[method['rounding']]))
                values=compare(actual,comparable,previous,method)
                values.update(unit=unit,rule_key=key,label=metric['label'],aggregation=metric['aggregation'],findings=line_findings)
                if actual is None or comparable is None or method['prior_required'] and previous is None:line_findings.append('Required comparison input unknown')
                target[key]=values
                findings.extend((bu or 'company')+'/'+key+': '+x for x in line_findings)
                chart.append({'scope':scope,'bu':bu,'metric':key,'label':metric['label'],'unit':unit,'actual':actual,'budget':comparable,'prior':previous})
    return {'status':'needs_attention' if findings else 'complete','findings':sorted(set(findings)),'company':company,'by_bu':by_bu,'chart':chart,
        'entity':method['entity'],'currency':currency,'accounting_basis':basis,'year_key':method['year_key'],'cutoff':request['cutoff'],'period':request['cutoff'],
        'included_periods':expected,'actual_manifest':[{'id':p.pk,'period':p.manifest['period'],'predecessor':p.predecessor_id,'hash':p.manifest['result_hash']} for p in ordered],
        'prior_manifest':[{'id':p.pk,'period':p.manifest['period'],'hash':p.manifest['result_hash']} for p in prior_ordered],
        'budget_id':budget.pk if budget else None,'budget_version':budget.number if budget else None,'budget_method':method['budget_method'],
        'method':method,'ledger_posted':False,'historical_values_rewritten':False}
