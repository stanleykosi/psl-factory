"""P03/P16 coordination over the incumbent Case and native engagement identity.

The intake packet is an immutable pointer, never a project master or an approval.
Planning may begin with explicitly unknown inputs. Registration consumes real plan
source evidence and remains a human native command during Planning.
"""
import hashlib,json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Evidence,Audit
from apps.core.services import lock_case,add_evidence,event
from apps.core.evidence_access import public_evidence
from apps.identity.services import require
from apps.documents.contracts import digest,validate
from adapters.forecast import KEY
from apps.pmo import engagement,planning
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt

DEFINITION='engagement/v1'
KIND='agent_private_engagement_intake'
RECEIVED='factory.engagement_intake'
LINKED='factory.engagement_planning_linked'


def readable(actor,case,purpose='factory.read'):
    from .factory import access
    access(actor,case,purpose,DEFINITION)
    if case.kind!='project':raise ValidationError('Existing project workspace required; intake does not create another project master')


def capture_current(case,pk=None):
    source=engagement.current_capture(case)
    if pk is not None and source.pk!=pk:raise ValidationError('Engagement capture changed; review its successor without replacing historical identity')
    for action in ['case.read','engagement.read','engagement.capture']:require(source.actor,case,action)
    if not get_user_model().objects.filter(pk=source.actor_id,is_active=True).exists():raise PermissionDenied('Current engagement source authority required')
    evidence=engagement.proof(case,source.evidence_id)
    if hashlib.sha256(evidence.body.encode()).hexdigest()!=evidence.sha256:raise ValidationError('Exact retained engagement source hash required')
    if source.data['route']=='A':
        from apps.pmo.models import RFPDisposition
        d=RFPDisposition.objects.filter(pk=source.data['rfp_disposition'],rfp__case=case,kind='route_a',outcome__result='won').first()
        if not d or d.snapshot.get('case')!=str(case.pk) or d.snapshot.get('outcome')!=d.outcome_id:raise ValidationError('Actual same-project won-RFP disposition required; receipt alone is not Route A')
    elif source.data['route']=='C' and evidence.kind!='product_input':raise ValidationError('Product-paper source required for Route C')
    return source


def pointer(case,evidence):
    if evidence is None or evidence.case_id!=case.pk or evidence.kind!=KIND:raise ValidationError('Exact engagement intake pointer required')
    if evidence.sha256!=hashlib.sha256(evidence.body.encode()).hexdigest():raise ValidationError('Intake pointer hash mismatch')
    try:value=json.loads(evidence.body)
    except (ValueError,TypeError):raise ValidationError('Closed engagement pointer required') from None
    if not isinstance(value,dict) or set(value)!={'protocol','capture','capture_hash','source','sha256'} or value['protocol']!='engagement-intake/v1':raise ValidationError('Closed engagement pointer required')
    if not Audit.objects.filter(case=case,actor=evidence.created_by,action=RECEIVED,data={'head':evidence.pk,'sha256':evidence.sha256}).exists():raise ValidationError('Native intake provenance required')
    source=engagement.Record.objects.filter(case=case,kind='capture',pk=value['capture']).first()
    if not source or (digest(source.data),source.evidence_id,source.evidence.sha256)!=(value['capture_hash'],value['source'],value['sha256']):raise ValidationError('Exact native capture and retained source required')
    return source


def write_pointer(actor,case,source):
    value={'protocol':'engagement-intake/v1','capture':source.pk,'capture_hash':digest(source.data),'source':source.evidence_id,'sha256':source.evidence.sha256}
    head=add_evidence(actor,case.pk,KIND,json.dumps(value,sort_keys=True,separators=(',',':')),'psl:engagement-intake/v1')
    event(actor,case,RECEIVED,head=head.pk,sha256=head.sha256)
    return head


@transaction.atomic
def start(actor,case_id,key,capture_id,reference,expected):
    case=lock_case(actor,case_id,'factory.start');readable(actor,case,'factory.start');validate(KEY,key)
    if not isinstance(reference,str) or not reference.strip() or len(reference)>100:raise ValidationError('Bounded engagement work reference required')
    if type(capture_id) is not int or capture_id<1:raise ValidationError('Exact native capture identity required')
    source=capture_current(case,capture_id)
    payload={'capture':source.pk,'reference':reference}
    business_key=digest([DEFINITION,str(case.pk)])
    old=Work.objects.filter(case=case).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business_key)).first()
    if old:
        if old.definition!=DEFINITION or old.actor_id!=actor.pk or old.request!=payload:raise ValidationError('IDEMPOTENCY_CONFLICT: use the existing engagement work and reviewed source recovery')
        return old
    if type(expected) is not int or case.revision!=expected:raise ValidationError('STALE_VERSION: refresh the engagement workspace')
    head=write_pointer(actor,case,source)
    work=Work.objects.create(case=case,actor=actor,key=key,definition=DEFINITION,business_key=business_key,request=payload,request_hash=digest(payload),source_head=head)
    event(actor,case,'factory.started',work=work.pk,definition=DEFINITION)
    return work


@transaction.atomic
def receive(actor,case_id,key,route,evidence_id,reference,expected,rfp_disposition=None):
    """User-selected source/route only. Reuse an exact current native capture."""
    case=lock_case(actor,case_id,'factory.start');readable(actor,case,'factory.start');validate(KEY,key)
    if not Work.objects.filter(case=case,definition=DEFINITION).exists() and (type(expected) is not int or case.revision!=expected):raise ValidationError('STALE_VERSION: refresh before engagement intake')
    if type(evidence_id) is not int or evidence_id<1 or rfp_disposition is not None and (type(rfp_disposition) is not int or rfp_disposition<1):raise ValidationError('Exact native source and optional won-RFP disposition identities required')
    existing=engagement.latest(case,'capture')
    exact={'route':route,'reference':reference,'rfp_disposition':rfp_disposition}
    if existing and (existing.data!=exact or existing.evidence_id!=evidence_id):
        raise ValidationError('Existing engagement source differs; review the native capture instead of replacing it from intake')
    if not existing:
        if type(expected) is not int or case.revision!=expected:raise ValidationError('STALE_VERSION: refresh before engagement capture')
        existing=engagement.capture(actor,case_id,route,evidence_id,reference,'factory-capture-'+digest([key,str(case.pk)]),rfp_disposition)
        case.refresh_from_db()
    return start(actor,case_id,key,existing.pk,reference,case.revision if not Work.objects.filter(case=case,definition=DEFINITION).exists() else expected)


def linked(work):
    return Audit.objects.filter(case=work.case,action=LINKED,data__work=work.pk).order_by('-pk').first()


def planning_context(work,actor):
    planning.readable(actor,work.case)
    item=planning.latest(work.case,'packet')
    if item is None:return None,None
    item,value=planning.packet(work.case,item.pk)
    return item,value


def identity_conflicts(actor,case):
    from apps.pmo.identity_resolution import report
    rows=report(actor,case.pk)['decisions']
    return [r['id'] for r in rows if r.get('status')=='other_case_access_held' or r.get('currently_accepted') and r.get('relation') in ['alias','unresolved']]


def native(work,actor):
    source=pointer(work.case,work.source_head);capture_current(work.case,source.pk)
    state={'capture':source.pk,'route':source.data['route'],'assignment':None,'registration':None,'planning_packet':None,'planning_work':None,'identity_conflicts':identity_conflicts(actor,work.case)}
    for name,fn in [('assignment',engagement.current_assignment),('registration',engagement.current_registration)]:
        try:state[name]=fn(work.case).pk
        except (ValidationError,PermissionDenied,get_user_model().DoesNotExist):pass
    packet,value=planning_context(work,actor)
    if packet:state['planning_packet']=packet.pk
    receipt=linked(work)
    if receipt:
        child=Work.objects.filter(case=work.case,pk=receipt.data['planning_work'],definition='planning/v1').first()
        if not child or child.request['engagement']!=source.pk or receipt.data['capture']!=source.pk:raise ValidationError('Original same-engagement planning handoff needs source-owned recovery')
        state.update(planning_work=child.pk,planning_status=child.status,planning_source=child.source_head_id,receipt=receipt.pk)
    return state


def snapshot(work,value,reader=None):
    actor=reader or work.execution_actor;readable(actor,work.case,'factory.read' if reader else 'factory.execute')
    state=native(work,actor)
    source=pointer(work.case,work.source_head)
    records=[work.source_head,source.evidence]
    latest={e.kind:e for e in records}
    missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    observed={'case_revision':work.case.revision,'profile':work.policy_id,'source_head':work.source_head_id,'sources':[(e.pk,e.sha256) for e in records],'native':state}
    observed['hash']=digest(observed);observed['work_revision']=work.revision
    return observed,latest,missing,stale,[],[]


def investigation_key(work,observed):return digest(['ACT04',observed['sources'],observed['native']['capture']])


def eligible(work,value,observed,latest,missing,stale,tasks,jobs):
    n=observed['native']
    if not Activity.objects.filter(work=work,key=investigation_key(work,observed),status='succeeded').exists():return ['ACT04'],'Investigate route evidence, possible duplicate identities and planning gaps'
    if missing or stale:return [],'Correct the configured engagement source requirements: '+', '.join(missing+stale)
    if n['identity_conflicts']:return [],'Resolve the recorded identity conflict through the native PMO identity controls'
    if not n['planning_packet']:return ['ACT07'],'Prepare native planning inputs with unknown values preserved'
    if not n['assignment']:return [],'Current source-owned PM assignment is needed; investigation and planning inputs remain available'
    if not n['planning_work']:return ['ACT11'],'Hand the same engagement to native planning work'
    if n['planning_status'] in ['cancelled','followup_needed'] or Work.objects.filter(pk=n['planning_work'],cancel_requested=True).exists():return [],'Native planning work was stopped; review its original intent rather than creating another'
    if not n['registration']:return [],'Register the supplied incumbent project identifier during Planning using actual plan evidence'
    if n['planning_source']!=n['planning_packet']:return [],'Continue native planning so it adopts the current same-engagement packet'
    return ['ACT13'],'Verify current human assignment, registration and the exact native planning handoff'


def empty_planning_payload():
    from adapters.planning_packet import SOURCE_KINDS
    from apps.policy.planning_validators import TEAMS
    return {**{key:None for key in SOURCE_KINDS},'stakeholders':[{'team':team,'contact_id':None,'evidence_id':None} for team in TEAMS],'questions':[]}


def act(work,choice,value,latest,missing,tasks,jobs):
    actor=work.execution_actor;case=lock_case(actor,work.case_id,'factory.execute');readable(actor,case,'factory.execute')
    if case.revision!=work.case.revision:raise ValidationError('STALE_VERSION: engagement changed before the command')
    source=pointer(case,work.source_head);capture_current(case,source.pk)
    kind=choice['activity']
    if kind=='ACT04':
        from apps.agents.engagement import investigate
        return {'investigation':investigate(actor,case.pk),'planning_inputs':'Unknown requirements, contacts and estimates stay unknown; no plan or approval is fabricated'}
    if kind=='ACT07':
        old,_=planning_context(work,actor)
        packet=old or planning.capture(actor,case.pk,empty_planning_payload())
        return {'planning_packet':packet.pk,'unknowns_preserved':True,'plan_evidence_created':False}
    if kind=='ACT11':
        assignment=engagement.current_assignment(case)
        if identity_conflicts(actor,case):raise ValidationError('Recorded identity conflict requires human reconciliation')
        packet,_=planning_context(work,actor)
        if packet is None:raise ValidationError('Native planning packet required')
        child=Work.objects.filter(case=case,definition='planning/v1',business_key=digest(['planning/v1',str(case.pk),source.pk])).first()
        if child:
            from .factory import access
            access(actor,case,'factory.read','planning/v1')
            if child.cancel_requested or child.status in ['cancelled','followup_needed']:raise ValidationError('Original planning work is stopped; no replacement work is created')
        else:
            from .factory_planning import start as start_planning
            case.refresh_from_db()
            child=start_planning(actor,case.pk,'engagement-planning-'+str(work.pk),packet.pk,work.request['reference'],case.revision)
        receipt=linked(work)
        data={'work':work.pk,'capture':source.pk,'assignment':assignment.pk,'packet':packet.pk,'planning_work':child.pk,'head':work.source_head_id}
        if receipt and receipt.data!=data:raise ValidationError('Original handoff receipt is retained; no implicit replacement')
        if not receipt:receipt=event(actor,case,LINKED,**data)
        return {'planning_work':child.pk,'planning_packet':packet.pk,'handoff':receipt.pk,'approval_granted':False,'registration_due':True}
    if kind=='ACT13':
        result=verify(work,actor);work.status='verified';return result
    raise ValidationError('FORBIDDEN: unregistered engagement command')


def verify(work,actor=None):
    actor=actor or work.execution_actor;readable(actor,work.case,'factory.execute')
    n=native(work,actor)
    if n['identity_conflicts'] or not all(n[k] for k in ['assignment','registration','planning_packet','planning_work']):raise ValidationError('Current assignment, registration and conflict-free native planning handoff required')
    if n['planning_source']!=n['planning_packet'] or n['planning_status'] in ['cancelled','followup_needed'] or Work.objects.filter(pk=n['planning_work'],cancel_requested=True).exists():raise ValidationError('Current active same-engagement planning work required')
    registration=engagement.current_registration(work.case)
    plan=public_evidence(Evidence.objects.filter(case=work.case,pk=registration.data['plan'],kind='plan')).first()
    if not plan or plan.sha256!=registration.data['plan_sha256']:raise ValidationError('Actual retained planning evidence for registration required')
    if not engagement.Identifier.objects.filter(case=work.case,tenant=work.case.tenant,namespace=registration.data['namespace'],normalized=registration.data['normalized']).exists():raise ValidationError('Existing native registered project identity required')
    return {'verified':True,'verification_scope':'current_engagement_identity_and_internal_planning_handoff','head':work.source_head_id,
        **{key:n[key] for key in ['capture','assignment','registration','planning_packet','planning_work','receipt']},
        'planning_complete':False,'signature_required':False,'external_master_verified':False}


def verified_output(work):
    record=Attempt.objects.filter(activity__work=work,activity__kind='ACT13',phase='observed').order_by('-pk').first()
    if not record or record.result!=verify(work):raise ValidationError('Recorded engagement handoff changed; review current native evidence')
    return record.result


@transaction.atomic
def reassess(actor,work_id,expected,reason,capture_id=None):
    work=Work.objects.select_for_update().select_related('case').get(pk=work_id,definition=DEFINITION)
    case=lock_case(actor,work.case_id,'factory.manage');readable(actor,case,'factory.manage')
    if type(expected) is not int or work.revision!=expected or work.cancel_requested or work.status in ['cancelled','followup_needed']:raise ValidationError('STALE_VERSION: refresh the current engagement work')
    if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: wait for the current worker')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the source-owned reassessment')
    source=capture_current(case,capture_id)
    previous=pointer(case,work.source_head)
    if source.pk!=previous.pk:
        if linked(work):raise ValidationError('Original planning work is tied to the previous capture; source-owned planning recovery is required before another handoff')
        if planning.latest(case,'packet') is not None:raise ValidationError('A planning packet already exists; correct it through native planning before changing the engagement link')
        work.source_head=write_pointer(actor,case,source)
    elif work.status=='verified':
        try:verified_output(work)
        except (ValidationError,PermissionDenied):pass
        else:raise ValidationError('The recorded handoff remains current')
    work.status='ready';work.finding='';work.revision+=1;work.save()
    event(actor,case,'factory.engagement_reassessed',work=work.pk,previous=previous.pk,capture=source.pk,reason=reason,spent=work.budget_used)
    return work


@transaction.atomic
def human(actor,work_id,expected,case_revision,operation,data):
    work=Work.objects.select_for_update().select_related('case').get(pk=work_id,definition=DEFINITION)
    case=lock_case(actor,work.case_id,'engagement.'+operation,case_revision);readable(actor,case)
    if work.revision!=expected or work.cancel_requested or work.status in ['verified','cancelled','followup_needed']:raise ValidationError('STALE_VERSION: refresh the open engagement work')
    if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: wait for current worker observation')
    capture_current(case,pointer(case,work.source_head).pk)
    if operation not in ['assign','register']:raise ValidationError('Choose a native human assignment or registration command')
    result=getattr(engagement,operation)(actor,case.pk,**data)
    if work.status=='waiting':work.status='ready';work.finding=''
    work.revision+=1;work.save()
    event(actor,case,'factory.engagement_human_recorded',work=work.pk,record=result.pk,kind=operation)
    return result


def projection(actor,work):
    readable(actor,work.case)
    result={'capture':None,'assignment':None,'registration':None,'planning_work':None,'finding':'','changed':False}
    try:result.update(native(work,actor))
    except (ValidationError,PermissionDenied):result.update(finding='Current engagement source or planning authority needs review',changed=True)
    if work.status=='verified':
        try:verified_output(work)
        except (ValidationError,PermissionDenied,get_user_model().DoesNotExist):result.update(changed=True,finding='The prior identity or planning handoff needs current-source review')
    return result


def human_roles(actor,case,operation):
    from apps.policy.engagement_validators import ASSIGN,REGISTER
    from apps.policy.services import active_component,reference_values
    component,purpose=(ASSIGN,'assignment') if operation=='assign' else (REGISTER,'registration')
    try:
        require(actor,case,'engagement.'+operation)
        roles=reference_values(active_component(component,case))[0][purpose+'_roles'];accepted=[]
        for role in roles:
            try:engagement.authority(actor,case,component,role,purpose);accepted.append(role)
            except (ValidationError,PermissionDenied):pass
        return accepted
    except (ValidationError,PermissionDenied):return []


def operator_projection(actor,work):
    from .factory_views import permitted
    state=projection(actor,work);out={'engagement':state}
    if state['changed']:
        out.update(state='Engagement evidence needs review',blocker=state['finding'],next_action='Review native engagement and planning sources',can_advance=False,needs_me=permitted(actor,work,'factory.manage'))
    elif work.status not in ['verified','cancelled','followup_needed']:
        # Native human decisions must not hide earlier useful agent work.
        if not state['planning_packet'] or not Activity.objects.filter(work=work,kind='ACT04',status='succeeded',attempts__phase='observed',attempts__observation__source_head=work.source_head_id).exists():return out
        for name,action,label in [('assignment','engagement.assign','Record the source-owned PM assignment'),('registration','engagement.register','Register the supplied project identifier during Planning')]:
            if not state[name] and (name=='assignment' or state['planning_work']):
                allowed=bool(human_roles(actor,work.case,'assign' if name=='assignment' else 'register'))
                out.update(next_action=label,needs_me=allowed,department_wait=True,owner=(actor.get_full_name() or actor.username) if allowed else 'PMO authority needed',blocker=label)
                break
    return out


def attempt_projection(attempt,actor):
    if attempt.phase=='failed':return {'status':'held','next_action':'Review current engagement source and native authority'}
    allowed={'verified','verification_scope','planning_work','planning_packet','handoff','capture','assignment','registration','receipt','unknowns_preserved','plan_evidence_created','registration_due','approval_granted','planning_complete','signature_required','external_master_verified'}
    try:
        from .factory import access
        access(actor,attempt.activity.work.case,'factory.read','planning/v1')
    except PermissionDenied:
        allowed-={'planning_work','planning_packet','handoff','receipt'}
    result={k:v for k,v in attempt.result.items() if k in allowed}
    if 'investigation' in attempt.result:result['investigation']='Route evidence, identity candidates and assignment/registration dependencies investigated; no identity, role or approval created'
    return result
