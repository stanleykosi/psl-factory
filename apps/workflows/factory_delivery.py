"""Native delivery gates to release evidence; no deployment or payment authority."""
import json,hashlib
from datetime import timedelta
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Evidence,Audit
from apps.core.services import lock_case,add_evidence,event
from apps.core.evidence_access import public_evidence
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.services import decision_authority
from apps.documents.contracts import digest,validate
from apps.pmo import delivery
from apps.pmo.models import DeliveryDossier,DeliveryRecord
from adapters.delivery import LocalDeliveryAdapter
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt

DEFINITION='delivery-release/v1'
KIND='agent_private_delivery_intake'
PROTOCOL='factory-delivery-intake/v1'
INTAKE={'type':'object','properties':{'protocol':{'const':PROTOCOL},'dossier_id':{'type':'integer','minimum':1}},'required':['protocol','dossier_id'],'additionalProperties':False}
STATIONS={
    'planning_sources':('Design, test and UAT evidence','Obtain current source-owned design, test and UAT evidence.'),
    'planning_decision':('Planning exit','A current Planning exit decision is required.'),
    'kickoff_and_upstream':('Kickoff and delivery approvals','Record the actual kickoff and current QA, UAT and Engineering approvals.'),
    'release_evidence':('Release request and approvals','Link the actual GLPI request and its current deployment approvals.'),
    'baseline':('Project baseline','The delivery baseline changed. Review a new candidate and retain the earlier evidence.'),
    'intake':('Intake authority','Review the delivery intake provenance and current source authority.'),
    'source_coverage':('Source coverage','This source history needs a narrower review.')}

def held(name,error):
    title,summary=STATIONS[name]
    return {'status':'held','title':title,'summary':summary,'finding':'; '.join(error.messages) if isinstance(error,ValidationError) else str(error)}

def intake_authority(work):
    require(work.source_head.created_by,work.case,'delivery.read')
    require(work.source_head.created_by,work.case,'factory.start')


def subject(work,actor=None,current=True):
    actor=actor or work.actor;require(actor,work.case,'delivery.read')
    e=work.source_head
    if not e or e.case_id!=work.case_id or e.kind!=KIND or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():raise ValidationError('Exact delivery intake and source hash required')
    try:value=json.loads(e.body)
    except (ValueError,TypeError) as exc:raise ValidationError('Typed delivery intake required') from exc
    validate(INTAKE,value)
    if not Audit.objects.filter(case=work.case,actor=e.created_by,action='factory.delivery_intake',data={'evidence_id':e.pk,'sha256':e.sha256}).exists():raise ValidationError('Native delivery intake provenance required')
    if current:intake_authority(work)
    if value['dossier_id']!=work.request['dossier']:raise ValidationError('Delivery intake subject differs from the recorded work')
    return delivery.dossier_for(work.case,value['dossier_id'],current=current)


def reaffirmation(actor,work):
    """A current human instruction can replace withdrawn intake authority, not old business facts."""
    from .factory import access
    from apps.agents.factory_coordinator import pending,has_receipt
    if work.definition not in [DEFINITION,'delivery-hypercare/v1']:raise ValidationError('Select release or stability work')
    access(actor,work.case,'factory.manage',work.definition)
    for action in ['factory.start','evidence.add']:require(actor,work.case,action)
    if work.cancel_requested or work.status in ['cancelled','followup_needed']:raise ValidationError('Stopped work needs its native follow-up')
    if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: a worker owns this instruction')
    original=pending(work)
    if original and not has_receipt(original):raise ValidationError('Check the original planning response before renewing source authority')
    d=subject(work,actor,current=False);delivery.dossier_for(work.case,d.pk);delivery.ensure_open(d)
    try:subject(work,actor)
    except PermissionDenied:pass
    else:raise ValidationError('The original intake authority is still current')
    return d,digest({'protocol':'factory-delivery-reaffirmation/v1','work':work.pk,'revision':work.revision,
        'head':work.source_head_id,'sha256':work.source_head.sha256,'dossier':d.pk,'baseline':d.baseline,'case_revision':work.case.revision})


@transaction.atomic
def reaffirm(actor,work_id,expected,case_expected,evidence_id,reason,packet):
    if any(type(n) is not int or n<1 for n in [expected,case_expected,evidence_id]):raise ValidationError('Exact current work, project and evidence references required')
    work=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id)
    work.case=lock_case(actor,work.case_id,'factory.manage',case_expected)
    list(Grant.objects.select_for_update().filter(case=work.case).order_by('pk'))
    if work.revision!=expected:raise ValidationError('STALE_VERSION: refresh the current instruction')
    d,current=reaffirmation(actor,work)
    if not isinstance(packet,str) or packet!=current:raise ValidationError('STALE_VERSION: review the exact current instruction and project')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the fresh instruction in at most2000 characters')
    if not public_evidence(Evidence.objects.filter(case=work.case,pk=evidence_id)).exists():raise ValidationError('Select available public project evidence for this instruction')
    previous=work.source_head
    evidence=add_evidence(actor,work.case_id,KIND,previous.body,'psl:factory-delivery-intake/reaffirmation/v1',work.case.revision)
    event(actor,work.case,'factory.delivery_intake',evidence_id=evidence.pk,sha256=evidence.sha256)
    event(actor,work.case,'factory.delivery_intake_reaffirmed',work=work.pk,previous=previous.pk,current=evidence.pk,
        evidence=evidence_id,reason=reason.strip(),case_revision=case_expected,packet=packet)
    work.source_head=evidence;work.status='ready';work.finding='';work.observation_hash='';work.fence+=1;work.revision+=1;work.save()
    return work

@transaction.atomic
def start(actor,case_id,key,dossier_id,reference,expected=None,*,envelope=DEFINITION):
    from .factory import access
    if envelope not in [DEFINITION,'delivery-hypercare/v1']:raise ValidationError('Closed delivery intent required')
    case=lock_case(actor,case_id,'factory.start',expected);access(actor,case,'factory.start',envelope)
    if case.kind!='project':raise ValidationError('Delivery work requires a project')
    if not isinstance(key,str) or not key.isascii() or not 1<=len(key)<=100 or not isinstance(reference,str) or not reference.strip() or len(reference)>100:raise ValidationError('Bounded work identity and reference required')
    d=delivery.dossier_for(case,dossier_id);delivery.ensure_open(d)
    payload={'dossier':d.pk,'reference':reference};sha=digest(payload);business=digest([str(case.pk),envelope,d.candidate_id])
    old=Work.objects.filter(case=case).filter(Q(key=key)|Q(definition=envelope,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=envelope or old.key==key and old.request_hash!=sha:raise ValidationError('IDEMPOTENCY_CONFLICT: delivery intent has changed payload or initiator')
        return old
    e=add_evidence(actor,case.pk,KIND,json.dumps({'protocol':PROTOCOL,'dossier_id':d.pk},sort_keys=True),'psl:factory-delivery-intake/v1')
    event(actor,case,'factory.delivery_intake',evidence_id=e.pk,sha256=e.sha256)
    work=Work.objects.create(case=case,actor=actor,key=key,definition=envelope,request=payload,request_hash=sha,business_key=business,source_head=e)
    event(actor,case,'factory.started',work=work.pk,definition=envelope);return work

def checks(d):
    result={}
    def plan(x):return {'planning_id':delivery.approved_plan(x).pk}
    for name,fn in [('planning_sources',delivery.planning_inputs),('planning_decision',plan),('kickoff_and_upstream',delivery.upstream),('release_evidence',delivery.readiness_inputs)]:
        try:result[name]={'status':'ready','title':STATIONS[name][0],'inputs':fn(d)}
        except (ValidationError,PermissionDenied) as exc:result[name]=held(name,exc)
    return result

def planning_owners(case):
    from django.contrib.auth import get_user_model
    candidates=list(get_user_model().objects.filter(is_active=True,grant__case=case,grant__active=True,grant__action='delivery.planning_decide').distinct()[:101])
    if len(candidates)>100:raise ValidationError('Planning owner candidate budget exceeded')
    result=[]
    for actor in candidates:
        try:require(actor,case,'case.read');require(actor,case,'delivery.read');decision_authority(actor,case,'PMO Lead');result.append(actor.pk)
        except (ValidationError,PermissionDenied):pass
    return result

def prepared(work):
    pk=Attempt.objects.filter(activity__work=work,phase='observed',result__head=work.source_head_id,result__has_key='release_ready').order_by('-pk').values_list('result__release_ready',flat=True).first()
    return DeliveryRecord.objects.filter(pk=pk,dossier_id=work.request['dossier'],kind='release_ready').first() if pk else None

def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor
    access(actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION);d=subject(work,actor)
    data=LocalDeliveryAdapter().read_current(d);observed=checks(d)
    records=list(public_evidence(Evidence.objects.filter(case=work.case,pk__in=data['source_evidence_ids'])).order_by('pk'))
    latest={work.source_head.kind:work.source_head}
    for e in records:
        if e.kind not in latest or e.version>latest[e.kind].version:latest[e.kind]=e
    missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(e.pk,e.sha256) for e in latest.values()],
        'dossier':d.pk,'native':data,'checks':observed,'planning_owners':planning_owners(work.case),
        'release_recorded':d.records.filter(kind='release_outcome').exists(),'prepared':prepared(work).pk if prepared(work) else None}
    state['hash']=digest(state);state['work_revision']=work.revision
    return state,latest,missing,stale,[],[]

def investigation_key(work,state):return digest(['ACT04',state['sources'],state['checks'],state['native']])

def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    key=investigation_key(work,state)
    if not Activity.objects.filter(work=work,key=key,status='succeeded').exists():return ['ACT04'],'Investigate current delivery sources and native gate prerequisites'
    if stale or missing:return [],'Current required delivery evidence is missing or stale: '+', '.join(missing+stale)
    for name in ['planning_sources','planning_decision','kickoff_and_upstream','release_evidence']:
        row=state['checks'][name]
        if row['status']=='held':
            if name=='planning_decision' and not state['planning_owners']:return ['ACT10'],'Resolve the configured native Planning exit authority'
            return [],row['summary']
    ready=prepared(work)
    if ready and ready.snapshot==state['checks']['release_evidence']['inputs']:return ['ACT13'],'Verify current native release-evidence readiness'
    if state['release_recorded']:return [],'An actual release is already recorded; use native exception controls instead of preparing retrospective readiness'
    return ['ACT08'],'Prepare release readiness from current source approvals'

def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    case=lock_case(work.execution_actor,work.case_id,'factory.execute');access(work.execution_actor,case,'factory.execute',DEFINITION)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    if case.revision!=work.case.revision:raise ValidationError('STALE_VERSION: delivery sources changed before the command')
    d=subject(work,work.execution_actor);kind=choice['activity']
    if kind=='ACT04':
        observed=checks(d)
        return {'head':work.source_head_id,'dossier':d.pk,'checks':{k:v['status'] for k,v in observed.items()},
            'findings':{k:v['finding'] for k,v in observed.items() if v['status']=='held'},'deployment_dispatched':False}
    if kind=='ACT10':
        if not planning_owners(case):raise ValidationError('owner_needed: Configure current native PMO Lead Planning exit authority')
        return {'head':work.source_head_id,'native_planning_owner_available':True}
    if kind=='ACT08':
        current=delivery.readiness_inputs(d)
        old=delivery.latest(d,'release_ready',False)
        if old and old.snapshot==current:
            require(old.actor,case,'delivery.manage');ready=old
        else:ready=delivery.prepare_readiness(work.execution_actor,case.pk,d.pk,case.revision)
        return {'head':work.source_head_id,'dossier':d.pk,'release_ready':ready.pk,'deployment_authorized':False}
    if kind=='ACT13':
        result=verify(work,actor=work.execution_actor);work.status='verified';return result
    raise ValidationError('FORBIDDEN: unregistered delivery activity')

def verify(work,actor=None):
    d=subject(work,actor);row=prepared(work)
    if not row or row.snapshot!=delivery.readiness_inputs(d):raise ValidationError('Current exact native release-evidence record required')
    require(row.actor,work.case,'delivery.manage')
    if row.snapshot.get('deployment_authorized') is not False or row.snapshot.get('financial_controls')!='independent':raise ValidationError('Independent deployment and financial controls must remain explicit')
    return {'head':work.source_head_id,'dossier':d.pk,'release_ready':row.pk,'verified':True,
        'verification_scope':'synthetic_native_release_evidence_readiness','deployment_authorized':False,'deployment_dispatched':False,'financial_release_granted':False,'external_authenticity_verified':False}

def projection(actor,work):
    from .factory import access
    access(actor,work.case,envelope=DEFINITION);current=True;intake_finding=None
    try:d=subject(work,actor,current=False);subject(work,actor)
    except (ValidationError,PermissionDenied) as exc:
        d=delivery.dossier_for(work.case,work.request['dossier'],current=False);current=False;intake_finding=str(exc)
    observed=checks(d)
    if intake_finding:observed['intake']=held('intake',intake_finding)
    try:delivery.dossier_for(work.case,d.pk)
    except (ValidationError,PermissionDenied) as exc:current=False;observed['baseline']=held('baseline',exc)
    authorities={}
    if current and not work.cancel_requested and work.status not in ['verified','cancelled','followup_needed'] and observed['planning_sources']['status']=='ready' and observed['planning_decision']['status']=='held':
        try:
            require(actor,work.case,'delivery.planning_decide')
            for verdict in ['approve','return','reject']:
                try:authorities[verdict]=decision_authority(actor,work.case,'PMO Lead',verdict)
                except (ValidationError,PermissionDenied):pass
        except (ValidationError,PermissionDenied):pass
    can_decide=bool(authorities)
    packet=digest({'inputs':observed['planning_sources']['inputs'],'authorities':authorities}) if can_decide else None
    changed=False
    if work.status=='verified':
        try:verify(work,actor=actor)
        except (ValidationError,PermissionDenied):changed=True
    coverage=None
    try:
        current_sources=LocalDeliveryAdapter().read_current(d);ids=current_sources['source_evidence_ids'];coverage=current_sources['coverage']
        sources=list(public_evidence(Evidence.objects.filter(case=work.case,pk__in=ids)).order_by('kind','pk'))
    except (ValidationError,PermissionDenied) as exc:
        sources=[];observed['source_coverage']=held('source_coverage',exc)
    owner_ids=planning_owners(work.case) if current and observed['planning_sources']['status']=='ready' and observed['planning_decision']['status']=='held' else []
    from django.contrib.auth import get_user_model
    owner_names=[u.get_full_name() or u.username for u in get_user_model().objects.filter(pk__in=owner_ids).order_by('pk')]
    instruction_packet=None
    try:_,instruction_packet=reaffirmation(actor,work)
    except (ValidationError,PermissionDenied):pass
    author_current=True
    try:intake_authority(work)
    except PermissionDenied:author_current=False
    return {'dossier':d,'checks':observed,'can_decide':can_decide,'ready':prepared(work),'readiness_changed':changed,
        'can_reaffirm':instruction_packet is not None,'intake_current':current,'intake_authority_current':author_current,
        'planning_owner_names':owner_names,'public_sources':sources,'source_coverage':coverage,'decision_packet':packet,'allowed_verdicts':list(authorities),
        'decision_evidence':list(public_evidence(Evidence.objects.filter(case=work.case))) if can_decide else []}

@transaction.atomic
def decide(actor,work_id,expected,verdict,evidence_id,note,case_expected,packet_sha256):
    from .factory import access
    work=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,work.case,envelope=DEFINITION)
    if type(case_expected) is not int or case_expected<1:raise ValidationError('Exact rendered project version required')
    case=lock_case(actor,work.case_id,'delivery.planning_decide',case_expected)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    work.case=case;panel=projection(actor,work)
    if work.revision!=expected or verdict not in panel['allowed_verdicts'] or not packet_sha256 or packet_sha256!=panel['decision_packet']:raise ValidationError('STALE_VERSION: current exact Planning exit sources and authority required')
    if not public_evidence(Evidence.objects.filter(case=case,pk=evidence_id)).exists():raise ValidationError('Choose an available public delivery decision source')
    result=delivery.decide_planning(actor,case.pk,work.request['dossier'],verdict,evidence_id,note,case.revision)
    work.revision+=1;work.status='ready';work.finding='';work.save();return result

@transaction.atomic
def reassess(actor,work_id,expected,reason):
    from .factory import access
    work=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,work.case,'factory.manage',DEFINITION)
    if work.revision!=expected or work.status!='verified' or work.cancel_requested:raise ValidationError('STALE_VERSION: select verified delivery evidence')
    if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: current worker owns this work')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the reviewed reassessment in at most2000 characters')
    try:verify(work,actor=actor)
    except (ValidationError,PermissionDenied):pass
    else:raise ValidationError('The exact readiness remains current')
    work.status='ready';work.finding='';work.revision+=1;work.save()
    event(actor,work.case,'factory.reassessment',work=work.pk,reason=reason,spent=work.budget_used);return work

def attempt_projection(attempt):
    allowed={'head','dossier','checks','release_ready','verified','verification_scope','deployment_authorized','deployment_dispatched','financial_release_granted','external_authenticity_verified','native_planning_owner_available'}
    return {k:v for k,v in attempt.result.items() if k in allowed}
