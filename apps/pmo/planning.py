"""P17/P21/P25 references over existing immutable evidence, meetings and P02 controls."""
import json,hashlib
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case,Evidence,Audit
from apps.core.services import lock_case,add_evidence,event
from apps.core.evidence_access import public_evidence
from apps.core.workbench import active
from apps.identity.models import Grant
from apps.identity.services import require
from apps.documents.contracts import validate,digest
from apps.policy.services import active_component,reference_values,decision_authority
from apps.policy.planning_validators import COMPONENT,TEAMS
from adapters.planning_packet import INPUT,SOURCE_KINDS,PURPOSES,KINDS,PlanningPacketAdapter
from .models import ActionItem,MeetingVersion,Baseline,ApprovalRequest
from . import engagement,approvals

SUBJECTS={'scope':'planning_scope','estimates':'planning_estimates'}
OWNER_ROLES={'scope':'Product Owner','estimates':'Engineering Lead'}

def readable(a,c):
    active(a);require(a,c,'case.read');require(a,c,'planning.read')
    if c.kind!='project':raise PermissionDenied('Planning sources belong to a project workspace')

def locked(a,case_id,purpose):
    c=lock_case(a,case_id,'planning.'+purpose);readable(a,c)
    if c.kind!='project':raise ValidationError('Project planning workspace required')
    list(get_user_model().objects.select_for_update().filter(pk=a.pk));list(Grant.objects.select_for_update().filter(case=c).order_by('pk'))
    active(a);return c

def proof(c,pk,kinds=None):
    e=public_evidence(c.evidence.all()).filter(pk=pk).first()
    if not e or kinds and e.kind not in kinds:raise ValidationError('Exact same-case public source of the required kind required')
    return e

def latest(c,kind):return c.evidence.filter(kind=KINDS[kind]).order_by('-version').first()

def write(a,c,kind,value):
    e=add_evidence(a,c.pk,KINDS[kind],json.dumps(value,sort_keys=True,separators=(',',':')),'psl:planning-v1')
    event(a,c,'planning.recorded',kind=kind,evidence_id=e.pk,sha256=e.sha256);return e

def read(c,e,kind,purpose):
    if not e or e.case_id!=c.pk or e.kind!=KINDS[kind] or not Audit.objects.filter(case=c,actor=e.created_by,action='planning.recorded',data={'kind':kind,'evidence_id':e.pk,'sha256':e.sha256}).exists():raise ValidationError('Actual domain-recorded immutable planning provenance required')
    if hashlib.sha256(e.body.encode()).hexdigest()!=e.sha256:raise ValidationError('Planning content hash mismatch')
    readable(e.created_by,c);require(e.created_by,c,'planning.'+purpose)
    return PlanningPacketAdapter.parse(e)

def payload_context(c,payload):
    validate(INPUT,payload)
    if {x['team'] for x in payload['stakeholders']}!=set(TEAMS) or len({x['key'] for x in payload['questions']})!=len(payload['questions']):raise ValidationError('Map all four distinct teams and distinct question keys')
    for key,kinds in SOURCE_KINDS.items():
        if payload[key] is not None:proof(c,payload[key],kinds)
    for row in payload['stakeholders']:
        if row['evidence_id'] is not None:proof(c,row['evidence_id'])
        if row['contact_id'] is not None:
            person=get_user_model().objects.filter(pk=row['contact_id'],is_active=True).first()
            if not person:raise ValidationError('Actual current stakeholder contact required')
            require(person,c,'planning.participate')
    heads={}
    for q in payload['questions']:
        if q['evidence_id'] is not None:proof(c,q['evidence_id'])
        if q['action_id'] is not None:
            item=ActionItem.objects.filter(case=c,pk=q['action_id'],current__isnull=False).first()
            if not item:raise ValidationError('Exact same-case current action required')
            heads[str(item.pk)]=item.current_id
    from .planning_sources import context
    context(c,payload)
    return heads

@transaction.atomic
def capture(a,case_id,payload,predecessor=None):
    c=locked(a,case_id,'coordinate');old=latest(c,'packet')
    if (old.pk if old else None)!=predecessor:raise ValidationError('Explicit latest packet predecessor required')
    source=engagement.current_capture(c);heads=payload_context(c,payload)
    from .planning_sources import context,validate_successor,historical_predecessor
    prior,old_value,skipped=historical_predecessor(c)
    if prior:validate_successor(c,old_value['payload'],payload)
    item=write(a,c,'packet',{'protocol':'planning-packet/v2','engagement_id':source.pk,'engagement_hash':digest(source.data),'payload':payload,'action_heads':heads,'source_pins':context(c,payload)})
    event(a,c,'planning.packet_source_lineage',packet_id=item.pk,explicit_predecessor=predecessor,
        trusted_historical_predecessor=prior.pk if prior else None,skipped_heads=skipped,
        historical_authority_reused=False,new_capture_authority_checked=True,
        reason='Retained immutable native source history; skipped heads contribute no trusted claims, approval or completeness.')
    return item

def packet(c,pk=None):
    e=latest(c,'packet')
    if pk is not None and (not e or e.pk!=pk):raise ValidationError('Current planning packet required')
    v=read(c,e,'packet','coordinate')
    keys={'protocol','engagement_id','engagement_hash','payload','action_heads'}
    if v.get('protocol')=='planning-packet/v2':keys.add('source_pins')
    if set(v)!=keys or v['protocol'] not in ['planning-packet/v1','planning-packet/v2']:raise ValidationError('Closed planning packet protocol required')
    if v['protocol']=='planning-packet/v2':
        from .planning_sources import context
        if context(c,v['payload'])!=v['source_pins']:raise ValidationError('Exact declared source/version pins changed')
    source=engagement.current_capture(c)
    if (v['engagement_id'],v['engagement_hash'])!=(source.pk,digest(source.data)) or payload_context(c,v['payload'])!=v['action_heads']:raise ValidationError('Engagement, source authority or linked action head changed; capture a successor packet')
    return e,v

@transaction.atomic
def align(a,case_id,packet_id,purpose,meeting_version_id):
    c=locked(a,case_id,'coordinate');e,_=packet(c,packet_id);require(a,c,'meeting.read')
    if purpose not in PURPOSES:raise ValidationError('Choose the documented alignment purpose')
    m=MeetingVersion.objects.filter(pk=meeting_version_id,meeting__case=c,meeting__current_id=meeting_version_id,kind='alignment').first()
    if not m or m.occurred_at>timezone.now():raise ValidationError('Current actually held formal alignment meeting required')
    value={'packet_id':e.pk,'packet_sha256':e.sha256,'purpose':purpose,'meeting_version_id':m.pk}
    old=latest(c,purpose)
    if old:
        try:
            if read(c,old,purpose,'coordinate')==value:return old
        except (ValidationError,PermissionDenied):pass
    return write(a,c,purpose,value)

@transaction.atomic
def open_requests(a,case_id,packet_id):
    c=locked(a,case_id,'route');e,_=packet(c,packet_id)
    marker=Audit.objects.filter(case=c,action='planning.requests_opened',data__packet_id=e.pk).order_by('-pk').first()
    if marker:return marker.data
    from .gates import register_candidate
    wrapper=add_evidence(a,c.pk,'requirements',json.dumps({'planning_packet_id':e.pk,'planning_packet_sha256':e.sha256},sort_keys=True),'psl:planning-request-subject-v1')
    candidate=register_candidate(a,c.pk,'planning-packet-'+str(e.pk),wrapper.pk,None)
    ids={}
    for key,kind in SUBJECTS.items():
        request_source=add_evidence(a,c.pk,'approval_request',json.dumps({'planning_packet_id':e.pk,'planning_packet_sha256':e.sha256,'purpose':kind},sort_keys=True),'psl:planning-department-request-v1')
        r=approvals.create_request(a,c.pk,kind+'-'+str(e.pk),candidate.pk,kind,None,None,request_source.pk)
        ids[key]=r.pk
    value={'packet_id':e.pk,'candidate_id':candidate.pk,'requests':ids}
    event(a,c,'planning.requests_opened',**value);return value

def requests(c,e,reader):
    approvals.readable(reader,c)
    marker=Audit.objects.filter(case=c,action='planning.requests_opened',data__packet_id=e.pk).order_by('-pk').first()
    if not marker:raise ValidationError('Open the separate department-owned scope/estimate requests')
    readable(marker.actor,c);require(marker.actor,c,'planning.route');value=marker.data;observations={}
    for key,kind in SUBJECTS.items():
        r=ApprovalRequest.objects.select_related('case','candidate__requirements').filter(pk=value['requests'][key],case=c,candidate_id=value['candidate_id'],kind=kind).first()
        if not r or r.candidate.case_id!=c.pk or r.candidate.requirements.case_id!=c.pk or PlanningPacketAdapter.parse(r.candidate.requirements)!={'planning_packet_id':e.pk,'planning_packet_sha256':e.sha256}:raise ValidationError('Exact packet-correlated department subject required')
        approvals.current_request(r);s=r.source_receipts.order_by('-pk').first();o=s.observations.order_by('-pk').first() if s else None
        if not o:raise ValidationError('Current department-owned source observation required: '+key)
        require(reader,c,'approval.source.read:'+s.system)
        approvals.current_observation(o);_,route,_=approvals.context(s)
        if route['owner_role']!=OWNER_ROLES[key] or s.payload['decision']!='accepted':raise ValidationError('Separate accepted source decision from '+OWNER_ROLES[key]+' required')
        observations[key]=o.pk
    return value,observations

def criteria(c):
    p=active_component(COMPONENT,c);return p,reference_values(p)[0]

def comparison_context(c,e,p,rules):
    base=Baseline.objects.filter(case=c,signed__isnull=False).first()
    if not base:raise ValidationError('An actual signed baseline is required for contract comparison')
    from .signatures import assert_current_signed_baseline
    assert_current_signed_baseline(c)
    item=latest(c,'comparison');v=read(c,item,'comparison','compare')
    expected={'packet_id':e.pk,'packet_sha256':e.sha256,'sow_id':base.sow_id,'signature_id':base.signed_id,'policy_id':p.pk}
    if any(v.get(k)!=x for k,x in expected.items()) or v.get('verdict')!='no_difference':raise ValidationError('Current exact signed-contract comparison required; resolve differences through controlled commercial/change work')
    actor=item.created_by
    if actor.pk!=rules['comparison_reviewer_id'] or rules['independent_comparison'] and actor.pk==e.created_by_id:raise PermissionDenied('Configured independent comparison reviewer required')
    if v.get('authority')!=decision_authority(actor,c,rules['comparison_reviewer_role']):raise ValidationError('Comparison authority changed')
    return item.pk

@transaction.atomic
def compare(a,case_id,packet_id,verdict,evidence_id):
    c=locked(a,case_id,'compare');e,_=packet(c,packet_id);p,rules=criteria(c)
    if verdict not in ['no_difference','difference_unresolved']:raise ValidationError('Record a source-backed match or unresolved difference')
    if a.pk!=rules['comparison_reviewer_id'] or rules['independent_comparison'] and a.pk==e.created_by_id:raise PermissionDenied('Configured comparison reviewer required')
    auth=decision_authority(a,c,rules['comparison_reviewer_role']);base=Baseline.objects.filter(case=c,signed__isnull=False).first()
    if not base:raise ValidationError('Actual signed contract required; no signature prerequisite for planning capture')
    source=proof(c,evidence_id)
    previous=latest(c,'comparison')
    if previous and Audit.objects.filter(case=c,actor=previous.created_by,action='planning.recorded',data={'kind':'comparison','evidence_id':previous.pk,'sha256':previous.sha256}).exists():
        before=PlanningPacketAdapter.parse(previous)
        if before.get('packet_id')==e.pk and before.get('verdict')=='difference_unresolved' and verdict=='no_difference' and before.get('evidence_id')==source.pk:raise ValidationError('New supporting evidence is required to resolve a previously recorded contract difference')
    return write(a,c,'comparison',{'packet_id':e.pk,'packet_sha256':e.sha256,'sow_id':base.sow_id,'signature_id':base.signed_id,'policy_id':p.pk,'verdict':verdict,'evidence_id':source.pk,'authority':auth})

def inputs(c,e,comparison_required,reader):
    _,v=packet(c,e.pk);payload=v['payload']
    from .planning_sources import require_complete
    if v['protocol']!='planning-packet/v2':raise ValidationError('Legacy packet retains history only; capture explicit source bindings in a successor for current readiness')
    correlation=require_complete(c,payload)
    p,rules=criteria(c)
    if any(payload[k] is None for k in SOURCE_KINDS):raise ValidationError('PRD, scope and owning-team estimate sources remain unknown')
    for row in payload['stakeholders']:
        if row['team'] in rules['require_named_contacts'] and (row['contact_id'] is None or row['evidence_id'] is None):raise ValidationError('Configured named stakeholder/contact proof remains unknown')
    for q in payload['questions']:
        if q['state'] in rules['blocking_question_states']:raise ValidationError('Configured question disposition blocks readiness: '+q['key'])
        if q['action_id'] is not None and ActionItem.objects.get(pk=q['action_id']).current.status not in rules['allowed_action_states']:raise ValidationError('Configured linked-action state is not ready')
    links={};meeting_ids=[]
    for purpose in PURPOSES:
        item=latest(c,purpose);link=read(c,item,purpose,'coordinate')
        if set(link)!={'packet_id','packet_sha256','purpose','meeting_version_id'} or (link['packet_id'],link['packet_sha256'],link['purpose'])!=(e.pk,e.sha256,purpose):raise ValidationError('Both alignment purposes must refer to this exact current packet')
        m=MeetingVersion.objects.filter(pk=link['meeting_version_id'],meeting__case=c,meeting__current_id=link['meeting_version_id'],kind='alignment').first()
        if not m or not 0<=(timezone.now()-m.occurred_at).total_seconds()<=rules['alignment_max_age_seconds']:raise ValidationError('Current actually held alignment meeting within configured age required')
        active(m.created_by);require(m.created_by,c,'meeting.record')
        links[purpose]=[item.pk,m.pk];meeting_ids.append((m.meeting_id,m.occurred_at))
    if meeting_ids[0][0]==meeting_ids[1][0] or meeting_ids[1][1]<meeting_ids[0][1]:raise ValidationError('Two distinct alignment sessions in their documented order required')
    pair,observations=requests(c,e,reader)
    return {'policy_id':p.pk,'alignment_links':links,'candidate_id':pair['candidate_id'],'observations':observations,'comparison_id':comparison_context(c,e,p,rules) if comparison_required else None,
        'source_hashes':{k:proof(c,payload[k]).sha256 for k in SOURCE_KINDS},'source_correlation':correlation,'native_verified':False}

def guard_prepare(a,c,packet_id):
    readable(a,c);require(a,c,'planning.prepare')
    e,_=packet(c,packet_id)
    requests(c,e,a)
    old=latest(c,'ready')
    if old:
        try:
            if current_readiness(c,old.pk)['packet_id']==e.pk:return e,None,old
        except (ValidationError,PermissionDenied):pass
    required=Baseline.objects.filter(case=c,signed__isnull=False).exists()
    value={'packet_id':e.pk,'packet_sha256':e.sha256,'comparison_required':required,'inputs':inputs(c,e,required,a)}
    return e,value,None

@transaction.atomic
def prepare(a,case_id,packet_id):
    c=locked(a,case_id,'prepare')
    _,value,old=guard_prepare(a,c,packet_id)
    return old or write(a,c,'ready',value)

def current_readiness(c,evidence_id):
    item=c.evidence.filter(pk=evidence_id,kind=KINDS['ready']).first();value=read(c,item,'ready','prepare')
    if set(value)!={'packet_id','packet_sha256','comparison_required','inputs'} or type(value['comparison_required']) is not bool:raise ValidationError('Closed readiness protocol required')
    e,_=packet(c,value['packet_id'])
    if value['packet_sha256']!=e.sha256 or value['inputs']!=inputs(c,e,value['comparison_required'],item.created_by):raise ValidationError('Current planning readiness source/criteria/authority changed')
    return value

@transaction.atomic
def bridge(a,case_id,readiness_id,dossier_id):
    c=locked(a,case_id,'prepare');v=current_readiness(c,readiness_id)
    e,_=packet(c,v['packet_id']);requests(c,e,a)
    from .delivery import dossier_for,capture_source
    dossier=dossier_for(c,dossier_id)
    if dossier.candidate_id!=v['inputs']['candidate_id']:raise ValidationError('Delivery dossier must use the exact approved planning subject candidate')
    old=dossier.sources.filter(kind='scope_baseline',evidence_id=readiness_id).first()
    return old or capture_source(a,c.pk,dossier_id,'scope_baseline','psl:planning-readiness:'+str(readiness_id),readiness_id,{},None)

def report(a,case_id):
    c=Case.objects.get(pk=case_id);readable(a,c);out={'process_ids':['P17','P21','P25','P26','P63'],'effect_tools':[],'native_verified':False}
    current=latest(c,'packet');out['current_packet_id']=current.pk if current else None
    try:
        e,v=packet(c);out.update(packet_id=e.pk,packet_sha256=e.sha256,payload=v['payload'])
        from .planning_sources import assessment,clarifications
        out['source_clarifications']=clarifications(c,e.pk)
        out['source_correlation']=assessment(c,v['payload'])
        if v['protocol']!='planning-packet/v2':
            out['source_correlation']['complete']=False
            out['source_correlation']['findings'].append({'key':'legacy_packet','code':'correlation_unknown','source_ids':[],
                'detail':'Legacy packet retains history only; explicit source bindings require a successor.'})
        if not out['source_correlation']['complete']:
            out.update(status='dependent_readiness_held',finding='; '.join(f['key']+': '+f['detail'] for f in out['source_correlation']['findings']))
            return out
        requests(c,e,a)
        old=latest(c,'ready');current=current_readiness(c,old.pk) if old else None
        out['readiness_inputs']=current['inputs'] if current else inputs(c,e,Baseline.objects.filter(case=c,signed__isnull=False).exists(),a);out['status']='source_referenced_ready'
        out['readiness_id']=old.pk if current else None
    except (ValidationError,PermissionDenied) as exc:
        out.update(status='dependent_readiness_held',finding='; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Some department sources are outside your current access.')
    return out
