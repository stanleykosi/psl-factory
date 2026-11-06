"""Declared PMO inventory to native archive index; no new approval or byte-backup claim."""
import json,hashlib
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Evidence,Audit
from apps.core.evidence_access import public_evidence
from apps.core.services import lock_case,add_evidence,event
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.services import resolve,reference_values
from apps.documents.contracts import validate,digest
from apps.pmo import delivery,delivery_closure as closure
from apps.pmo.models import DeliveryRecord
from adapters.delivery import LocalDeliveryAdapter
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt
from .factory_delivery import investigation_key

DEFINITION='delivery-archive/v1'
KIND='agent_private_archive_intake'
PROTOCOL='factory-archive-intake/v1'
CORE_KINDS=['technical_document','test_results','project_artifact']
INVENTORY={'type':'object','maxProperties':20,'propertyNames':{'type':'string','pattern':'^[a-z][a-z0-9_]{0,49}$'},
    'additionalProperties':{'anyOf':[{'type':'integer','minimum':1,'maximum':9223372036854775807},{'type':'null'}]}}
SCHEMA={'type':'object','properties':{'protocol':{'const':PROTOCOL},'dossier_id':{'type':'integer','minimum':1},'inventory':INVENTORY},
    'required':['protocol','dossier_id','inventory'],'additionalProperties':False}


def inventory_rows(case,inventory):
    validate(INVENTORY,inventory)
    if any(pk is not None and type(pk) is not int for pk in inventory.values()):raise ValidationError('Exact integer evidence identifiers or an unprovided value are required')
    rows={e.pk:e for e in public_evidence(Evidence.objects.filter(case=case,pk__in=[pk for pk in inventory.values() if pk is not None]))}
    for kind,pk in inventory.items():
        if pk is not None and (pk not in rows or rows[pk].kind!=kind):raise ValidationError('Choose available same-project public '+kind.replace('_',' ')+' evidence')
    return rows


def source(work,actor=None,current=True):
    actor=actor or work.actor;require(actor,work.case,'delivery.read');e=work.source_head
    if not e or e.kind!=KIND or e.case_id!=work.case_id or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():raise ValidationError('Exact same-project archive intake required')
    try:data=json.loads(e.body)
    except (ValueError,TypeError):raise ValidationError('Typed declared inventory required') from None
    validate(SCHEMA,data)
    audit=Audit.objects.filter(case=work.case,actor_id=e.created_by_id,action__in=['factory.archive_intake','factory.archive_source'],
        data={'evidence_id':e.pk,'sha256':e.sha256}).order_by('-pk').first()
    if not audit or data['dossier_id']!=work.request['dossier']:raise ValidationError('Native archive intake provenance and exact dossier required')
    if current:
        for action in ['delivery.read','evidence.add','factory.start' if audit.action=='factory.archive_intake' else 'factory.manage']:require(e.created_by,work.case,action)
    d=delivery.dossier_for(work.case,data['dossier_id'],current=current)
    return d,data,inventory_rows(work.case,data['inventory'])


def capture(actor,case,dossier,inventory,action):
    body=json.dumps({'protocol':PROTOCOL,'dossier_id':dossier.pk,'inventory':inventory},sort_keys=True)
    e=add_evidence(actor,case.pk,KIND,body,'psl:factory-archive-intake/v1')
    event(actor,case,action,evidence_id=e.pk,sha256=e.sha256);return e


@transaction.atomic
def start(actor,case_id,key,dossier_id,inventory,reference,expected=None):
    from .factory import access
    case=lock_case(actor,case_id,'factory.start',expected);access(actor,case,'factory.start',DEFINITION);require(actor,case,'evidence.add')
    if case.kind!='project':raise ValidationError('Project artifact archival requires a project workspace')
    if not isinstance(key,str) or not key.isascii() or not 1<=len(key)<=100:raise ValidationError('Bounded work identity required')
    if not isinstance(reference,str) or not reference.strip() or len(reference)>160:raise ValidationError('Describe the archive work in at most160 characters')
    d=delivery.dossier_for(case,dossier_id);delivery.ensure_open(d);inventory_rows(case,inventory)
    payload={'dossier':d.pk,'reference':reference};sha=digest(payload);business=digest([str(case.pk),DEFINITION,d.candidate_id])
    old=Work.objects.filter(case=case).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.key==key and old.request_hash!=sha:raise ValidationError('IDEMPOTENCY_CONFLICT: archive intent changed')
        if source(old)[1]['inventory']!=inventory:raise ValidationError('Review a declared inventory correction in the existing archive work')
        return old
    e=capture(actor,case,d,inventory,'factory.archive_intake')
    w=Work.objects.create(case=case,actor=actor,key=key,definition=DEFINITION,request=payload,request_hash=sha,business_key=business,source_head=e)
    event(actor,case,'factory.started',work=w.pk,definition=DEFINITION);return w


def storage(case):
    p=resolve('D11.template_storage_retention_rules',case)
    if p.status!='ACTIVE':raise ValidationError('configuration_needed: Current reviewed archive inventory and storage/retention rules are required')
    value=reference_values(p.configuration)[0]
    if 'closure_inventory' not in value:raise ValidationError('configuration_needed: Reviewed storage v2 closure inventory is required')
    return p.configuration,value


def required_kinds(case):
    try:return storage(case)[1]['closure_inventory']['required_kinds']
    except (ValidationError,PermissionDenied):return CORE_KINDS


def operator(work,value):
    user=get_user_model().objects.filter(pk=value['executor_id'],is_active=True).first()
    if not user:raise ValidationError('owner_needed: Configure a currently authorised archive operator for the dependent index command')
    try:
        for action in ['case.read','delivery.read','factory.execute','delivery.manage']:require(user,work.case,action)
    except PermissionDenied:raise ValidationError('owner_needed: The configured archive operator no longer has current project permissions') from None
    return user


def checks(d,data):
    result={}
    try:
        policy,value=storage(d.case);kinds=value['closure_inventory']['required_kinds']
        result['storage']={'status':'ready','title':'Archive rules','inputs':{'policy':policy.pk,'required_kinds':kinds,'repository':value['repository'],'retention_days':value['retention_days']}}
    except (ValidationError,PermissionDenied) as exc:
        result['storage']={'status':'held','title':'Archive rules','summary':'Review the inventory, storage and retention rule.','finding':str(exc)}
        result['archive']={'status':'held','title':'Declared evidence','summary':'Archive rules are needed to check the declared inventory.'};return result
    if set(data['inventory'])!=set(kinds) or any(pk is None for pk in data['inventory'].values()):
        result['archive']={'status':'held','title':'Declared evidence','summary':'Complete the exact configured artifact inventory. Unknown evidence remains unprovided.'};return result
    try:result['archive']={'status':'ready','title':'Declared evidence','inputs':closure.archive_inputs(d,data['inventory'])}
    except (ValidationError,PermissionDenied) as exc:
        result['archive']={'status':'held','title':'Declared evidence','summary':'Obtain current go-live acceptance and Engineering final-document evidence for this exact inventory.','finding':str(exc)}
    return result


def current_index(d,data,inputs):
    row=delivery.latest(d,'archive',False)
    if not row or row.data['inventory']!=data['inventory'] or row.snapshot!=inputs:return None
    try:require(row.actor,d.case,'delivery.manage')
    except PermissionDenied:return None
    return row


def assessed(work):
    pk=Attempt.objects.filter(activity__work=work,phase='observed',result__head=work.source_head_id,result__has_key='archive').order_by('-pk').values_list('result__archive',flat=True).first()
    return DeliveryRecord.objects.filter(pk=pk,dossier_id=work.request['dossier'],kind='archive').first() if pk else None


def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor
    access(actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION);d,data,chosen=source(work,actor);native=LocalDeliveryAdapter().read_current(d)
    records=list(public_evidence(Evidence.objects.filter(case=work.case,pk__in=set(native['source_evidence_ids'])|set(chosen))).order_by('pk'))
    latest={KIND:work.source_head}
    for e in records:
        if e.kind not in latest or e.version>latest[e.kind].version:latest[e.kind]=e
    missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    # Check every exact selected artifact, not an unrelated newer artifact of the same kind.
    stale+=['inventory:'+kind for kind,pk in data['inventory'].items() if pk is not None and chosen[pk].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    observed=checks(d,data);index=current_index(d,data,observed['archive']['inputs']) if observed['archive']['status']=='ready' else None
    try:user=operator(work,value);owner={'status':'ready','id':user.pk}
    except ValidationError:owner={'status':'held','id':value['executor_id']}
    old=assessed(work)
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(e.pk,e.sha256) for e in latest.values()],
        'native':native,'checks':observed,'operator':owner,'current_archive':index.pk if index else None,'assessed':old.pk if old else None}
    state['hash']=digest(state);state['work_revision']=work.revision
    return state,latest,missing,stale,[],[]


def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Investigate final-document evidence and declared archive inventory'
    if missing or stale:return [],'Current required archive evidence is missing or stale: '+', '.join(missing+stale)
    if state['checks']['storage']['status']=='held':return ['ACT10'],'Resolve the reviewed storage and inventory rule'
    if state['checks']['archive']['status']=='held':return [],state['checks']['archive']['summary']
    if not state['current_archive'] and state['operator']['status']=='held':return ['ACT10'],'Resolve the authorised archive operator'
    if not state['assessed'] or state['assessed']!=state['current_archive']:return ['ACT08'],'Create or observe the exact current native archive index'
    return ['ACT13'],'Verify the current archive index and preserved source references'


def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    case=lock_case(work.execution_actor,work.case_id,'factory.execute');access(work.execution_actor,case,'factory.execute',DEFINITION)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    if case.revision!=work.case.revision:raise ValidationError('STALE_VERSION: archive sources changed while planning')
    d,data,rows=source(work,work.execution_actor);kind=choice['activity']
    if kind=='ACT04':return {'head':work.source_head_id,'dossier':d.pk,'checks':{k:v['status'] for k,v in checks(d,data).items()},'source_refs':sorted(rows)}
    if kind=='ACT10':
        storage(case);user=operator(work,value);return {'head':work.source_head_id,'operator':user.pk,'configuration_available':True}
    if kind=='ACT08':
        inputs=closure.archive_inputs(d,data['inventory']);row=current_index(d,data,inputs);created=False
        if not row:
            user=operator(work,value)
            row=closure.archive_artifacts(user,case.pk,d.pk,data['inventory'],data['inventory']['technical_document'],
                f'Native archive index from exact declared inventory; factory work {work.pk}, execution profile {work.policy_id}. No separate archive approval or physical purge.',case.revision);created=True
        return {'head':work.source_head_id,'dossier':d.pk,'archive':row.pk,'operator':row.actor_id,'created':created,'physical_purge_performed':False}
    if kind=='ACT13':result=verify(work,actor=work.execution_actor);work.status='verified';return result
    raise ValidationError('FORBIDDEN: unregistered archive activity')


def verify(work,actor=None):
    d,data,_=source(work,actor);row=assessed(work);current=closure.current_archive(d)
    if not row or row.pk!=current.pk or row.data['inventory']!=data['inventory']:raise ValidationError('Exact current source-bound native archive index required')
    if row.snapshot['physical_purge_performed'] is not False:raise ValidationError('The archive index cannot claim a physical purge')
    return {'head':work.source_head_id,'dossier':d.pk,'archive':row.pk,'verified':True,'verification_scope':'synthetic_native_archive_index',
        'external_bytes_verified':False,'external_authenticity_verified':False,'physical_purge_performed':False,
        'support_handover_received':False,'closure_approved':False,'financial_release_granted':False,'deployment_authorized':False}


@transaction.atomic
def correct(actor,work_id,expected,case_expected,inventory,reason):
    from .factory import access
    if type(expected) is not int or expected<1 or type(case_expected) is not int or case_expected<1:raise ValidationError('Exact rendered work and project versions required')
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);require(actor,w.case,'evidence.add')
    case=lock_case(actor,w.case_id,'delivery.read',case_expected);w.case=case
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    if w.revision!=expected or w.cancel_requested or w.status in ['cancelled','followup_needed']:raise ValidationError('STALE_VERSION: refresh archive work')
    if w.lease_until and w.lease_until>timezone.now():raise ValidationError('CONFLICT: wait for the current worker')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the inventory correction in at most2000 characters')
    d,data,_=source(w,actor,current=False);delivery.ensure_open(d);inventory_rows(case,inventory)
    if inventory==data['inventory']:raise ValidationError('The inventory is unchanged; recheck corrected prerequisites instead')
    previous=w.source_head_id;w.source_head=capture(actor,case,d,inventory,'factory.archive_source')
    w.status='ready';w.finding='';w.revision+=1;w.save()
    event(actor,case,'factory.archive_corrected',work=w.pk,previous=previous,current=w.source_head_id,reason=reason,spent=w.budget_used);return w


@transaction.atomic
def reassess(actor,work_id,expected,reason):
    from .factory import access
    if type(expected) is not int or expected<1:raise ValidationError('Exact rendered work version required')
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION)
    if w.revision!=expected or w.status!='verified' or w.cancel_requested:raise ValidationError('STALE_VERSION: select verified archive work')
    if w.lease_until and w.lease_until>timezone.now():raise ValidationError('CONFLICT: current worker owns this work')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain reassessment in at most2000 characters')
    try:verify(w)
    except (ValidationError,PermissionDenied):pass
    else:raise ValidationError('The exact archive index remains current')
    w.status='ready';w.finding='';w.revision+=1;w.save();event(actor,w.case,'factory.reassessment',work=w.pk,reason=reason,spent=w.budget_used);return w


@transaction.atomic
def cancel(actor,work_id,expected):
    """Settle an idle/expired local-index stop; an active worker keeps its fence."""
    from .factory import access,manage
    if type(expected) is not int or expected<1:raise ValidationError('Exact rendered work version required')
    w=Work.objects.select_for_update(of=('self',)).select_related('case').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION)
    if w.revision!=expected:raise ValidationError('STALE_VERSION: refresh archive work')
    if w.status in ['verified','followup_needed']:raise ValidationError('A verified index needs its native correction path')
    if w.status=='cancelled':return w
    if not w.cancel_requested:w=manage(actor,w.pk,w.revision,'cancel')
    if not w.lease_until or w.lease_until<=timezone.now():
        w.status='cancelled';w.finding='Stopped archive work retains every recorded native index and its source history.'
        w.lease_until=None;w.fence+=1;w.revision+=1;w.save()
        event(actor,w.case,'factory.archive_stopped',work=w.pk,spent=w.budget_used)
    return w


@transaction.atomic
def restart(actor,work_id,expected,case_expected,reason):
    """Explicit new human instruction for this local-index-only envelope, same budget."""
    from .factory import access
    if type(expected) is not int or type(case_expected) is not int or min(expected,case_expected)<1:raise ValidationError('Exact rendered work and project versions required')
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);require(actor,w.case,'evidence.add')
    case=lock_case(actor,w.case_id,'delivery.read',case_expected);w.case=case
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    if w.revision!=expected or w.status!='cancelled' or not w.cancel_requested:raise ValidationError('STALE_VERSION: select stopped archive work')
    if w.lease_until and w.lease_until>timezone.now():raise ValidationError('CONFLICT: current worker has not stopped')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the new archive instruction in at most2000 characters')
    d,data,_=source(w,actor,current=False);delivery.dossier_for(case,d.pk);delivery.ensure_open(d)
    previous=w.source_head_id;w.source_head=capture(actor,case,d,data['inventory'],'factory.archive_source')
    w.cancel_requested=False;w.status='ready';w.finding='';w.lease_until=None;w.fence+=1;w.revision+=1;w.save()
    event(actor,case,'factory.archive_restarted',work=w.pk,previous=previous,current=w.source_head_id,reason=reason,spent=w.budget_used);return w


def projection(actor,work):
    from .factory import access
    access(actor,work.case,envelope=DEFINITION);d,data,rows=source(work,actor,current=False);observed=checks(d,data)
    try:source(work,actor);intake_current=True
    except (ValidationError,PermissionDenied):intake_current=False
    changed=False
    if work.status=='verified':
        try:verify(work,actor=actor)
        except (ValidationError,PermissionDenied):changed=True
    can_correct=can_restart=can_settle=False
    if not (work.lease_until and work.lease_until>timezone.now()):
        try:
            require(actor,work.case,'factory.manage');require(actor,work.case,'evidence.add');delivery.ensure_open(d)
            if work.status=='cancelled' and work.cancel_requested:
                delivery.dossier_for(work.case,d.pk)
                can_restart=True
            can_correct=not work.cancel_requested and work.status not in ['cancelled','followup_needed']
            can_settle=work.cancel_requested and work.status not in ['cancelled','verified','followup_needed']
        except (ValidationError,PermissionDenied):pass
    return {'dossier':d,'data':data,'inventory':[{'kind':kind,'evidence':rows.get(pk),'missing':pk is None} for kind,pk in data['inventory'].items()],
        'checks':observed,'assessment':assessed(work),'readiness_changed':changed,'intake_current':intake_current,
        'can_correct':can_correct,'can_restart':can_restart,'can_settle':can_settle}


def attempt_projection(attempt):
    allowed={'head','dossier','archive','operator','created','checks','source_refs','configuration_available','verified','verification_scope',
        'external_bytes_verified','external_authenticity_verified','physical_purge_performed','support_handover_received','closure_approved','financial_release_granted','deployment_authorized'}
    return {k:v for k,v in attempt.result.items() if k in allowed}
