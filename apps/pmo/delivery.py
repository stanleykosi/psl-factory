"""Planning/delivery and release evidence. No deployment command exists here."""
import math
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.policy.services import decision_authority
from apps.documents.controlled import baseline_manifest
from apps.documents.contracts import validate,digest
from .services import subject
from .commercial import note_required
from .clocks import aware
from .models import DeliveryDossier,DeliverySource,DeliverySourceVerification,DeliveryRecord,DeliveryCandidate,MeetingVersion
from apps.core.read_observation import observed_fact

SOURCE_OWNERS={'registration':'PMO','scope_baseline':'PMO','ui_applicability':'Product/Design','ui_design':'Design Lead',
    'ui_client':'Client','technical_design':'Engineering Lead','test_strategy':'QA Lead','uat_approach':'Product Owner',
    'hypercare_engineering':'Engineering','hypercare_infrastructure':'Infrastructure','technical_finalization':'Engineering'}
PLANNING=['registration','scope_baseline','technical_design','test_strategy','uat_approach','ui_applicability']
UPSTREAM_GATES=['qa_exit','uat_product_manager','uat_product_owner','uat_client','engineering_go']
GLPI_GATES=['glpi_security','glpi_cto','glpi_ceo']


def dossier_for(case,pk,current=True):
    d=DeliveryDossier.objects.select_related('case','candidate__requirements').filter(case=case,pk=pk).first()
    if not d:raise ValidationError('Select this case delivery dossier')
    if current and d.baseline!={k:v for k,v in baseline_manifest(case).items() if k!='signed_id'}:
        raise ValidationError('Delivery baseline changed; create a dossier for a new candidate and preserve history')
    return d


def ensure_open(d):
    if d.records.filter(kind='closure').exists():raise ValidationError('Project dossier is archived; preserve history and use a new candidate for new delivery')


def latest(d,kind,required=True):
    r=d.records.filter(kind=kind).order_by('-pk').first()
    if required and not r:raise ValidationError('Missing delivery record: '+kind)
    return r


def record(actor,case,d,kind,evidence,data,snapshot,parent=None):
    r=DeliveryRecord.objects.create(dossier=d,kind=kind,parent=parent,evidence=evidence,data=data,snapshot=snapshot,actor=actor)
    event(actor,case,'delivery.'+kind,record=r.pk,dossier=d.pk);bump(case);return r


@transaction.atomic
def open_dossier(actor,case_id,candidate_id,evidence_id,note,expected):
    case=lock_case(actor,case_id,'delivery.manage',expected);decision_authority(actor,case,'PM');note_required(note)
    candidate=DeliveryCandidate.objects.filter(case=case,pk=candidate_id).first();base=baseline_manifest(case)
    if case.kind!='project' or not candidate or not base:raise ValidationError('Project candidate and prepared plan/cost/SOW baseline required; signature is not a planning prerequisite')
    if DeliveryDossier.objects.filter(candidate=candidate).exists():raise ValidationError('Candidate dossier already exists')
    d=DeliveryDossier.objects.create(case=case,candidate=candidate,baseline={k:v for k,v in base.items() if k!='signed_id'},
        evidence=subject(case,evidence_id),actor=actor)
    event(actor,case,'delivery.opened',dossier=d.pk,note=note);bump(case);return d


def validate_source_payload(kind,payload):
    if kind=='ui_applicability':
        schema={'type':'object','properties':{k:{'type':['boolean','null']} for k in ['requires_ui','client_signoff_required']},
            'required':['requires_ui','client_signoff_required'],'additionalProperties':False}
    elif kind.startswith('hypercare_'):
        schema={'type':'object','properties':{'observed_at':{'type':'string'},'confirmed':{'type':['boolean','null']},
            'metrics':{'type':'object','maxProperties':20,'propertyNames':{'pattern':'^[a-z][a-z0-9_]{0,39}$'},
                'additionalProperties':{'type':'object','properties':{'value':{'type':['number','null']},'unit':{'type':'string','minLength':1,'maxLength':40}},
                    'required':['value','unit'],'additionalProperties':False}}},'required':['observed_at','confirmed','metrics'],'additionalProperties':False}
    else:schema={'type':'object','maxProperties':0}
    validate(schema,payload)
    if kind.startswith('hypercare_'):
        instant=aware(payload['observed_at'])
        if instant>timezone.now():raise ValidationError('Hypercare observation must be an actual past instant')
        if any(m['value'] is not None and not math.isfinite(m['value']) for m in payload['metrics'].values()):raise ValidationError('Observed metrics must be finite or explicitly unknown')


@transaction.atomic
def capture_source(actor,case_id,dossier_id,kind,external_ref,evidence_id,payload,expected):
    case=lock_case(actor,case_id,'delivery.source',expected);d=dossier_for(case,dossier_id);ensure_open(d)
    if kind not in SOURCE_OWNERS or not isinstance(external_ref,str) or not external_ref.strip() or len(external_ref)>240:
        raise ValidationError('Choose an owned source kind and bounded external reference')
    validate_source_payload(kind,payload)
    s=DeliverySource.objects.create(dossier=d,kind=kind,external_ref=external_ref,evidence=subject(case,evidence_id),payload=payload,actor=actor)
    event(actor,case,'delivery.source_captured',source=s.pk,owner=SOURCE_OWNERS[kind],verified=False);bump(case);return s


def verify_source(actor,case_id,source_id,expected,adapter=None):
    from apps.core.models import Case
    from adapters.delivery import SyntheticDeliverySourceAdapter
    case=Case.objects.get(pk=case_id);require(actor,case,'delivery.verify')
    s=DeliverySource.objects.select_related('dossier__candidate','evidence').filter(pk=source_id,dossier__case=case).first()
    if not s:raise ValidationError('Source is outside this case')
    if not case.synthetic:raise ValidationError('Operational source capture is available; authoritative verification needs an accepted remote adapter contract')
    adapter=adapter or SyntheticDeliverySourceAdapter();result=adapter.read(s)
    validate({'type':'object','properties':{'source_id':{'const':s.pk},'candidate_ref':{'const':s.dossier.candidate.reference},
        'external_ref':{'const':s.external_ref},'owner':{'const':SOURCE_OWNERS[s.kind]},'evidence_sha256':{'const':s.evidence.sha256},
        'payload_sha256':{'const':digest(s.payload)},'decision':{'enum':['accepted','rejected','unknown']},'source_receipt':{'type':'string','minLength':1}},
        'required':['source_id','candidate_ref','external_ref','owner','evidence_sha256','payload_sha256','decision','source_receipt'],'additionalProperties':False},result)
    with transaction.atomic():
        case=lock_case(actor,case_id,'delivery.verify',expected);d=dossier_for(case,s.dossier_id);ensure_open(d)
        if d.sources.filter(kind=s.kind).order_by('-pk').first().pk!=s.pk:raise ValidationError('Source revision changed; verify the current record')
        v=DeliverySourceVerification.objects.create(source=s,adapter=adapter.name,result=result,actor=actor)
        event(actor,case,'delivery.source_verified',verification=v.pk,source=s.pk,decision=result['decision']);bump(case);return v


def verified_source(d,kind):
    s=d.sources.filter(kind=kind).order_by('-pk').first();v=s.verifications.order_by('-pk').first() if s else None
    if not v or v.result['decision']!='accepted':raise ValidationError('Current source-verified evidence required: '+kind)
    if kind=='scope_baseline' and s.evidence.kind=='planning_readiness':
        from .planning import current_readiness
        value=current_readiness(d.case,s.evidence_id)
        if value['inputs']['candidate_id']!=d.candidate_id:raise ValidationError('Planning source subject differs from delivery candidate')
    require(v.actor,d.case,'delivery.verify');return s,v


@observed_fact
def planning_inputs(d):
    pins={}
    for k in PLANNING:
        s,v=verified_source(d,k);pins[k]=[s.pk,v.pk]
    ui=DeliverySource.objects.get(pk=pins['ui_applicability'][0]).payload
    if ui['requires_ui'] is None or ui['client_signoff_required'] is None:raise ValidationError('UI and conditional client applicability remain unknown; obtain Product/Design evidence')
    for k in (['ui_design'] if ui['requires_ui'] else [])+(['ui_client'] if ui['requires_ui'] and ui['client_signoff_required'] else []):
        s,v=verified_source(d,k);pins[k]=[s.pk,v.pk]
    return {'baseline':d.baseline,'requirements_id':d.candidate.requirements_id,'sources':pins}


@transaction.atomic
def decide_planning(actor,case_id,dossier_id,verdict,evidence_id,note,expected):
    case=lock_case(actor,case_id,'delivery.planning_decide',expected);d=dossier_for(case,dossier_id);ensure_open(d);note_required(note)
    if verdict not in ['approve','return','reject']:raise ValidationError('Choose an explicit planning verdict')
    authority=decision_authority(actor,case,'PMO Lead',verdict)
    return record(actor,case,d,'planning_decision',subject(case,evidence_id),{'verdict':verdict,'authority':authority,'note':note},planning_inputs(d))


def approved_plan(d):
    r=latest(d,'planning_decision');require(r.actor,d.case,'delivery.planning_decide')
    if r.data['verdict']!='approve' or r.data['authority']!=decision_authority(r.actor,d.case,'PMO Lead') or r.snapshot!=planning_inputs(d):
        raise ValidationError('Current exact Planning exit approval required')
    return r


@transaction.atomic
def record_progress(actor,case_id,dossier_id,kind,evidence_id,note,expected,meeting_id=None):
    case=lock_case(actor,case_id,'delivery.manage',expected);d=dossier_for(case,dossier_id);ensure_open(d);decision_authority(actor,case,'PM');note_required(note)
    if kind not in ['kickoff','progress']:raise ValidationError('Choose kickoff or progress evidence')
    plan=approved_plan(d);meeting=None
    if kind=='kickoff':
        meeting=MeetingVersion.objects.filter(pk=meeting_id,meeting__case=case,kind='kickoff').first()
        if not meeting or meeting.meeting.current_id!=meeting.pk or meeting.occurred_at<plan.created_at or meeting.occurred_at>timezone.now():
            raise ValidationError('Link the current actual kickoff meeting after Planning approval')
    return record(actor,case,d,kind,subject(case,evidence_id),{'note':note,'meeting_id':meeting.pk if meeting else None},{'planning_id':plan.pk})


def upstream(d):
    plan=approved_plan(d);kickoff=latest(d,'kickoff');require(kickoff.actor,d.case,'delivery.manage')
    if kickoff.snapshot!={'planning_id':plan.pk}:raise ValidationError('Kickoff binds an older Planning exit')
    meeting=MeetingVersion.objects.get(pk=kickoff.data['meeting_id'])
    if meeting.meeting.current_id!=meeting.pk:raise ValidationError('Kickoff meeting was revised')
    return {'planning_id':plan.pk,'kickoff_id':kickoff.pk,'gates':verified_gates(d,UPSTREAM_GATES)}


def verified_gates(d,kinds,external_ref=None):
    pins=[]
    for kind in kinds:
        g=d.candidate.gates.filter(kind=kind).order_by('-pk').first();v=g.verifications.order_by('-pk').first() if g else None
        if not v or v.result['decision']!='accepted' or (kind=='qa_exit' and v.result['critical_defects']!=0):
            raise ValidationError('Current accepted candidate gate required: '+kind)
        from .approvals import gate_current
        gate_current(d.candidate,kind,v)
        if external_ref and g.external_ref!=external_ref:raise ValidationError('GLPI evidence must identify this exact deployment request')
        require(v.actor,d.case,'pmo.gate_verify');pins.append([g.pk,v.pk])
    return pins


@transaction.atomic
def record_release_request(actor,case_id,dossier_id,external_ref,evidence_id,note,expected):
    case=lock_case(actor,case_id,'delivery.release_request',expected);d=dossier_for(case,dossier_id);ensure_open(d);decision_authority(actor,case,'PM');note_required(note)
    if not external_ref.strip() or len(external_ref)>240:raise ValidationError('Actual GLPI request reference required')
    return record(actor,case,d,'glpi_request',subject(case,evidence_id),{'external_ref':external_ref,'note':note},upstream(d))


@observed_fact
def readiness_inputs(d):
    if not baseline_manifest(d.case).get('signed_id'):raise ValidationError('Signed baseline required before release evidence readiness')
    request=latest(d,'glpi_request');require(request.actor,d.case,'delivery.release_request');decision_authority(request.actor,d.case,'PM')
    source=upstream(d)
    if request.snapshot!=source:raise ValidationError('Deployment request prerequisites changed; reconcile the exact source request')
    return {'upstream':source,'request_id':request.pk,'signed_id':baseline_manifest(d.case)['signed_id'],
        'glpi':verified_gates(d,GLPI_GATES,request.data['external_ref']), 'deployment_authorized':False,'financial_controls':'independent'}


@transaction.atomic
def prepare_readiness(actor,case_id,dossier_id,expected):
    case=lock_case(actor,case_id,'delivery.manage',expected);d=dossier_for(case,dossier_id);ensure_open(d)
    if latest(d,'release_outcome',False):raise ValidationError('Actual release already recorded; a later readiness check cannot authorize earlier work')
    inputs=readiness_inputs(d)
    return record(actor,case,d,'release_ready',latest(d,'glpi_request').evidence,{},inputs)


@transaction.atomic
def capture_release(actor,case_id,dossier_id,readiness_id,released_at,external_ref,evidence_id,note,expected):
    case=lock_case(actor,case_id,'delivery.release_record',expected);d=dossier_for(case,dossier_id,current=False);note_required(note)
    instant=aware(released_at)
    if instant>timezone.now() or not external_ref.strip() or len(external_ref)>240:raise ValidationError('Actual past release instant and source reference required')
    parent=d.records.filter(pk=readiness_id,kind='release_ready').first() if readiness_id else None
    if readiness_id and not parent:raise ValidationError('Readiness must belong to this exact dossier')
    if latest(d,'release_outcome',False):raise ValidationError('Release outcome already recorded; preserve original event history')
    return record(actor,case,d,'release_outcome',subject(case,evidence_id),{'released_at':instant.isoformat(),'external_ref':external_ref,'note':note},
        {'readiness_preceded':bool(parent and parent.created_at<=instant),'deployment_dispatched':False},parent)


@observed_fact
def valid_release(d):
    o=latest(d,'release_outcome');require(o.actor,d.case,'delivery.release_record')
    ready=o.parent
    if not ready or ready.created_at>aware(o.data['released_at']):raise ValidationError('Missing pre-release readiness remains an exception; it cannot be backdated')
    require(ready.actor,d.case,'delivery.manage')
    if ready.snapshot!=readiness_inputs(d):raise ValidationError('Release evidence/policy/authority changed; explicit correction required')
    return o
