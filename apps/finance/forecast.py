"""Versioned forecast assumptions and actual reconciliation; never money execution."""
import json,re
from decimal import Decimal,localcontext
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.identity.models import Grant
from apps.pmo.services import subject
from apps.policy.services import active_component,reference_values,resolve,decision_authority
from adapters.forecast import scenario as parse_scenario,actual as parse_actual,day
from .analysis import note,digest,review_authority
from .rules import decimal,number
from .models import ForecastScenario,ForecastRun,ForecastReview,ForecastActual,ForecastActualVerification,ForecastMatch,ForecastMatchReversal,InvoiceIssue,CashVerification,CashReversal
from . import receivables,cash,corrections

METHOD='D10.forecast_inclusion_rule_id'

def exact(case,model,pk):
    r=model.objects.filter(case=case,pk=pk).first()
    if not r:raise ValidationError('Select the exact forecast subject on this case')
    return r

def method(case):
    c=active_component(METHOD,case);return c,reference_values(c)[0]

def precise(amount,rule):
    if amount is None:return
    n=decimal(amount)
    with localcontext() as ctx:
        ctx.prec=512
        if n!=n.quantize(Decimal(1).scaleb(-rule['decimal_places'])):raise ValidationError('Forecast amount exceeds configured precision; no implicit rounding')

def amount_sum(values):
    with localcontext() as ctx:
        ctx.prec=512
        return sum(values,Decimal(0))

def root_of(s):return s.root or s
def direction(item):return 'outflow' if item['kind']=='outflow' else 'inflow'

def matched(root,key):
    with localcontext() as ctx:
        ctx.prec=512
        return sum((m.amount for m in active_matches().filter(root=root,item_key=key)),Decimal(0))

def active_matches():return ForecastMatch.objects.filter(reversal__isnull=True)

def residual(s,item):
    with localcontext() as ctx:
        ctx.prec=512
        return None if item['amount'] is None else decimal(item['amount'])-matched(root_of(s),item['key'])

def unmatched_actual(a,links):
    with localcontext() as ctx:
        ctx.prec=512
        return None if a.payload['amount'] is None else number(decimal(a.payload['amount'])-amount_sum(x.amount for x in links if x.actual_id==a.pk))

def actual_available(r):
    if r.lot_id:
        return not CashReversal.objects.filter(lot_id=r.lot_id).exists()
    return ForecastActualVerification.objects.filter(actual=r).exists()

def validate_inputs(case,v):
    if day(v['as_of'])>timezone.localdate():raise ValidationError('Forecast as-of is actual, not future')
    if v['months'][0]<v['as_of'][:7]:raise ValidationError('Forecast horizon cannot begin before its as-of month')
    if not set(o['account'] for o in v['openings']).issubset(v['coverage']['accounts']):raise ValidationError('Opening account is outside declared coverage')
    seen_issues=set()
    for o in v['openings']:
        proof=subject(case,o['evidence_id'],'forecast_opening')
        try:actual=json.loads(proof.body)
        except (ValueError,TypeError):raise ValidationError('Opening evidence must contain exact account/amount/date snapshot')
        if actual!={k:x for k,x in o.items() if k!='evidence_id'}:raise ValidationError('Opening balance differs from exact supplied evidence')
        if day(o['observed_on'])>day(v['as_of']):raise ValidationError('Opening observation is later than scenario as-of')
    for i in v['items']:
        subject(case,i['evidence_id'])
        if i['kind']=='receivable':
            issue=InvoiceIssue.objects.filter(pk=i['issue_id'],invoice__case=case).first()
            if not issue or i['issue_id'] in seen_issues:raise ValidationError('Select each exact captured receivable once')
            seen_issues.add(issue.pk)
            if issue.invoice.currency!=v['currency'] or issue.invoice.amount_basis!='gross_including_tax':raise ValidationError('Receivable currency/basis differs from scenario; no implicit FX')
            if i['amount'] is not None and decimal(i['amount'])>cash.open_amount(issue):raise ValidationError('Selected inflow exceeds current corrected receivable')

@transaction.atomic
def capture(actor,case_id,reference,evidence_id,reason,expected,parent_id=None):
    case=lock_case(actor,case_id,'finance.forecast.capture',expected);require(actor,case,'finance.read');note(reason)
    if not isinstance(reference,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',reference):raise ValidationError('Supply an explicit scenario reference')
    e=subject(case,evidence_id,'forecast_input');v=parse_scenario(e.body)
    parent=exact(case,ForecastRun,parent_id) if parent_id else None
    root=None
    if parent:
        approved(parent,current=False);c,m=method(case);root=root_of(parent.scenario)
        old=parent.scenario.payload
        if any(v[k]!=old[k] for k in ['entity','currency','basis']):raise ValidationError('Roll-forward preserves entity/currency/basis')
        if v['as_of']<=old['as_of'] or v['months'][0]<=old['months'][0]:raise ValidationError('Roll-forward advances actual as-of and horizon start')
        if v['months'][0]!=v['as_of'][:7]:raise ValidationError('Roll-forward starts in the new actual as-of month')
        source={i['key']:i for i in old['items']};new={i['key']:i for i in v['items']};roll={r['key']:r for r in v['rollover']}
        unresolved={k for k,i in source.items() if residual(parent.scenario,i) is None or residual(parent.scenario,i)>0}
        if set(roll)!=unresolved or set(new)!={k for k in unresolved if roll[k]['disposition']=='carry'}:raise ValidationError('Explicitly carry or cancel every unresolved item, and no other item')
        for k,i in new.items():
            if {x:y for x,y in i.items() if x!='expected_on'}!={x:y for x,y in source[k].items() if x!='expected_on'}:raise ValidationError('Roll-forward preserves original amount/due/source/owner; only expected date changes')
            if not i['expected_on'] or i['expected_on'][:7] not in v['months']:raise ValidationError('Carried items require an explicit new expected date within horizon')
        # A forecast close is never silently promoted to an actual opening.
        if {o['evidence_id'] for o in v['openings']} & {o['evidence_id'] for o in old['openings']}:raise ValidationError('Roll-forward requires fresh actual opening evidence')
    elif v['rollover']:raise ValidationError('Rollover dispositions require an exact prior reviewed run')
    # Residuals on rollover retain original selected amounts; the live balance may now be lower after actual allocation.
    if parent:
        check=dict(v,items=[i for i in v['items'] if i['kind']!='receivable']);validate_inputs(case,check)
    else:validate_inputs(case,v)
    s=ForecastScenario.objects.create(case=case,reference=reference,number=(ForecastScenario.objects.filter(case=case,reference=reference).count()+1),root=root,parent=parent,evidence=e,payload=v,reason=reason,actor=actor)
    event(actor,case,'forecast.captured',scenario=s.pk,parent=parent.pk if parent else None);bump(case);return s

def calculate(s):
    case=s.case;v=s.payload;findings=[]
    r=resolve(METHOD,case);c=r.configuration;m=reference_values(c)[0] if r.status=='ACTIVE' else None
    manifest={'implementation':'forecast/v1','scenario':s.pk,'source_hash':s.evidence.sha256,'method':{'status':r.status,'id':c.pk if c else None},'today':timezone.localdate().isoformat()}
    ledger,position=receivables.calculate(case,timezone.localdate());manifest['receivables']=ledger
    actuals=list(ForecastActual.objects.filter(case=case).order_by('pk'));links=list(active_matches().filter(case=case).order_by('pk'))
    manifest['actuals']=[[a.pk,actual_available(a),a.evidence.sha256] for a in actuals];manifest['verifications']=list(ForecastActualVerification.objects.filter(actual__case=case).values_list('pk',flat=True));manifest['matches']=list(ForecastMatch.objects.filter(case=case).values_list('pk',flat=True));manifest['match_reversals']=list(ForecastMatchReversal.objects.filter(match__case=case).values_list('pk',flat=True))
    if not m:findings.append('Configure '+METHOD+': '+r.status)
    if day(v['as_of'])!=timezone.localdate():findings.append('Scenario as-of is historical; capture a fresh actual-as-of scenario before new review/publication')
    openings={o['account']:o for o in v['openings']}
    if set(openings)!=set(v['coverage']['accounts']):findings.append('Opening account coverage is incomplete')
    for o in openings.values():
        if m:
            precise(o['amount'],m)
            if (day(v['as_of'])-day(o['observed_on'])).days>m['opening_max_age_days']:findings.append('Opening balance exceeds configured freshness: '+o['account'])
    coverage_partial=any(v['coverage'][k]!='complete' for k in ['inflows','outflows']) or bool(v['coverage']['omissions'])
    if coverage_partial:findings.append('Declared source coverage is partial or unknown; omitted activity is outside this forecast')
    selected={i['issue_id'] for i in v['items'] if i['kind']=='receivable'}
    omitted=[x for x in position['invoices'] if x['issue'] not in selected and (x['open'] is None or decimal(x['open'])!=0)]
    if omitted:findings.append('Captured receivables omitted from selected scenario')
    queues={k:position[k] for k in ['unbilled_drafts','uncertain_issuance','pending_corrections','uncertain_corrections','pending_cash_successors','reported_unverified','unmatched_cash']}
    queues['verified_unallocated_cash']=[g for g in position['groups'] if g['unallocated_cash'] is None or decimal(g['unallocated_cash'])>0]
    if any(queues.values()):findings.append('Captured unbilled, unmatched, unverified or uncertain activity remains outside selected cash assumptions')
    inputs=[];unscheduled=[];invalid_actuals=[a.pk for a in actuals if not actual_available(a) and any(x.actual_id==a.pk for x in links)]
    if invalid_actuals:findings.append('Matched actual source was reversed; reconciliation required')
    if any(not actual_available(a) and not a.lot_id for a in actuals):findings.append('Unverified actuals remain in the actual queue')
    if any(a.payload['amount'] is None or decimal(a.payload['amount'])>amount_sum(x.amount for x in links if x.actual_id==a.pk) for a in actuals if actual_available(a)):findings.append('Unmatched actuals require explicit investigation; no automatic settlement inferred')
    with localcontext() as ctx:
        ctx.prec=512
        for i in v['items']:
            amount=residual(s,i)
            if amount is not None and amount<0:raise ValidationError('Actual links exceed original selected forecast amount')
            if m:precise(number(amount),m)
            if i['kind']=='receivable':
                issue=InvoiceIssue.objects.get(pk=i['issue_id'],invoice__case=case)
                if corrections.unresolved(issue):findings.append('Selected receivable has unresolved correction: '+i['key'])
                if amount is not None and amount>cash.open_amount(issue):findings.append('Selected residual exceeds current corrected receivable: '+i['key'])
            row=dict(i,residual=number(amount),matched=number(matched(root_of(s),i['key'])))
            inputs.append(row)
            if not i['expected_on'] or i['expected_on'][:7] not in v['months']:
                unscheduled.append(i['key']);findings.append('Unknown/out-of-horizon timing: '+i['key'])
        opening_date_gap=any(o['observed_on']!=v['as_of'] for o in openings.values())
        if opening_date_gap:findings.append('Opening is not the declared as-of start of day; intervening cash reconciliation is unavailable')
        if any(o['amount'] is None for o in openings.values()) or set(openings)!=set(v['coverage']['accounts']) or opening_date_gap:opening=None
        else:opening=sum((decimal(o['amount']) for o in openings.values()),Decimal(0))
        periods=[]
        for month in v['months']:
            values={}
            for d in ['inflow','outflow']:
                rows=[i for i in inputs if direction(i)==d and i['expected_on'] and i['expected_on'][:7]==month]
                unknown=bool(invalid_actuals) or any(i['residual'] is None for i in rows) or any(direction(i)==d and i['key'] in unscheduled for i in inputs)
                values[d]=None if unknown else sum((decimal(i['residual']) for i in rows),Decimal(0))
            if m:
                from apps.policy.forecast_validators import chain
                close=chain(number(opening),number(values['inflow']),number(values['outflow']))
            else:close=None
            expected_values=dict(values)
            realized={}
            for d in ['inflow','outflow']:
                realized[d]=sum((decimal(a.payload['amount']) for a in actuals if actual_available(a) and a.payload['amount'] is not None and a.payload['direction']==d and all(a.payload[k]==v[k] for k in ['entity','currency','basis']) and a.payload['account'] in v['coverage']['accounts'] and a.payload['occurred_on']>=v['as_of'] and a.payload['occurred_on'][:7]==month),Decimal(0))
                if values[d] is not None:values[d]+=realized[d]
            if m:close=chain(number(opening),number(values['inflow']),number(values['outflow']))
            periods.append({'month':month,'opening':number(opening),'inflow':number(values['inflow']),'outflow':number(values['outflow']),'closing':close,
                'expected_inflow':number(expected_values['inflow']),'expected_outflow':number(expected_values['outflow']),'actual_inflow':number(realized['inflow']),'actual_outflow':number(realized['outflow'])})
            opening=None if close is None else decimal(close)
    if any(p['closing'] is None for p in periods):findings.append('Projected balance is unknown; missing input is not zero')
    result={'status':'held' if not m else 'partial' if findings else 'ready','entity':v['entity'],'currency':v['currency'],'basis':v['basis'],'as_of':v['as_of'],
        'coverage':v['coverage'],'scope':'captured_case_and_explicit_account_inventory_only','full_business_cash_forecast':False,'periods':periods,'items':inputs,'omitted_receivables':omitted,'queues':queues,'findings':findings,
        'actuals':[{'id':a.pk,'direction':a.payload['direction'],'amount':a.payload['amount'],'verified':actual_available(a),'unmatched':unmatched_actual(a,links)} for a in actuals],
        'rollover':v['rollover'],'execution_authorized':False}
    return manifest,result

@transaction.atomic
def prepare(actor,case_id,scenario_id,expected):
    case=lock_case(actor,case_id,'finance.forecast.calculate',expected);require(actor,case,'finance.read');s=exact(case,ForecastScenario,scenario_id)
    if ForecastScenario.objects.filter(case=case,reference=s.reference,number__gt=s.number).exists():raise ValidationError('Select current scenario revision')
    manifest,result=calculate(s);h=digest({'manifest':manifest,'result':result})
    old=ForecastRun.objects.filter(scenario=s,sha256=h).first()
    if old:return old
    run=ForecastRun.objects.create(case=case,scenario=s,manifest=manifest,result=result,sha256=h,actor=actor)
    event(actor,case,'forecast.prepared',run=run.pk,status=result['status']);bump(case);return run

def ensure_current(run):
    require(run.actor,run.case,'finance.forecast.calculate');require(run.scenario.actor,run.case,'finance.forecast.capture')
    if ForecastScenario.objects.filter(case=run.case,reference=run.scenario.reference,number__gt=run.scenario.number).exists():raise ValidationError('A newer forecast scenario revision exists')
    manifest,result=calculate(run.scenario)
    if run.sha256!=digest({'manifest':manifest,'result':result}):raise ValidationError('Forecast sources, actuals, matches, date or policy changed; calculate and review current evidence')

def review_snapshot(run):
    ensure_current(run);c,m=method(run.case)
    if run.result['status']=='held' or run.result['status']=='partial' and m['partial_publication']=='hold':raise ValidationError('Configured policy holds this incomplete forecast')
    return {'run_hash':run.sha256,'method':c.pk}

@transaction.atomic
def review(actor,case_id,run_id,role,verdict,evidence_id,reason,expected):
    case=lock_case(actor,case_id,'finance.forecast.review',expected);list(Grant.objects.select_for_update().filter(case=case));run=exact(case,ForecastRun,run_id);note(reason)
    require(actor,case,'finance.read')
    if verdict not in ['approve','return','reject']:raise ValidationError('Choose exact review verdict')
    snapshot=review_snapshot(run) if verdict=='approve' else {'run_hash':run.sha256}
    authority=review_authority(actor,case,'forecast_rollover' if run.scenario.parent_id else 'forecast',role,verdict,run.actor_id)
    r=ForecastReview.objects.create(run=run,snapshot=snapshot,role=role,verdict=verdict,authority=authority,evidence=subject(case,evidence_id,'forecast_review'),reason=reason,actor=actor)
    event(actor,case,'forecast.reviewed',review=r.pk,run=run.pk,verdict=verdict);bump(case);return r

def approved(run,current=True):
    r=ForecastReview.objects.filter(run=run).order_by('-pk').first()
    if not r or r.verdict!='approve':raise ValidationError('Exact configured human forecast approval is required')
    if not current:
        if r.snapshot.get('run_hash')!=run.sha256:raise ValidationError('Historical forecast review does not identify exact run')
        return r
    require(r.actor,run.case,'finance.forecast.review')
    auth=review_authority(r.actor,run.case,'forecast_rollover' if run.scenario.parent_id else 'forecast',r.role,r.verdict,run.actor_id)
    strip=lambda v:{k:x for k,x in v.items() if k!='D05.decision_action_matrix'}
    if strip(auth)!=strip(r.authority):raise ValidationError('Forecast review authority changed')
    if current and r.snapshot!=review_snapshot(run):raise ValidationError('Exact current forecast review is stale')
    return r

@transaction.atomic
def capture_actual(actor,case_id,evidence_id,expected,lot_id=None):
    case=lock_case(actor,case_id,'finance.forecast.actual',expected);list(Grant.objects.select_for_update().filter(case=case));require(actor,case,'finance.read');e=subject(case,evidence_id,'forecast_actual');v=parse_actual(e.body)
    if day(v['occurred_on'])>timezone.localdate():raise ValidationError('Actual transaction date cannot be future')
    lot=CashVerification.objects.filter(pk=lot_id,receipt__case=case).first() if lot_id else None
    if lot_id:
        if not lot or CashReversal.objects.filter(lot=lot).exists():raise ValidationError('Select a current active verified cash lot')
        value=cash.lot_payload(lot)
        if (v['source'],v['transaction'],v['amount'],v['currency'],v['direction'],v['occurred_on'])!=(value['source'],value['transaction_ref'],number(lot.amount),value['currency'],'inflow',value['received_at'][:10]):
            # Compare money numerically; formatting does not create a different transaction.
            if any(v[k]!=val for k,val in [('source',value['source']),('transaction',value['transaction_ref']),('currency',value['currency']),('direction','inflow'),('occurred_on',value['received_at'][:10])]) or v['amount'] is None or decimal(v['amount'])!=lot.amount:raise ValidationError('Actual statement differs from exact verified cash lot')
    old=ForecastActual.objects.filter(case=case,source=v['source'],transaction=v['transaction']).order_by('-pk').first()
    predecessor=None
    if old:
        if old.payload==v and old.lot_id==(lot.pk if lot else None):return old
        if not lot or not old.lot_id or not lot.successor_id or lot.successor.parent_id!=old.lot_id or not CashReversal.objects.filter(lot=old.lot).exists():raise ValidationError('Actual source transaction already captured with different facts; investigate')
        if any(v[k]!=old.payload[k] for k in ['entity','account','currency','basis','source','transaction','direction','occurred_on']):raise ValidationError('Corrected cash actual preserves original dimensions')
        predecessor=old
    r=ForecastActual.objects.create(case=case,source=v['source'],transaction=v['transaction'],payload=v,evidence=e,lot=lot,supersedes=predecessor,actor=actor)
    event(actor,case,'forecast.actual_reported',actual=r.pk,verified_lot=lot_id);bump(case);return r

@transaction.atomic
def verify_actual(actor,case_id,actual_id,role,evidence_id,expected):
    case=lock_case(actor,case_id,'finance.forecast.actual_verify',expected);list(Grant.objects.select_for_update().filter(case=case));r=exact(case,ForecastActual,actual_id);c,m=method(case)
    require(actor,case,'finance.read')
    proof=subject(case,evidence_id,'forecast_actual_verification')
    if r.lot_id:raise ValidationError('Existing verified cash lot is already the actual source; no second attestation')
    if role not in m['actual_roles'] or m['distinct_actual_reporter'] and r.actor_id==actor.pk:raise PermissionDenied('Configured actual verifier role/separation is required')
    if r.payload['amount'] is None or parse_actual(proof.body)!=r.payload:raise ValidationError('Known exact actual verification statement is required')
    precise(r.payload['amount'],m);auth=dict(decision_authority(actor,case,role),**{METHOD:c.pk})
    result,created=ForecastActualVerification.objects.get_or_create(actual=r,defaults={'evidence':proof,'authority':auth,'actor':actor})
    if created:event(actor,case,'forecast.actual_verified',actual=r.pk,verification=result.pk);bump(case)
    return result

@transaction.atomic
def match(actor,case_id,scenario_id,item_key,actual_id,amount,operation_key,evidence_id,expected):
    case=lock_case(actor,case_id,'finance.forecast.match',expected);list(Grant.objects.select_for_update().filter(case=case));s=exact(case,ForecastScenario,scenario_id);a=exact(case,ForecastActual,actual_id);c,m=method(case)
    require(actor,case,'finance.read')
    if not isinstance(operation_key,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',operation_key):raise ValidationError('Supply an exact match operation key')
    amount=decimal(amount,positive=True);precise(number(amount),m);root=root_of(s)
    old=ForecastMatch.objects.filter(case=case,operation_key=operation_key).first()
    if old:
        if (old.root_id,old.item_key,old.actual_id,old.amount)!=(root.pk,item_key,a.pk,amount):raise ValidationError('Match operation key reused with changed facts')
        return old
    item=next((i for i in s.payload['items'] if i['key']==item_key),None)
    if not item or not actual_available(a) or a.payload['amount'] is None:raise ValidationError('Select exact remaining forecast item and verified actual')
    if any(s.payload[k]!=a.payload[k] for k in ['entity','currency','basis']) or a.payload['direction']!=direction(item) or a.payload['account'] not in s.payload['coverage']['accounts']:raise ValidationError('Actual dimensions/direction/account do not match scenario')
    if day(a.payload['occurred_on'])<day(root.payload['as_of']):raise ValidationError('Actual predates original forecast cut-off; opening double-count risk')
    remaining=residual(s,item)
    with localcontext() as ctx:
        ctx.prec=512
        capacity=decimal(a.payload['amount'])-sum((r.amount for r in active_matches().filter(actual=a)),Decimal(0))
    if remaining is None or amount>remaining or amount>capacity:raise ValidationError('Match exceeds known forecast or actual capacity')
    if m['matching']=='exact_only' and (amount!=remaining or amount!=capacity):raise ValidationError('Configured matching requires exact full settlement')
    proof=subject(case,evidence_id,'forecast_match')
    r=ForecastMatch.objects.create(case=case,root=root,item_key=item_key,actual=a,amount=amount,operation_key=operation_key,evidence=proof,authority={METHOD:c.pk},actor=actor)
    event(actor,case,'forecast.actual_matched',match=r.pk,actual=a.pk,item=item_key);bump(case);return r

@transaction.atomic
def unmatch(actor,case_id,match_id,evidence_id,reason,expected):
    case=lock_case(actor,case_id,'finance.forecast.match',expected);list(Grant.objects.select_for_update().filter(case=case));note(reason)
    require(actor,case,'finance.read')
    match=exact(case,ForecastMatch,match_id);c,m=method(case);proof=subject(case,evidence_id,'forecast_match')
    r,created=ForecastMatchReversal.objects.get_or_create(match=match,defaults={'evidence':proof,'authority':{METHOD:c.pk,'method':m['match_reversal']},'reason':reason,'actor':actor})
    if created:event(actor,case,'forecast.match_reversed',match=match.pk,reversal=r.pk);bump(case)
    return r

@transaction.atomic
def prioritize(actor,case_id,run_id,role,reference,description,owner_id,due_at,evidence_id,reason,expected):
    case=lock_case(actor,case_id,'finance.forecast.prioritize',expected);list(Grant.objects.select_for_update().filter(case=case));run=exact(case,ForecastRun,run_id);review=approved(run)
    require(actor,case,'finance.read')
    authority=review_authority(actor,case,'forecast_priority',role,'approve',run.actor_id)
    if owner_id is None or due_at is None:raise ValidationError('Forecast follow-up requires an explicit accountable owner and deadline')
    proof=subject(case,evidence_id,'forecast_review')
    from apps.pmo.meetings import create_action
    from .models import ForecastPriority
    item=create_action(actor,case.pk,reference,description,owner_id,due_at,proof.pk,reason,case.revision)
    binding=ForecastPriority.objects.create(review=review,action=item,authority=authority)
    event(actor,case,'forecast.priority_recorded',priority=binding.pk,review=review.pk,action_item=item.pk,execution_authorized=False);return binding
