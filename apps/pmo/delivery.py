"""Planning/delivery and release evidence. No deployment command exists here."""
import math
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,DatabaseError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from apps.core.evidence_access import public_evidence
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.policy.services import decision_authority
from apps.documents.controlled import baseline_manifest
from apps.documents.contracts import validate,digest
from .services import subject
from .commercial import note_required
from . import delivery_workarounds
from .clocks import aware
from .models import DeliveryDossier,DeliverySource,DeliverySourceVerification,DeliveryRecord,DeliveryCandidate,MeetingVersion
from apps.core.read_observation import observed_fact

SOURCE_OWNERS={'registration':'PMO','scope_baseline':'PMO','ui_applicability':'Product/Design','ui_target':'Product/Design','ui_design':'Design Lead',
    'ui_client':'Client','technical_design':'Engineering Lead','test_strategy':'QA Lead','uat_approach':'Product Owner',
    'hypercare_engineering':'Engineering','hypercare_infrastructure':'Infrastructure','technical_finalization':'Engineering'}
SOURCE_OWNERS.update(uat_client_target='PMO',uat_client_response='Client')
SOURCE_OWNERS[delivery_workarounds.KIND] = 'PMO'
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
def open_dossier(actor,case_id,candidate_id,evidence_id,note,expected,*,declined_reply_id=None):
    case=lock_case(actor,case_id,'delivery.manage',expected);decision_authority(actor,case,'PM');note_required(note)
    candidate=DeliveryCandidate.objects.filter(case=case,pk=candidate_id).first();base=baseline_manifest(case)
    if case.kind!='project' or not candidate or not base:raise ValidationError('Project candidate and prepared plan/cost/SOW baseline required; signature is not a planning prerequisite')
    if DeliveryDossier.objects.filter(candidate=candidate).exists():raise ValidationError('Candidate dossier already exists')
    origin=None
    if declined_reply_id is not None:
        from .models import GoLiveClientReply
        origin=GoLiveClientReply.objects.filter(pk=declined_reply_id,dossier__case=case,outcome='declined').exclude(dossier__candidate=candidate).first()
        if not origin:raise ValidationError('Select the source decline for this distinct candidate.')
        from .go_live_replies import rules,current_authority,head
        _,handling=rules(case)
        if handling['decline_handling']!='new_release_candidate' or head(origin).pk!=origin.pk:
            raise ValidationError('Review current decline handling before opening this candidate.')
        current_authority(origin,handling)
    d=DeliveryDossier.objects.create(case=case,candidate=candidate,baseline={k:v for k,v in base.items() if k!='signed_id'},
        evidence=subject(case,evidence_id),actor=actor,declined_reply=origin)
    event(actor,case,'delivery.opened',dossier=d.pk,note=note)
    if origin:
        event(actor,case,'delivery.client_decline_candidate',reply_id=origin.pk,candidate_id=candidate.pk,
              dossier_id=d.pk,deployment_authorized=False)
    bump(case)
    return d


def validate_source_payload(kind,payload):
    from adapters.client_uat import KINDS as CLIENT_KINDS,validate_payload as validate_client
    if kind in CLIENT_KINDS:
        validate_client(kind,payload);return
    from .delivery_ui import KINDS,validate_payload
    if kind in KINDS:
        validate_payload(kind,payload);return
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
    from adapters.client_uat import KINDS as CLIENT_KINDS
    if kind in CLIENT_KINDS:raise ValidationError('Use the human client-response workflow for these records')
    if kind == delivery_workarounds.KIND:raise ValidationError('Use the exact returned Planning workaround action')
    case=lock_case(actor,case_id,'delivery.source',expected);d=dossier_for(case,dossier_id);ensure_open(d)
    if kind not in SOURCE_OWNERS or not isinstance(external_ref,str) or not external_ref.strip() or len(external_ref)>240:
        raise ValidationError('Choose an owned source kind and bounded external reference')
    validate_source_payload(kind,payload)
    evidence=subject(case,evidence_id)
    from .delivery_ui import KINDS,validate_capture
    if kind in KINDS:validate_capture(d,kind,external_ref,evidence,payload)
    try:
        s=DeliverySource.objects.create(dossier=d,kind=kind,external_ref=external_ref,evidence=evidence,payload=payload,actor=actor)
    except DatabaseError as exc:
        # The persisted UI guard remains authoritative for parser/race edges.
        # Translate only its explicit rejection, never connectivity or other DB failures.
        if kind in KINDS and getattr(exc.__cause__,'sqlstate',None)=='P0001':
            raise ValidationError('UI source does not meet the stored artifact/owner receipt contract; check its exact fields and current authority') from exc
        raise
    event(actor,case,'delivery.source_captured',source=s.pk,owner=SOURCE_OWNERS[kind],verified=False);bump(case);return s


def source_result_schema(s):
    schema={'type':'object','properties':{'source_id':{'const':s.pk},'candidate_ref':{'const':s.dossier.candidate.reference},
        'external_ref':{'const':s.external_ref},'owner':{'const':SOURCE_OWNERS[s.kind]},'evidence_sha256':{'const':s.evidence.sha256},
        'payload_sha256':{'const':digest(s.payload)},'decision':{'enum':['accepted','rejected','unknown']},'source_receipt':{'type':'string','minLength':1}},
        'required':['source_id','candidate_ref','external_ref','owner','evidence_sha256','payload_sha256','decision','source_receipt'],'additionalProperties':False}
    from .delivery_ui import KINDS
    if s.kind in KINDS:
        schema['properties']['ui_binding']={'const':s.payload}
        schema['properties']['source_receipt']['maxLength']=240
        schema['required'].append('ui_binding')
    return schema


def verify_source(actor,case_id,source_id,expected,adapter=None):
    from apps.core.models import Case
    from adapters.delivery import SyntheticDeliverySourceAdapter
    case=Case.objects.get(pk=case_id);require(actor,case,'delivery.verify')
    s=DeliverySource.objects.select_related('dossier__candidate','evidence').filter(pk=source_id,dossier__case=case).first()
    if not s:raise ValidationError('Source is outside this case')
    from adapters.client_uat import KINDS as CLIENT_KINDS
    if s.kind in CLIENT_KINDS:raise ValidationError('Agent or synthetic source checks cannot confirm a human client response')
    if s.kind == delivery_workarounds.KIND:raise ValidationError('Use the current human-reviewed client workaround')
    if not case.synthetic:raise ValidationError('Operational source capture is available; authoritative verification needs an accepted remote adapter contract')
    adapter=adapter or SyntheticDeliverySourceAdapter();result=adapter.read(s)
    validate(source_result_schema(s),result)
    with transaction.atomic():
        case=lock_case(actor,case_id,'delivery.verify',expected);d=dossier_for(case,s.dossier_id);ensure_open(d)
        if d.sources.filter(kind=s.kind).order_by('-pk').first().pk!=s.pk:raise ValidationError('Source revision changed; verify the current record')
        from .delivery_ui import KINDS,validate_current,match_approval
        if s.kind in KINDS:
            validate_current(s)
            if s.kind!='ui_target' and result['decision']=='accepted':match_approval(d,s)
        v=DeliverySourceVerification.objects.create(source=s,adapter=adapter.name,result=result,actor=actor)
        event(actor,case,'delivery.source_verified',verification=v.pk,source=s.pk,decision=result['decision']);bump(case);return v


def verified_source(d,kind):
    s=d.sources.filter(kind=kind).order_by('-pk').first();v=s.verifications.order_by('-pk').first() if s else None
    if not v or v.result['decision']!='accepted':raise ValidationError('Current source-verified evidence required: '+kind)
    if kind=='scope_baseline' and s.evidence.kind=='planning_readiness':
        from .planning import current_readiness
        value=current_readiness(d.case,s.evidence_id)
        if value['inputs']['candidate_id']!=d.candidate_id:raise ValidationError('Planning source subject differs from delivery candidate')
    require(v.actor,d.case,'delivery.verify')
    from .delivery_ui import KINDS,validate_current
    if kind in KINDS:validate_current(s,v)
    return s,v


@observed_fact
def planning_inputs(d):
    pins={}
    for k in PLANNING:
        s,v=verified_source(d,k);pins[k]=[s.pk,v.pk]
    ui=DeliverySource.objects.get(pk=pins['ui_applicability'][0]).payload
    if ui['requires_ui'] is None or ui['client_signoff_required'] is None:raise ValidationError('UI and conditional client applicability remain unknown; obtain Product/Design evidence')
    result={'baseline':d.baseline,'requirements_id':d.candidate.requirements_id,'sources':pins}
    if ui['requires_ui']:
        from .delivery_ui import planning_binding
        result['ui_target']=planning_binding(d,pins,ui['client_signoff_required'])
    return result


@transaction.atomic
def decide_planning(actor,case_id,dossier_id,verdict,evidence_id,note,expected,*,issue_id=None):
    case=lock_case(actor,case_id,'delivery.planning_decide',expected);d=dossier_for(case,dossier_id);ensure_open(d);note_required(note)
    if verdict not in ['approve','return','reject']:raise ValidationError('Choose an explicit planning verdict')
    authority=decision_authority(actor,case,'PMO Lead',verdict)
    inputs = planning_inputs(d)
    prior = latest(d, 'planning_decision', False)
    remedy = planning_remedy(d, prior, inputs, actor=actor) if verdict == 'approve' or (
        prior and prior.data['verdict'] in ('return', 'reject')) else None
    data = {'verdict': verdict, 'authority': authority, 'note': note}
    returned = delivery_workarounds.origin(d, prior)
    if verdict != 'approve' and returned and (prior.data.get('issue_remedy') or delivery_workarounds.head(d, returned)):
        ongoing = planning_issue(d, returned.data['blocking_issue']['issue'])
        if ongoing.current.status not in ('Resolved', 'Closed'):
            if issue_id is not None and issue_id != ongoing.pk:
                raise ValidationError('Keep the original linked issue on a new return while it still needs work.')
            issue_id = ongoing.pk
    if issue_id is not None:
        if verdict not in ('return', 'reject'):
            raise ValidationError('Link a blocking issue when returning or rejecting delivery.')
        require(actor, case, 'issue.read')
        issue = planning_issue(d, issue_id)
        if issue.current.status in ('Resolved', 'Closed'):
            raise ValidationError('Choose an issue that still needs work.')
        data['blocking_issue'] = {'issue': issue.pk, 'state': issue.current_id}
    if remedy and verdict == 'approve':
        if remedy.get('kind') == delivery_workarounds.KIND:
            if remedy['recorder_id'] == actor.pk:
                raise PermissionDenied('A different assigned PMO Lead must approve the linked client workaround.')
            delivery_workarounds.approval_statement(actor, d, remedy)
        data['issue_remedy'] = remedy
        data['blocking_decision_id'] = returned.pk
    return record(actor,case,d,'planning_decision',subject(case,evidence_id),data,inputs,parent=prior)


def planning_issue(d, issue_id):
    from .issue_access import state_public
    from .models import Issue

    if type(issue_id) is not int or issue_id < 1:
        raise ValidationError('Choose a current issue from this project.')
    issue = Issue.objects.filter(case=d.case, pk=issue_id).select_related('case', 'current').first()
    if not issue or not issue.current or not state_public(issue.current):
        raise ValidationError('Choose a current issue from this project.')
    return issue


def planning_remedy(d, prior, inputs, *, actor=None):
    """An unchanged packet cannot replace a negative decision by replay."""
    returned = delivery_workarounds.origin(d, prior)
    if not prior or (not returned and prior.data.get('verdict') not in ('return', 'reject')):
        return None
    blocking = (returned or prior).data.get('blocking_issue')
    if blocking:
        if actor is not None:
            require(actor, d.case, 'issue.read')
        issue = planning_issue(d, blocking['issue'])
        current = issue.current
        if current.pk != blocking['state'] and current.status in ('Resolved', 'Closed') and current.fix_id:
            return {'issue': issue.pk, 'state': current.pk, 'fix': current.fix_id}
        if returned and returned.data.get('verdict') == 'return':
            workaround = delivery_workarounds.current(d, returned, issue)
            if workaround:
                return workaround
            raise ValidationError('Record the fix for the linked issue or link its reviewed client-approved workaround before requesting another decision.')
        raise ValidationError('Record the fix for the linked issue before requesting another decision.')
    previous = prior.snapshot
    old_sources = previous.get('sources', {})
    pairs = [(old_sources.get(kind, [None])[0], pin[0]) for kind, pin in inputs['sources'].items()]
    source_ids = {pk for pair in pairs for pk in pair if pk is not None}
    source_facts = {pk: (sha, payload) for pk, sha, payload in d.sources.filter(pk__in=source_ids)
                    .values_list('pk', 'evidence__sha256', 'payload')}
    if any(old in source_facts and new in source_facts and source_facts[old] != source_facts[new]
           for old, new in pairs):
        return None
    raise ValidationError('Record and verify corrected Planning evidence before requesting another decision.')


def approved_plan(d):
    r=latest(d,'planning_decision');require(r.actor,d.case,'delivery.planning_decide')
    if r.data['verdict']!='approve' or r.data['authority']!=decision_authority(r.actor,d.case,'PMO Lead') or r.snapshot!=planning_inputs(d):
        raise ValidationError('Current exact Planning exit approval required')
    remedy = r.data.get('issue_remedy')
    if remedy:
        require(r.actor, d.case, 'issue.read')
        returned = delivery_workarounds.origin(d, r)
        issue = planning_issue(d, remedy['issue'])
        if remedy.get('kind') == delivery_workarounds.KIND:
            if (r.actor_id == remedy['recorder_id'] or not returned or returned.data.get('verdict') != 'return' or
                    delivery_workarounds.current(d, returned, issue) != remedy):
                raise ValidationError('The client workaround used for Planning approval needs review.')
            delivery_workarounds.approval_statement(r.actor, d, remedy)
        elif issue.current.status not in ('Resolved', 'Closed') or issue.current.fix_id != remedy['fix']:
            raise ValidationError('The issue fix used for the Planning approval needs review.')
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
    from .go_live_replies import release_handoff
    handoff=release_handoff(d)
    from .signature_exemptions import assert_current_baseline_assurance
    assurance = assert_current_baseline_assurance(d.case)
    request=latest(d,'glpi_request');require(request.actor,d.case,'delivery.release_request');decision_authority(request.actor,d.case,'PM')
    source=upstream(d)
    if request.snapshot!=source:raise ValidationError('Deployment request prerequisites changed; reconcile the exact source request')
    result = {'upstream':source,'request_id':request.pk,'signed_id':baseline_manifest(d.case)['signed_id'],
        'glpi':verified_gates(d,GLPI_GATES,request.data['external_ref']), 'deployment_authorized':False,'financial_controls':'independent'}
    if handoff is not None:result['client_decline_handoff']=handoff
    if assurance['kind'] == 'internal_signature_exemption':
        result.update(signature_requirement='not_applicable', signature_exemption_id=assurance['id'])
    return result


@transaction.atomic
def prepare_readiness(actor,case_id,dossier_id,expected):
    case=lock_case(actor,case_id,'delivery.manage',expected);d=dossier_for(case,dossier_id);ensure_open(d)
    if latest(d,'release_outcome',False):raise ValidationError('Actual release already recorded; a later readiness check cannot authorize earlier work')
    inputs=readiness_inputs(d)
    return record(actor,case,d,'release_ready',latest(d,'glpi_request').evidence,{},inputs)


def release_environment(value):
    if value is None or value == '':
        return None
    if not isinstance(value, str) or not value.isprintable() or len(value) > 160:
        raise ValidationError('Enter a release environment in plain text, up to 160 characters.')
    return value.strip() or None


@transaction.atomic
def capture_release(actor,case_id,dossier_id,readiness_id,released_at,external_ref,evidence_id,note,expected,*,deployment_environment=None):
    case=lock_case(actor,case_id,'delivery.release_record',expected);d=dossier_for(case,dossier_id,current=False);note_required(note)
    instant=aware(released_at)
    if instant>timezone.now() or not external_ref.strip() or len(external_ref)>240:raise ValidationError('Actual past release instant and source reference required')
    parent=d.records.filter(pk=readiness_id,kind='release_ready').first() if readiness_id else None
    if readiness_id and not parent:raise ValidationError('Readiness must belong to this exact dossier')
    if latest(d,'release_outcome',False):raise ValidationError('Release outcome already recorded; preserve original event history')
    environment = release_environment(deployment_environment)
    data = {'released_at': instant.isoformat(), 'external_ref': external_ref, 'note': note}
    if environment is not None:
        data['deployment_environment'] = environment
    return record(actor,case,d,'release_outcome',subject(case,evidence_id),data,
        {'readiness_preceded':bool(parent and parent.created_at<=instant),'deployment_dispatched':False},parent)


def release_observations(case, dossier_ids):
    """Read only the named release facts whose exact proof is available in a delivery view."""
    proof = public_evidence(case.evidence.all()).values('pk')
    rows = DeliveryRecord.objects.filter(dossier__case=case, dossier_id__in=dossier_ids,
        kind='release_outcome', evidence_id__in=proof).values('dossier_id', 'dossier__candidate__reference',
        'evidence_id', 'evidence__version', 'data__released_at', 'data__external_ref', 'data__deployment_environment')
    return {row['dossier_id']: {
        'candidate': row['dossier__candidate__reference'],
        'released_at': parse_datetime(row['data__released_at']),
        'reference': row['data__external_ref'],
        'environment': row['data__deployment_environment'],
        'evidence_id': row['evidence_id'],
        'evidence_version': row['evidence__version'],
    } for row in rows}


@observed_fact
def valid_release(d):
    o=latest(d,'release_outcome');require(o.actor,d.case,'delivery.release_record')
    ready=o.parent
    if not ready or ready.created_at>aware(o.data['released_at']):raise ValidationError('Missing pre-release readiness remains an exception; it cannot be backdated')
    require(ready.actor,d.case,'delivery.manage')
    if ready.snapshot!=readiness_inputs(d):raise ValidationError('Release evidence/policy/authority changed; explicit correction required')
    return o
