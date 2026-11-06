"""Selected read-only rehearsal evidence. Local records never authorize live work."""
import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import event
from apps.identity.models import Grant
from apps.identity.services import require
from adapters import pilot_preflight as adapter
from . import pilot_validators as validators
from .impact import digest,configuration
from .models import PilotContract,PilotObservation,ScopeApplication
from .registry import dependencies
from .services import resolve


def context(actor,case_id,action='pilot.read'):
    if not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists() or not Grant.objects.filter(user=actor,case_id=case_id,action='case.read',active=True).exists():
        raise PermissionDenied('Current case access required before pilot lookup')
    case=Case.objects.get(pk=case_id)
    require(actor,case,'policy.read');require(actor,case,'pilot.read');require(actor,case,action)
    return case


def observation(actor,case,payload,selected_contract=None):
    validators.validate(case,payload)
    from adapters.pilot_acceptance import read as acceptance
    decisions=[acceptance(actor,case,pk) for pk in payload.get('acceptance_reviews',[])]
    participants=[]
    for row in payload['participants']:
        # A grant on this exact case is the membership boundary; do not enumerate tenant users.
        if not Grant.objects.filter(case=case,user_id=row['user_id']).exists():
            raise ValidationError('Selected participant is unavailable in this case')
        user=get_user_model().objects.get(pk=row['user_id'])
        rights=list(Grant.objects.filter(case=case,user=user,action__in=set(row['actions'])|{'case.read'}).order_by('action').values_list('action','active'))
        granted={k for k,v in rights if v} if user.is_active else set()
        participants.append({'user_id':user.pk,'active':user.is_active,'rights':rights,
            'missing':sorted((set(row['actions'])|{'case.read'})-granted)})
    policies=[]
    for operation in payload['operations']:
        results=[]
        for component in dependencies(operation):
            r=resolve(component,case);p=r.configuration
            if p:configuration(actor,case.pk,p.pk) # Current scoped-source read, even for historical pins.
            app=ScopeApplication.objects.filter(configuration=p).first() if p else None
            results.append({'component':component,'status':r.status,'configuration':p.pk if p else None,
                'revision':p.revision if p else None,'scope_source':app.source_id if app else None})
        policies.append({'operation':operation,'dependencies':results,'policy_ready':all(r['status']=='ACTIVE' for r in results),
            'domain_runtime_guards':'NOT_EVALUATED'})
    integrations=[adapter.integration(actor,case,pk) for pk in payload['integrations']]
    jobs=[adapter.job(actor,case,r['family'],r['id']) for r in payload['jobs']]
    from .pilot_bindings import report as binding_report
    bindings=binding_report(actor,case,selected_contract) if selected_contract else {'state':'UNCONFIGURED','native_guards':[],'worker_deployment_ready':False}
    for p in policies:
        checks=[{'user_id':g['user_id'],'state':g['state']} for g in bindings['native_guards'] if g['operation']==p['operation']]
        p['native_checks']=checks
        p['domain_runtime_guards']='NOT_EVALUATED' if not checks else 'READY_AT_OBSERVATION' if all(g['state']=='READY_AT_OBSERVATION' for g in checks) else 'HELD_OR_SOURCE_RECOVERY'
    return {'format':'psl.pilot-observation/v1','case_id':str(case.pk),'case_revision':case.revision,
        'classification':'synthetic' if case.synthetic else 'operational','contract':digest(payload),
        'participants':participants,'policies':policies,'integrations':integrations,'jobs':jobs,
        'technical':adapter.technical(),'bindings':bindings,'coverage':{'process_ids':payload['process_ids'],
            'operations':payload['operations'],'complete_122_acceptance':False,
            'unknown':['Unselected cases, operations, families and variants','Operation-to-participant action sufficiency','Business source/oracle validation','Worker deployment and storage/retention/monitoring','Staff supervised pilot acceptance']},
        'human_acceptance':{'verdict':'SOURCE_OWNED_SELECTED_SCOPE_REVIEW' if decisions else 'UNRECORDED','live_run_evidence':None,
            'references':decisions,'uncovered_process_ids':sorted(set(payload['process_ids'])-{pid for r in decisions if r['current'] for pid in r['process_ids']}),
            'scope':'Existing AF13 source/example execution review; not full pilot or external/business-oracle acceptance'},
        'rehearsal_steps':[
            {'kind':'engineering_proposal','step':'Inspect current exact participant grants and selected dependency holds'},
            {'kind':'engineering_proposal','step':'Review native integration/source/oracle evidence and deployment findings'},
            {'kind':'engineering_proposal','step':'Investigate unknown effects through source-owned receipt-first controls'},
            {'kind':'engineering_proposal','step':'Obtain separate supervised staff acceptance before live runtime work'}],
        'boundaries':{'read_only':True,'effect_tools':[],'effects_scheduled':False,'owner_values_installed':False,
            'live_pilot_performed':False,'operational_acceptance':False}}


@transaction.atomic
def configure(actor,case_id,payload,predecessor=None):
    case=context(actor,case_id,'pilot.configure');lock_selection(case,payload,actor)
    current=PilotContract.objects.filter(case=case).order_by('-version').first()
    if (current.pk if current else None)!=predecessor:raise ValidationError('Refresh the current pilot contract predecessor')
    observation(actor,case,payload) # Validate exact selections and domain/source/private access now.
    row=PilotContract.objects.create(case=case,version=current.version+1 if current else 1,payload=payload,sha256=digest(payload),actor=actor)
    event(actor,case,'agent.data.pilot_contract',contract=row.pk,version=row.version)
    return row


def contract(actor,case_id,pk):
    case=context(actor,case_id)
    row=PilotContract.objects.filter(case=case,pk=pk).first()
    if not row:raise ValidationError('Exact selected pilot contract required')
    return case,row


def stored_sources(actor,case,snapshot):
    # resolve() intentionally returns no Configuration for revoked/unavailable
    # origins. Historical private source permissions must still be checked.
    pins={r['configuration'] for p in snapshot['policies'] for r in p['dependencies'] if r['configuration']}
    pins.update(pk for g in snapshot.get('bindings',{}).get('native_guards',[]) for pk in g['policy_pins'])
    for pk in sorted(pins):configuration(actor,case.pk,pk)
    from adapters.pilot_acceptance import read
    for r in snapshot.get('human_acceptance',{}).get('references',[]):read(actor,case,r['review'])


def lock_selection(case,payload,actor=None):
    if isinstance(payload,dict) and any(j.get('family') in ['application','cold'] for j in payload.get('jobs',[]) if isinstance(j,dict)):
        if actor is None:raise PermissionDenied('Current native recovery reader required')
        for family in {j.get('family') for j in payload['jobs'] if isinstance(j,dict)} & {'application','cold'}:
            if family=='application':
                from apps.workflows.application_recovery import access
            else:
                from apps.workflows.cold_recovery import access
            access(actor,case,'read',locked=False)
        list(Case.objects.select_for_update().order_by('pk')) # Native database recovery uses a whole-source authority/lock boundary.
    if isinstance(payload,dict) and payload.get('acceptance_reviews'):
        from apps.finance.ledger import scope_lock
        scope_lock(case.pk) # Match AF13/private Finance ordered participant/case lock order.
    else:Case.objects.select_for_update().get(pk=case.pk)


@transaction.atomic
def capture(actor,case_id,pk):
    case,row=contract(actor,case_id,pk);require(actor,case,'pilot.capture')
    lock_selection(case,row.payload,actor)
    case.refresh_from_db()
    if PilotContract.objects.filter(case=case,version__gt=row.version).exists():raise ValidationError('Use the current pilot contract')
    snapshot=observation(actor,case,row.payload,row);sha=digest(snapshot)
    existing=PilotObservation.objects.filter(contract=row,actor=actor,sha256=sha).order_by('-pk').first()
    now=timezone.now()
    if existing and now-existing.created_at<timedelta(minutes=15):return existing
    # The case lock deduplicates retries; expired unchanged heads need a fresh observation.
    key=digest([row.pk,actor.pk,sha,now.isoformat()])
    result=PilotObservation.objects.create(contract=row,snapshot=snapshot,sha256=sha,operation_key=key,actor=actor)
    event(actor,case,'agent.data.pilot_observed',observation=result.pk)
    return result


@transaction.atomic
def inspect(actor,case_id,pk):
    case=context(actor,case_id)
    row=PilotObservation.objects.select_related('contract','actor','contract__actor').filter(contract__case=case,pk=pk).first()
    if not row:raise ValidationError('Exact pilot observation required')
    lock_selection(case,row.contract.payload,actor)
    stored_sources(actor,case,row.snapshot)
    current=observation(actor,case,row.contract.payload,row.contract) # Reauthorize all native sources before exporting stored metadata.
    author_current=True
    try:
        context(row.actor,case.pk,'pilot.capture');context(row.contract.actor,case.pk,'pilot.configure')
        stored_sources(row.actor,case,row.snapshot);stored_sources(row.contract.actor,case,row.snapshot)
        observation(row.actor,case,row.contract.payload,row.contract);observation(row.contract.actor,case,row.contract.payload,row.contract)
    except PermissionDenied:author_current=False
    fresh=timezone.now()-row.created_at<timedelta(minutes=15)
    matches=digest(current)==row.sha256 and row.contract.sha256==digest(row.contract.payload)
    successor=PilotContract.objects.filter(case=case,version__gt=row.contract.version).exists()
    return {'observation':row.pk,'contract':row.contract_id,'version':row.contract.version,
        'observed_at':row.created_at.isoformat(),'sha256':row.sha256,
        'current':matches and fresh and author_current and not successor,
        'fresh_within_15_minutes':fresh,'heads_match':matches,'author_authority_current':author_current,
        'superseded':successor,'snapshot':row.snapshot,'live_pilot_performed':False,'operational_acceptance':False}
