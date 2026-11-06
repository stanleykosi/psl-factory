"""Declared actual evidence → native report → prescribed human decision → native closure."""
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
from apps.documents.contracts import validate,digest
from apps.documents.models import Template
from apps.documents.controlled import current_version,validate_review
from apps.policy.services import active_component,reference_values,decision_authority
from apps.pmo import delivery,delivery_closure as closure
from apps.pmo.models import MeetingVersion,DeliveryDocumentBinding,DeliveryRecord
from apps.pmo.delivery_documents import draft_delivery_document
from adapters.delivery import LocalDeliveryAdapter
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt,HumanTask
from .factory_delivery import investigation_key
from apps.core.read_observation import read_observation

DEFINITION='delivery-closure/v1'
KIND='agent_private_closure_intake'
PROTOCOL='factory-closure-intake/v1'
FIELDS=['template_id','retrospective_id','report_evidence_id']
ID={'anyOf':[{'type':'integer','minimum':1,'maximum':9223372036854775807},{'type':'null'}]}
INPUT={'type':'object','properties':{k:ID for k in FIELDS},'required':FIELDS,'additionalProperties':False}
SCHEMA={'type':'object','properties':{'protocol':{'const':PROTOCOL},'dossier_id':{'type':'integer','minimum':1},'inputs':INPUT},
    'required':['protocol','dossier_id','inputs'],'additionalProperties':False}


def finding(exc):return '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)


def input_rows(case,inputs):
    validate(INPUT,inputs)
    if any(pk is not None and type(pk) is not int for pk in inputs.values()):raise ValidationError('Exact integer references or unprovided values required')
    ids=[]
    if inputs['template_id'] is not None and not Template.objects.filter(case=case,pk=inputs['template_id'],definition__document_type='project_artifact').exists():
        raise ValidationError('Choose this project controlled closure template')
    if inputs['retrospective_id'] is not None:
        meeting=MeetingVersion.objects.filter(pk=inputs['retrospective_id'],meeting__case=case,kind='retrospective').first()
        if not meeting:raise ValidationError('Choose this project recorded retrospective version')
        ids.append(meeting.evidence_id)
    if inputs['report_evidence_id'] is not None:
        if not public_evidence(Evidence.objects.filter(case=case,pk=inputs['report_evidence_id'],kind='closure_report')).exists():
            raise ValidationError('Choose this project public PM closure report evidence')
        ids.append(inputs['report_evidence_id'])
    rows={e.pk:e for e in public_evidence(Evidence.objects.filter(case=case,pk__in=ids))}
    if set(ids)!=set(rows):raise ValidationError('Restricted retrospective evidence requires its authorised native interface')
    return rows


def source(work,actor=None,current=True):
    require(actor or work.actor,work.case,'delivery.read');e=work.source_head
    if not e or e.case_id!=work.case_id or e.kind!=KIND or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():raise ValidationError('Exact native closure intake required')
    try:data=json.loads(e.body)
    except (ValueError,TypeError):raise ValidationError('Typed closure intake required') from None
    validate(SCHEMA,data)
    audit=Audit.objects.filter(case=work.case,actor_id=e.created_by_id,action__in=['factory.closure_intake','factory.closure_source'],data={'evidence_id':e.pk,'sha256':e.sha256}).first()
    if not audit or data['dossier_id']!=work.request['dossier']:raise ValidationError('Exact same-project closure provenance required')
    if current:
        for action in ['delivery.read','evidence.add','factory.start' if audit.action=='factory.closure_intake' else 'factory.manage']:require(e.created_by,work.case,action)
    return delivery.dossier_for(work.case,data['dossier_id'],current=current),data,input_rows(work.case,data['inputs'])


def capture(actor,case,d,inputs,action):
    e=add_evidence(actor,case.pk,KIND,json.dumps({'protocol':PROTOCOL,'dossier_id':d.pk,'inputs':inputs},sort_keys=True),'psl:'+PROTOCOL)
    event(actor,case,action,evidence_id=e.pk,sha256=e.sha256);return e


@transaction.atomic
def start(actor,case_id,key,dossier_id,inputs,reference,expected=None):
    from .factory import access
    case=lock_case(actor,case_id,'factory.start',expected);access(actor,case,'factory.start',DEFINITION);require(actor,case,'evidence.add')
    if case.kind!='project':raise ValidationError('Project closure requires a project')
    if not isinstance(key,str) or not key.isascii() or not 1<=len(key)<=100 or not isinstance(reference,str) or not reference.strip() or len(reference)>160:
        raise ValidationError('Bounded closure identity and description required')
    d=delivery.dossier_for(case,dossier_id);input_rows(case,inputs)
    payload={'dossier':d.pk,'reference':reference};business=digest([str(case.pk),DEFINITION,d.candidate_id]);sha=digest(payload)
    old=Work.objects.filter(case=case).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.key==key and old.request_hash!=sha:raise ValidationError('IDEMPOTENCY_CONFLICT: changed closure intent')
        if source(old)[1]['inputs']!=inputs:raise ValidationError('Review changed inputs in the existing closure work')
        return old
    delivery.ensure_open(d)
    w=Work.objects.create(case=case,actor=actor,key=key,definition=DEFINITION,request=payload,request_hash=sha,business_key=business,
        source_head=capture(actor,case,d,inputs,'factory.closure_intake'))
    event(actor,case,'factory.started',work=w.pk,definition=DEFINITION);return w


def selected(data):return {k:data['inputs'][k] for k in FIELDS[1:]}


def prerequisites(d,data):
    if any(data['inputs'][k] is None for k in FIELDS):raise ValidationError('Provide the controlled template, actual retrospective and PM report')
    return closure.closure_inputs(d,selected(data))


def document(work):
    pk=Attempt.objects.filter(activity__work=work,phase='observed',result__head=work.source_head_id,result__has_key='document_version').order_by('-pk').values_list('result__document_version',flat=True).first()
    binding=DeliveryDocumentBinding.objects.select_related('version__document','version__template').filter(version_id=pk,dossier_id=work.request['dossier'],purpose='closure').first()
    return binding.version if binding else None


def owners(case,role,action):
    try:ids={r['user_id'] for r in reference_values(active_component('D05.role_principal_assignments',case)) if r['role']==role}
    except (ValidationError,PermissionDenied):return []
    result=[]
    for user in get_user_model().objects.filter(pk__in=ids,is_active=True).order_by('pk'):
        try:require(user,case,action);decision_authority(user,case,role,'approve');result.append(user)
        except (ValidationError,PermissionDenied):pass
    return result


def operator(work,value):
    user=get_user_model().objects.filter(pk=value['executor_id'],is_active=True).first()
    if not user:raise ValidationError('owner_needed: Configure the already-authorised PM for native closure finalisation')
    try:
        for action in ['case.read','delivery.read','factory.execute','delivery.manage']:require(user,work.case,action)
        decision_authority(user,work.case,'PM')
    except (ValidationError,PermissionDenied):raise ValidationError('owner_needed: Closure finaliser needs current project permissions and PM authority') from None
    return user


@read_observation
def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor
    access(actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION);d,data,chosen=source(work,actor);native=LocalDeliveryAdapter().read_current(d)
    rows=list(public_evidence(Evidence.objects.filter(case=work.case,pk__in=set(native['source_evidence_ids'])|set(chosen))).order_by('pk'))
    latest={KIND:work.source_head}
    for e in rows:
        if e.kind not in latest or e.version>latest[e.kind].version:latest[e.kind]=e
    missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    due=timezone.now()-timedelta(seconds=value['max_age_seconds'])
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<due]
    stale+=['selected:'+str(pk) for pk,e in chosen.items() if e.created_at<due]
    # Fence on the native aggregate contract once. Independent per-station breadth
    # remains in the actual investigation/UI, not every internal plan comparison.
    try:
        inputs=prerequisites(d,data)
        checks={'ready_to_prepare':True,'checks':[],'inputs':inputs}
    except (ValidationError,PermissionDenied) as exc:
        checks={'ready_to_prepare':False,'checks':[{'status':'held','summary':finding(exc)}],'inputs':None}
    v=document(work);issue='';review=None;approval=None
    last_decision=delivery.latest(d,'closure_decision',False)
    if v:
        if last_decision and last_decision.data['verdict']=='approve' and last_decision.data['version_id']==v.pk:
            try:approval=closure.current_closure_approval(d,v.pk)[0]
            except (ValidationError,PermissionDenied):pass
        try:
            if not approval:current_version(work.case,v.pk)
            validate_review(work.case,v)
        except (ValidationError,PermissionDenied) as exc:issue=finding(exc)
        review=HumanTask.objects.filter(version=v,status='open').first()
    try:user=operator(work,value);finaliser={'status':'current','id':user.pk}
    except ValidationError:finaliser={'status':'held','id':value['executor_id']}
    closed=delivery.latest(d,'closure',False)
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(e.pk,e.sha256) for e in latest.values()],
        'native':native,'checks':checks,'document':v.pk if v else None,'document_issue':issue,
        'review':review.pk if review else None,'review_owners':[u.pk for u in owners(work.case,'PMO Lead','document.review_controlled')],
        'decision_owners':[u.pk for u in owners(work.case,'Head of PMO','delivery.closure_decide')],
        'last_decision':[last_decision.pk,last_decision.data['verdict'],last_decision.data['version_id']] if last_decision else None,
        'approval':approval.pk if approval else None,'operator':finaliser,'closure':closed.pk if closed else None}
    state['hash']=digest(state);state['work_revision']=work.revision
    return state,latest,missing,stale,[],[]


def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Investigate closure evidence and prescribed human decisions'
    if missing or stale:return [],'Current required closure evidence is missing or stale: '+', '.join(missing+stale)
    if state['closure']:return ['ACT13'],'Verify the recorded native closure against current exact source and authority'
    if not state['checks']['ready_to_prepare'] or any(source(work,work.execution_actor)[1]['inputs'][k] is None for k in FIELDS):
        return [],next((c['summary'] for c in state['checks']['checks'] if c['status']!='current'),'Provide the closure template and actual source records')
    if not state['document']:return ['ACT09'],'Prepare the native controlled PM report'
    v=document(work)
    if v.template.definition.get('internal_review_required') is not False and not HumanTask.objects.filter(version=v).exists():
        try:current_version(work.case,v.pk)
        except (ValidationError,PermissionDenied):return [],'The draft is retained; review current source and recipient configuration before requesting review'
        return ['ACT09'],'Request the configured controlled-document review'
    if state['review']:
        return ([], 'Await the prescribed controlled-document review') if state['review_owners'] else (['ACT10'],'Resolve the current controlled-document reviewer')
    if state['document_issue']:return [],'Review the current report, source or configured document review requirement'
    if not state['approval']:
        if state['last_decision'] and state['last_decision'][2]==state['document'] and state['last_decision'][1] in ['return','reject']:
            return [],'The Head of PMO returned or rejected this exact report; record corrected source evidence'
        return ([], 'Await the Head of PMO decision on this exact report') if state['decision_owners'] else (['ACT10'],'Resolve the current Head of PMO decision owner')
    if state['operator']['status']=='held':return ['ACT10'],'Resolve the already-authorised PM finaliser'
    return ['ACT11'],'Record native closure after the current prescribed decision'


def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    case=lock_case(work.execution_actor,work.case_id,'factory.execute');access(work.execution_actor,case,'factory.execute',DEFINITION)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    if case.revision!=work.case.revision:raise ValidationError('STALE_VERSION: closure sources changed while planning')
    d,data,_=source(work,work.execution_actor);kind=choice['activity']
    if kind=='ACT04':
        return {'head':work.source_head_id,'dossier':d.pk,'checks':LocalDeliveryAdapter().read_closure(d,selected(data)),
            'separate_retrospective_approval':False,'finance_attestation_inferred':False}
    if kind=='ACT09':
        prerequisites(d,data);v=document(work)
        if not v:v=draft_delivery_document(work.execution_actor,case.pk,d.pk,'closure',data['inputs']['template_id'],selected(data),case.revision)
        task=None;waiting=None
        if v.template.definition.get('internal_review_required') is not False and not HumanTask.objects.filter(version=v).exists():
            from apps.documents.controlled import request_review
            try:current_version(case,v.pk)
            except (ValidationError,PermissionDenied):waiting='The draft is retained. Review its current source and recipient configuration before requesting review.'
            else:case.refresh_from_db();task=request_review(work.execution_actor,case.pk,v.pk,case.revision)
        result={'head':work.source_head_id,'document_version':v.pk,'native_review_task':task.pk if task else None}
        if waiting:result['waiting']=waiting
        return result
    if kind=='ACT10':
        v=document(work)
        if v and HumanTask.objects.filter(version=v,status='open').exists():
            if not owners(case,'PMO Lead','document.review_controlled'):raise ValidationError('owner_needed: Configure the current controlled-document reviewer')
        elif v:
            try:closure.current_closure_approval(d,v.pk)
            except (ValidationError,PermissionDenied):
                if not owners(case,'Head of PMO','delivery.closure_decide'):raise ValidationError('owner_needed: Configure current Head of PMO closure authority')
            else:operator(work,value)
        return {'head':work.source_head_id,'current_authority_checked':True}
    if kind=='ACT11':
        v=document(work)
        if not v:raise ValidationError('Exact prepared closure report required')
        prerequisites(d,data);current_version(case,v.pk);validate_review(case,v);closure.current_closure_approval(d,v.pk)
        row=closure.finalize_closure(operator(work,value),case.pk,d.pk,case.revision)
        return {'head':work.source_head_id,'dossier':d.pk,'closure':row.pk,'document_version':v.pk,'operator':row.actor_id}
    if kind=='ACT13':result=verify(work,actor=work.execution_actor);work.status='verified';return result
    raise ValidationError('FORBIDDEN: unregistered closure activity')


def verify(work,actor=None):
    d,data,_=source(work,actor);v=document(work);row=delivery.latest(d,'closure')
    if not v or v.template_id!=data['inputs']['template_id']:raise ValidationError('Exact current-source controlled closure report required')
    decision,binding=closure.current_closure_approval(d,v.pk)
    if binding.data!=selected(data) or row.data['version_id']!=v.pk or row.data['decision_id']!=decision.pk or row.snapshot!=binding.snapshot:
        raise ValidationError('Native closure must bind the exact current report, source and prescribed decision')
    require(row.actor,work.case,'delivery.manage');decision_authority(row.actor,work.case,'PM');validate_review(work.case,v)
    if row.snapshot['debt_waived'] is not False or row.snapshot['deployment_authorized'] is not False:raise ValidationError('Closure cannot grant independent financial or release authority')
    return {'verified':True,'head':work.source_head_id,'dossier':d.pk,'closure':row.pk,'document_version':v.pk,'decision':decision.pk,
        'verification_scope':'synthetic_native_project_closure','debt_waived':False,'deployment_authorized':False,
        'external_authenticity_verified':False,'separate_retrospective_approval':False,'finance_attestation_inferred':False}


@transaction.atomic
def correct(actor,work_id,expected,case_expected,inputs,reason):
    from .factory import access
    if type(expected) is not int or type(case_expected) is not int or min(expected,case_expected)<1:raise ValidationError('Exact rendered work and project versions required')
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);require(actor,w.case,'evidence.add');case=lock_case(actor,w.case_id,'delivery.read',case_expected);w.case=case
    if w.revision!=expected or w.cancel_requested or w.status in ['cancelled','followup_needed']:raise ValidationError('STALE_VERSION: refresh closure work')
    if w.lease_until and w.lease_until>timezone.now():raise ValidationError('CONFLICT: wait for the current worker')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the reviewed correction in at most2000 characters')
    d,data,_=source(w,actor,current=False);delivery.dossier_for(case,d.pk);delivery.ensure_open(d);input_rows(case,inputs)
    if inputs==data['inputs']:
        v=document(w)
        if not v:raise ValidationError('The selected inputs are unchanged')
        try:current_version(case,v.pk);prerequisites(d,data)
        except (ValidationError,PermissionDenied):pass
        else:raise ValidationError('The current report and selected inputs remain valid; provide corrected evidence')
    previous=w.source_head_id;w.source_head=capture(actor,case,d,inputs,'factory.closure_source');w.status='ready';w.finding='';w.revision+=1;w.save()
    event(actor,case,'factory.closure_corrected',work=w.pk,previous=previous,current=w.source_head_id,reason=reason,spent=w.budget_used);return w


@transaction.atomic
def decide(actor,work_id,expected,case_expected,version_id,verdict,evidence_id,note):
    from .factory import access
    if any(type(pk) is not int or pk<1 for pk in [expected,case_expected,version_id,evidence_id]):raise ValidationError('Exact rendered versions and evidence references required')
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION)
    if w.revision!=expected or w.cancel_requested or w.lease_until and w.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh the current closure work')
    d,data,_=source(w,actor);v=document(w)
    if not v or v.pk!=version_id:raise ValidationError('Exact current-source closure version required')
    prerequisites(d,data);validate_review(w.case,v)
    return closure.decide_closure(actor,w.case_id,v.pk,verdict,evidence_id,note,case_expected)


@transaction.atomic
def review(actor,work_id,expected,case_expected,version_id,verdict,note):
    from .factory import access
    from apps.documents.controlled import review_version
    if any(type(pk) is not int or pk<1 for pk in [expected,case_expected,version_id]):raise ValidationError('Exact rendered versions required')
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION)
    if w.revision!=expected or w.cancel_requested or w.lease_until and w.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh closure work')
    source(w,actor);v=document(w)
    if not v or v.pk!=version_id:raise ValidationError('Exact current closure document required')
    return review_version(actor,w.case_id,v.pk,verdict,note,case_expected)


@transaction.atomic
def cancel(actor,work_id,expected):
    from .factory import access,manage,cancellation_status
    if type(expected) is not int or expected<1:raise ValidationError('Exact rendered work version required')
    w=Work.objects.select_for_update(of=('self',)).select_related('case').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION)
    if w.revision!=expected:raise ValidationError('STALE_VERSION: refresh closure work')
    if w.status in ['verified','followup_needed']:raise ValidationError('Recorded closure requires its native follow-up path')
    if w.status=='cancelled':return w
    if not w.cancel_requested:w=manage(actor,w.pk,w.revision,'cancel')
    if not w.lease_until or w.lease_until<=timezone.now():
        w.status=cancellation_status(w);w.finding='Stopped work preserves every native report, decision and recorded closure.'
        w.lease_until=None;w.fence+=1;w.revision+=1;w.save()
        event(actor,w.case,'factory.closure_stopped',work=w.pk,spent=w.budget_used)
    return w


@transaction.atomic
def restart(actor,work_id,expected,case_expected,reason):
    from .factory import access
    if type(expected) is not int or type(case_expected) is not int or min(expected,case_expected)<1:raise ValidationError('Exact rendered work and project versions required')
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);require(actor,w.case,'evidence.add');case=lock_case(actor,w.case_id,'delivery.read',case_expected);w.case=case
    if w.revision!=expected or w.status!='cancelled' or not w.cancel_requested:raise ValidationError('STALE_VERSION: select stopped closure work')
    if w.lease_until and w.lease_until>timezone.now():raise ValidationError('CONFLICT: current worker has not stopped')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the fresh closure instruction in at most2000 characters')
    d,data,_=source(w,actor,current=False);delivery.dossier_for(case,d.pk);delivery.ensure_open(d)
    previous=w.source_head_id;w.source_head=capture(actor,case,d,data['inputs'],'factory.closure_source')
    w.cancel_requested=False;w.status='ready';w.finding='';w.lease_until=None;w.fence+=1;w.revision+=1;w.save()
    event(actor,case,'factory.closure_restarted',work=w.pk,previous=previous,current=w.source_head_id,reason=reason,spent=w.budget_used);return w


def projection(actor,work):
    from .factory import access,profile
    access(actor,work.case,envelope=DEFINITION);d,data,rows=source(work,actor,current=False);v=document(work)
    report=LocalDeliveryAdapter().read_closure(d,selected(data));closed=delivery.latest(d,'closure',False);changed=False;issue=''
    try:source(work,actor);intake_current=True
    except (ValidationError,PermissionDenied) as exc:intake_current=False;issue=finding(exc)
    if work.status=='verified':
        try:verify(work,actor=actor)
        except (ValidationError,PermissionDenied) as exc:changed=True;issue=finding(exc)
    pending_review=bool(v and HumanTask.objects.filter(version=v,status='open').exists())
    reviewer_names=[u.get_full_name() or u.username for u in owners(work.case,'PMO Lead','document.review_controlled')] if pending_review else []
    decision_names=[u.get_full_name() or u.username for u in owners(work.case,'Head of PMO','delivery.closure_decide')]
    can_review=can_correct=can_restart=can_settle=False;verdicts=[];review_verdicts=[]
    live=not work.cancel_requested and not closed and not (work.lease_until and work.lease_until>timezone.now())
    if live:
        try:require(actor,work.case,'factory.manage');require(actor,work.case,'evidence.add');delivery.ensure_open(d);can_correct=True
        except (ValidationError,PermissionDenied):pass
        if v and intake_current:
            try:
                prerequisites(d,data);current_version(work.case,v.pk)
                if pending_review:
                    require(actor,work.case,'document.review_controlled')
                    for verdict in ['approve','return','reject']:
                        try:decision_authority(actor,work.case,'PMO Lead',verdict);review_verdicts.append(verdict)
                        except (ValidationError,PermissionDenied):pass
                    can_review=bool(review_verdicts)
                else:
                    validate_review(work.case,v);require(actor,work.case,'delivery.closure_decide')
                    for verdict in ['approve','return','reject']:
                        try:decision_authority(actor,work.case,'Head of PMO',verdict);verdicts.append(verdict)
                        except (ValidationError,PermissionDenied):pass
            except (ValidationError,PermissionDenied) as exc:issue=finding(exc)
    if not (work.lease_until and work.lease_until>timezone.now()):
        try:
            require(actor,work.case,'factory.manage');require(actor,work.case,'evidence.add');delivery.ensure_open(d);delivery.dossier_for(work.case,d.pk)
            can_restart=work.status=='cancelled' and work.cancel_requested
            can_settle=work.cancel_requested and work.status not in ['cancelled','verified','followup_needed']
        except (ValidationError,PermissionDenied):pass
    next_options=[];next_action='Review current closure evidence and prescribed decisions'
    try:
        _,value=profile(work);state,*args=snapshot(work,value);next_options,next_action=eligible(work,value,state,*args)
    except (ValidationError,PermissionDenied):pass
    last_decision=delivery.latest(d,'closure_decision',False)
    if last_decision and (not v or last_decision.data['version_id']!=v.pk):last_decision=None
    return {'dossier':d,'data':data,'report':report,'document':v,'decision':last_decision,'closure':closed,'finding':issue,
        'intake_current':intake_current,'readiness_changed':changed,'pending_review':pending_review,
        'reviewer_names':reviewer_names,'decision_names':decision_names,'can_review':can_review,'review_verdicts':review_verdicts,'verdicts':verdicts,
        'can_correct':can_correct,'can_restart':can_restart,'can_settle':can_settle,'next_options':next_options,'next_action':next_action}


def attempt_projection(attempt):
    allowed={'head','dossier','checks','document_version','native_review_task','operator','closure','decision','verified','verification_scope',
        'separate_retrospective_approval','finance_attestation_inferred','current_authority_checked','debt_waived','deployment_authorized','external_authenticity_verified','waiting'}
    return {k:v for k,v in attempt.result.items() if k in allowed}
