"""Scoped O01 choice. Native eligibility and domain services retain all authority."""
from django.core.exceptions import PermissionDenied,ValidationError
from apps.policy.services import active_component,reference_values
from apps.policy.factory_coordinator_validators import COMPONENT
from apps.policy.factory_coordinator_validators import PROTOCOL,SCOPE
from django.db import transaction
from django.db.models import Exists,OuterRef
from django.utils import timezone
from datetime import timedelta
from apps.documents.contracts import digest,validate

class PlanningUnknown(ConnectionError):
    pass

def configured(work):
    from apps.workflows.factory import access
    access(work.execution_actor,work.case,'factory.execute',work.definition)
    policy=active_component(COMPONENT,work.case);value=reference_values(policy)[0]
    from apps.policy.models import ScopeApplication
    application=ScopeApplication.objects.select_related('source__configuration__case').filter(configuration=policy).first()
    if application:
        from apps.policy.scopes import authorized
        authorized(work.execution_actor,application.source.configuration.case,'policy.read')
    if value['mode'] is None:raise ValidationError('configuration_needed: select a coordination mode')
    if value['planner_id'] is None:raise ValidationError('owner_needed: nominate a current coordinator principal')
    if value['planner_id']!=work.execution_actor_id:raise PermissionDenied('Configured coordinator principal does not match current execution authority')
    return policy,value

def provider_binding(work,value):
    from apps.workflows import readiness
    from apps.workflows.readiness_models import IntegrationSelection
    from adapters.readiness import binding
    if value['contract_id'] is None:raise ValidationError('configuration_needed: select a reviewed planning provider contract')
    contract=readiness.contract_for(work.case,value['contract_id'])
    readiness.readable(work.execution_actor,work.case,True);readiness.contract_access(work.execution_actor,contract);readiness.current_contract(contract)
    if contract.payload['contract_version']!=PROTOCOL or 'receipt_lookup' not in contract.payload['capabilities']:
        raise ValidationError('configuration_needed: exact planning protocol and receipt lookup capability required')
    selection=IntegrationSelection.objects.filter(case=work.case,family='provider').order_by('-version').first()
    if not selection or selection.contract_id!=contract.pk:raise ValidationError('configuration_needed: select the reviewed planning provider')
    pins=readiness.gate(work.case,'provider')
    if not pins:raise ValidationError('configuration_needed: current provider assessment and human review required')
    public,private=binding(contract)
    return contract,public,private,pins

def intent(work,context,activity,number):
    policy,value=configured(work)
    result={'schema':'factory-coordinator-plan/v1','coordinator_policy':policy.pk,'mode':value['mode']}
    if value['mode']=='internal_permitted_step_v1':return result
    contract,public,_,pins=provider_binding(work,value)
    if len(context['evidence_ids'])>16:raise ValidationError('Coordinator citation ceiling exceeded')
    handles={f'c{i}':pk for i,pk in enumerate(context['evidence_ids'])}
    execution=reference_values(work.policy)[0]
    payload={'protocol':PROTOCOL,'model_id':contract.payload['model_id'],'data_scope':SCOPE,
        'eligible':context['eligible'],'citation_handles':list(handles),'tools':[],
        'token_limit':execution['tokens_per_call'],'max_output_chars':value['max_output_chars']}
    result.update(schema='factory-provider-request/v1',contract=contract.pk,binding=public,readiness=pins,
        payload=payload,citation_map=handles,native_context=context,max_output_chars=value['max_output_chars'])
    result['operation_key']=digest({'work':work.pk,'activity':activity.pk,'number':number,'intent':result})
    return result

def pending(work):
    from apps.workflows.models import FactoryAttempt
    done=FactoryAttempt.objects.filter(activity_id=OuterRef('activity_id'),number=OuterRef('number'),phase__in=['observed','failed'])
    return FactoryAttempt.objects.filter(activity__work=work,activity__kind='ACT03',phase='started',
        result__schema='factory-provider-request/v1').annotate(done=Exists(done)).filter(done=False).select_related('activity__work__case').order_by('pk').first()

def has_receipt(attempt):
    from apps.workflows.models import FactoryPlanningReceipt
    return FactoryPlanningReceipt.objects.filter(attempt=attempt).exists()

def assert_current(work,request):
    policy,value=configured(work)
    if request.get('coordinator_policy')!=policy.pk or request.get('mode')!=value['mode']:
        raise ValidationError('STALE_VERSION: coordinator settings changed while planning')
    if value['mode']=='authenticated_planner_v1':
        contract,public,_,pins=provider_binding(work,value)
        if request['contract']!=contract.pk or request['binding']!=public or request['readiness']!=pins:
            raise ValidationError('STALE_VERSION: provider readiness or binding changed while planning')

def fetch(attempt,actor,send_allowed=False):
    from apps.workflows.models import FactoryPlanningReceipt
    from apps.workflows import readiness
    from adapters.readiness import binding
    from adapters.factory_planner import FactoryPlannerAdapter
    from adapters.forecast import obj
    import json
    old=FactoryPlanningReceipt.objects.filter(attempt=attempt).first()
    if old:return old
    work=attempt.activity.work;request=attempt.result
    readiness.readable(actor,work.case,True)
    contract=readiness.contract_for(work.case,request['contract']);readiness.contract_access(actor,contract)
    recovery=None
    try:public,private=binding(contract)
    except ValidationError:public=None
    from apps.workflows.models import FactoryPlanningRecovery
    if public!=request['binding'] or FactoryPlanningRecovery.objects.filter(attempt=attempt).exists():
        from apps.workflows.factory_receipt_recovery import transport
        recovery,private=transport(attempt,actor)
        # The returned receipt continues to identify the original immutable operation.
        public=request['binding']
        send_allowed=False
    adapter=FactoryPlannerAdapter()
    try:
        answer=adapter.lookup(request,private)
        if answer is None and send_allowed:
            current=type(work).objects.select_related('case','actor').get(pk=work.pk)
            assert_current(current,request)
            answer=adapter.plan(request,private)
        if answer is None:raise PlanningUnknown('Original planning result remains uncertain; no new request sent')
    except (TimeoutError,ConnectionError) as exc:raise PlanningUnknown('Original planning result remains uncertain; check its receipt before further work') from None
    try:output_sha256=digest(answer)
    except (ValueError,TypeError,RecursionError):raise PlanningUnknown('Malformed planning receipt; no native command authorised') from None
    valid=True;native={}
    try:
        if len(json.dumps(answer,allow_nan=False))>request['max_output_chars']:raise ValidationError('Planning output ceiling exceeded')
        validate(obj({'activity':{'enum':request['payload']['eligible']},'citations':{'type':'array','minItems':1,'maxItems':16,
            'uniqueItems':True,'items':{'enum':list(request['citation_map'])}}}),answer)
        native={'activity':answer['activity'],'citations':[request['citation_map'][key] for key in answer['citations']]}
    except (ValidationError,ValueError,TypeError):valid=False
    with transaction.atomic():
        receipt,created=FactoryPlanningReceipt.objects.get_or_create(attempt=attempt,defaults={'actor':actor,'valid':valid,
            'result':native,'output_sha256':output_sha256,'binding':public})
        if not created and (receipt.output_sha256!=output_sha256 or receipt.result!=native):raise ValidationError('Conflicting original planning receipt')
        if recovery:
            from apps.workflows.factory_receipt_recovery import attach
            attach(receipt,recovery)
        return receipt

def choose(work,context,attempt=None,resuming=False):
    _,value=configured(work)
    if value['mode']=='internal_permitted_step_v1':
        return {'activity':context['eligible'][0],'citations':context['evidence_ids'][:1]},value['mode']
    if attempt is None:raise ValidationError('Native started planning request required')
    receipt=fetch(attempt,work.execution_actor,send_allowed=not resuming)
    if not receipt.valid:raise ValidationError('Planning provider result rejected; no native command authorised')
    assert_current(work,attempt.result)
    return receipt.result,value['mode']

def reconcile(actor,work_id,expected):
    from apps.workflows.factory import access,fence,cancellation_status
    from apps.workflows.models import FactoryWork,FactoryAttempt
    from apps.identity.services import require
    from apps.core.services import event
    with transaction.atomic():
        work=FactoryWork.objects.select_for_update(of=('self',)).select_related('case','actor').get(pk=work_id)
        access(actor,work.case,'factory.execute',work.definition)
        from apps.workflows.factory_execution import require_control
        require_control(actor,work)
        if work.revision!=expected:raise ValidationError('STALE_VERSION: work changed')
        if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: worker owns this work')
        attempt=pending(work)
        if attempt is None:raise ValidationError('No original planning response to reconcile')
        work.fence+=1;token=work.fence;work.lease_until=timezone.now()+timedelta(seconds=30);work.revision+=1;work.save()
        event(actor,work.case,'factory.planning_lookup_requested',work=work.pk,attempt=attempt.pk,lookup_only=True)
    receipt=None;finding=''
    try:receipt=fetch(attempt,actor)
    except (PlanningUnknown,ValidationError,PermissionDenied) as exc:finding=str(exc)[:300]
    with transaction.atomic():
        work=FactoryWork.objects.select_for_update().get(pk=work_id);fence(work,token)
        if receipt and (work.cancel_requested or not receipt.valid):
            FactoryAttempt.objects.get_or_create(activity=attempt.activity,number=attempt.number,phase='failed',defaults={
                'fence':token,'observation':attempt.observation,'result':{'reason':'cancelled' if work.cancel_requested else 'provider_result_rejected'}})
        work.status=cancellation_status(work) if work.cancel_requested else 'ready' if receipt and receipt.valid else 'blocked' if receipt else 'waiting_effect'
        work.finding=finding or ('Planning result rejected; owner review required' if receipt and not receipt.valid else '')
        work.lease_until=None;work.revision+=1;work.save()
    return work

def presentation(actor,work):
    from apps.workflows.factory import access
    from apps.identity.services import require
    attempt=pending(work)
    if attempt is None:return None
    access(actor,work.case,envelope=work.definition)
    received=has_receipt(attempt);leased=bool(work.lease_until and work.lease_until>timezone.now())
    can_lookup=True
    try:
        access(actor,work.case,'factory.execute',work.definition)
        for action in ['integration.read','integration.source.read']:require(actor,work.case,action)
        from apps.workflows.factory_execution import require_control
        require_control(actor,work)
    except PermissionDenied:can_lookup=False
    can_recover=True
    try:
        access(actor,work.case,'factory.manage',work.definition)
        for action in ['integration.read','integration.source.read','integration.review']:require(actor,work.case,action)
    except PermissionDenied:can_recover=False
    return {'attempt':attempt.pk,'received':received,'leased':leased,'can_lookup':can_lookup and not leased,
        'can_recover':can_recover and not leased and not received,'operation_key':attempt.result['operation_key'],'work':work}

def decorate(actor,work,row):
    state=presentation(actor,work)
    if state and not state['received'] and not state['leased']:
        row.update(state='Planning response uncertain',next_action='Check the original planning response',can_advance=False,
            needs_me=state['can_lookup'],blocker='The original planning response must be reconciled; another request is not authorised')
    return row
