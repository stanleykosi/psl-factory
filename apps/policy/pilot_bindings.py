"""Native guard/deployment binding lifecycle. Engineering review is not business authority."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from apps.core.models import Case
from apps.core.services import event
from apps.identity.services import require
from . import pilot,pilot_binding_validators as validators
from .models import PilotBinding,PilotBindingReview,PilotRuntimeReceipt,PilotContract
from .impact import digest,configuration
from adapters import pilot_guards,pilot_runtime,pilot_preflight


def get(actor,case_id,pk):
    c=pilot.context(actor,case_id)
    b=PilotBinding.objects.select_related('contract__case','actor').filter(pk=pk,contract__case=c).first()
    if not b:raise ValidationError('Exact native pilot binding required')
    return c,b


@transaction.atomic
def configure(actor,case_id,contract_id,payload):
    c,contract=pilot.contract(actor,case_id,contract_id);require(actor,c,'pilot.configure')
    pilot.lock_selection(c,contract.payload,actor)
    if PilotContract.objects.filter(case=c,version__gt=contract.version).exists():raise ValidationError('Current pilot contract required')
    validators.validate(contract,payload)
    for g in payload['guards']:pilot_guards.check(actor,c,g)
    old=PilotBinding.objects.filter(contract=contract).first()
    if old:
        if old.payload!=payload or old.actor_id!=actor.pk:raise ValidationError('Binding exists; create a selected contract successor')
        return old
    row=PilotBinding.objects.create(contract=contract,payload=payload,sha256=digest(payload),actor=actor)
    event(actor,c,'agent.data.pilot_binding',binding=row.pk);return row


@transaction.atomic
def review(actor,case_id,pk,verdict,reason):
    c,b=get(actor,case_id,pk);require(actor,c,'pilot.binding.review');pilot.lock_selection(c,b.contract.payload,actor)
    if actor.pk==b.actor_id:raise PermissionDenied('Independent engineering reviewer required')
    if verdict not in ['accept','reject','defer'] or not isinstance(reason,str) or not 1<=len(reason.strip())<=2000:raise ValidationError('Typed bounded engineering verdict required')
    if PilotContract.objects.filter(case=c,version__gt=b.contract.version).exists():raise ValidationError('Current selected contract required')
    pilot.observation(actor,c,b.contract.payload)
    for g in b.payload['guards']:pilot_guards.check(actor,c,g)
    if PilotBindingReview.objects.filter(binding=b).exists():raise ValidationError('Engineering verdict is immutable; use a successor contract')
    row=PilotBindingReview.objects.create(binding=b,verdict=verdict,sha256=b.sha256,reason=reason,actor=actor)
    event(actor,c,'agent.data.pilot_binding_review',review=row.pk);return row


@transaction.atomic
def emit(actor,case_id,pk,role,family=None,observe_only=True):
    c,b=get(actor,case_id,pk);require(actor,c,'pilot.runtime.observe')
    if role not in ['web','worker']:raise ValidationError('Native runtime role required')
    if PilotContract.objects.filter(case=c,version__gt=b.contract.version).exists():raise ValidationError('Current selected contract required')
    p,_,_=pilot_runtime.profile(b,role)
    if p['principal_id']!=actor.pk:raise PermissionDenied('Current configured runtime principal required')
    payload,signature=pilot_runtime.observe(b,role,family,observe_only=observe_only)
    row=PilotRuntimeReceipt.objects.create(binding=b,payload=payload,sha256=digest(payload),signature=signature)
    event(actor,c,'agent.data.pilot_runtime_observed',receipt=row.pk,role=role);return row


def worker(pk,module,observe_only):
    family=next((f for f,m in validators.WORKERS.items() if m==module),None)
    if not family:raise ValidationError('Registered native worker command required')
    b=PilotBinding.objects.select_related('contract__case').get(pk=pk)
    p,_,_=pilot_runtime.profile(b,'worker')
    a=get_user_model().objects.get(pk=p['principal_id'])
    return emit(a,b.contract.case_id,b.pk,'worker',family,observe_only=observe_only)


def report(actor,case,contract):
    case=pilot.context(actor,case.pk)
    if contract.case_id!=case.pk:raise ValidationError('Exact selected case contract required')
    b=PilotBinding.objects.select_related('actor').filter(contract=contract).first()
    if not b:return {'state':'UNCONFIGURED','native_guards':[],'worker_deployment_ready':False,'native_guard_coverage_complete':False,'unbound_operations':contract.payload['operations']}
    contract_current=not PilotContract.objects.filter(case=case,version__gt=contract.version).exists()
    guards=[pilot_guards.check(actor,case,g) for g in b.payload['guards']]
    review=PilotBindingReview.objects.select_related('actor').filter(binding=b).first();review_current=False
    try:
        pilot.context(b.actor,case.pk,'pilot.configure')
        if review:
            pilot.context(review.actor,case.pk,'pilot.binding.review')
            for g in b.payload['guards']:pilot_guards.check(review.actor,case,g)
            review_current=review.verdict=='accept' and review.sha256==b.sha256 and contract_current
    except PermissionDenied:pass
    actual=pilot_preflight.technical();receipts=[];boots=[]
    for role,family in [('web',None)]+[('worker',f) for f in b.payload['deployment']['families']]:
        r=PilotRuntimeReceipt.objects.filter(binding=b,payload__role=role,payload__family=family).order_by('-pk').first()
        valid=bool(r and pilot_runtime.verify(b,r,role,family,actual))
        if valid:boots.append((role,r.payload['process_boot']))
        receipts.append({'role':role,'family':family,'receipt':r.pk if r else None,'sha256':r.sha256 if r else None,'current':valid})
    web_boots={p for r,p in boots if r=='web'};worker_boots={p for r,p in boots if r=='worker'}
    independent=bool(web_boots and worker_boots) and not (web_boots & worker_boots)
    unbound=sorted(set(contract.payload['operations'])-{g['operation'] for g in guards})
    return {'binding':b.pk,'sha256':b.sha256,'review':review.pk if review else None,'review_current':review_current,'contract_current':contract_current,
        'state':'OBSERVED','native_guards':guards,'receipts':receipts,'independent_processes':independent,
        'worker_deployment_ready':review_current and all(r['current'] for r in receipts) and independent,
        'all_native_guards_ready':all(g['state']=='READY_AT_OBSERVATION' for g in guards),
        'native_guard_coverage_complete':not unbound,'unbound_operations':unbound,
        'coverage':str(len(pilot_guards.REGISTRY))+' declared native PMO/Finance/BaaS/publication operations and sixteen native worker entry points only',
        'storage_retention_monitoring':'UNVERIFIED_DEPLOYMENT_DECLARATIONS_ONLY','operational_acceptance':False,'effect_tools':[]}
