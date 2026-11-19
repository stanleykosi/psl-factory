"""Ordinary client responses: a human witness, useful evidence checks and exact gates.

The recorded decision belongs to the external client. Neither the witness,
proof reviewer nor an agent becomes that client or authorises deployment.
"""
import json
from pathlib import PurePath

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.utils import timezone

from adapters import client_uat as contract,case_uploads,upload_text
from apps.agents.models import CaseUpload,AgentJob
from apps.core.client_contacts import authorize as contact_access
from apps.core.evidence_access import public_evidence
from apps.core.models import ClientContactRevision
from apps.core.read_budget import ReadBudget,ReadLimit
from apps.core.services import lock_case,add_evidence,event,bump
from apps.documents.contracts import digest,validate
from apps.identity.services import require
from apps.policy.client_uat_validators import COMPONENT
from apps.policy.services import active_component,reference_values,decision_authority
from .clocks import aware
from . import delivery
from .models import DeliverySource,DeliverySourceVerification,ClientUATGateBinding,GateRecord,GateVerification


def readable(actor,case):
    if not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():raise PermissionDenied('Current active reader required')
    for action in ['case.read','delivery.read','engagement.read']:require(actor,case,action)


def witness(actor,case):
    readable(actor,case);require(actor,case,'client_uat.record')
    return decision_authority(actor,case,'PM')


def rules(case):
    cfg=active_component(COMPONENT,case)
    return cfg,reference_values(cfg)[0]


def reviewer(actor,case):
    readable(actor,case)
    for action in ['client_uat.review','client_uat.proof.read']:require(actor,case,action)
    cfg,value=rules(case)
    if actor.pk not in value['reviewer_ids'] or value['reviewer_role'] is None:
        raise PermissionDenied('A current nominated proof reviewer is required')
    return cfg,value,decision_authority(actor,case,value['reviewer_role'])


def head(dossier,kind,target_id=None):
    query=dossier.sources.filter(kind=kind)
    if target_id is not None:query=query.filter(payload__target_id=target_id)
    return query.order_by('-pk').first()


def exact(case,pk,kind):
    row=DeliverySource.objects.select_related('dossier__case','dossier__candidate__requirements','evidence','actor').filter(
        pk=pk,dossier__case=case,kind=kind).first()
    if row is None:raise ValidationError('Choose an exact client-response record in this workspace')
    contract.validate_payload(kind,row.payload)
    return row


def contact(actor,case,pk):
    contact_access(actor,case,'project')
    row=ClientContactRevision.objects.select_related('evidence','actor').defer('name','client_name','email','role','evidence__body').filter(
        pk=pk,case=case,purpose='project',customer='').first()
    if row is None:raise ValidationError('Choose the current recorded project contact')
    if not get_user_model().objects.filter(pk=row.actor_id,is_active=True).exists():raise PermissionDenied('Original contact source owner is unavailable')
    require(row.actor,case,'engagement.capture')
    if ClientContactRevision.objects.filter(case=case,purpose='project',customer='',number__gt=row.number).exists():
        raise ValidationError('The project contact changed; review the current contact')
    if not public_evidence(case.evidence.filter(pk=row.evidence_id,kind__in=['engagement_source','policy_decision'])).exists():raise PermissionDenied('Original contact evidence is unavailable')
    return row


def contact_pin(row):
    return {'id':row.pk,'number':row.number,'evidence_id':row.evidence_id,'evidence_sha256':row.evidence.sha256}


def candidate_pin(dossier):
    row=dossier.candidate
    return {'id':row.pk,'reference':row.reference,'requirements_id':row.requirements_id,'requirements_sha256':row.requirements.sha256}


def current_target(actor,target):
    readable(actor,target.dossier.case)
    contract.validate_payload(contract.TARGET,target.payload)
    d=delivery.dossier_for(target.dossier.case,target.dossier_id)
    if head(d,contract.TARGET).pk!=target.pk:raise ValidationError('A newer client test request exists')
    if witness(target.actor,d.case)!=target.payload['recording_authority']:
        raise ValidationError('The original test-request witness authority changed')
    person=contact(actor,d.case,target.payload['contact']['id'])
    if (target.payload['candidate'],target.payload['contact'],target.payload['baseline'])!=(candidate_pin(d),contact_pin(person),d.baseline):
        raise ValidationError('The test version, contact or baseline changed')
    return d,person


def current_response(actor,response):
    readable(actor,response.dossier.case)
    contract.validate_payload(contract.RESPONSE,response.payload)
    target=exact(response.dossier.case,response.payload['target_id'],contract.TARGET)
    d,person=current_target(actor,target)
    if head(d,contract.RESPONSE,target.pk).pk!=response.pk or digest(target.payload)!=response.payload['target_sha256']:
        raise ValidationError('The client response or its exact test request changed')
    if witness(response.actor,d.case)!=response.payload['recording_authority']:
        raise ValidationError('The original response witness authority changed')
    return target,person


def _expect(actual,expected):
    if (actual.pk if actual else None)!=expected:raise ValidationError('This source changed. Review its current version.')


def _old(actor,dossier,kind,key,command_hash):
    old=DeliverySource.objects.filter(kind__in=contract.KINDS,payload__operation_key=key).first()
    if old and (old.dossier_id,old.kind,old.actor_id,old.payload['command_sha256'])!=(dossier.pk,kind,actor.pk,command_hash):
        raise ValidationError('This source key has already been used for a different record')
    return old


def _wake(case):
    from apps.workflows.models import FactoryWork
    from apps.workflows.factory_progress import wake_waiting
    ids=list(FactoryWork.objects.filter(case=case,definition__in=['delivery-release/v1','planning/v1']).order_by('pk').values_list('pk',flat=True)[:100])
    transaction.on_commit(lambda:[wake_waiting(pk) for pk in ids])


def _append(actor,case,dossier,kind,payload):
    contract.validate_payload(kind,payload)
    metadata=json.dumps({'kind':kind,'dossier':dossier.pk,'payload_sha256':digest(payload)},sort_keys=True)
    proof=add_evidence(actor,case.pk,'client_uat_metadata',metadata,'psl:client-uat:'+payload['operation_key'])
    case.refresh_from_db(fields=['revision'])
    row=DeliverySource.objects.create(dossier=dossier,kind=kind,external_ref='psl:client-uat:'+payload['operation_key'],
        payload=payload,evidence=proof,actor=actor)
    event(actor,case,'client_uat.recorded',source=row.pk,kind=kind,version=payload['number'],
          client_approval_granted=False,go_live_accepted=False,payment_authorized=False)
    bump(case);_wake(case);return row


@transaction.atomic
def record_target(actor,case_id,dossier_id,contact_id,sent_at,previous_id,expected_gate_id,replace_existing,operation_key,expected):
    case=lock_case(actor,case_id,'client_uat.record',expected);authority=witness(actor,case)
    d=delivery.dossier_for(case,dossier_id);delivery.ensure_open(d)
    if isinstance(sent_at,str) and len(sent_at)>64:raise ValidationError('Use a valid actual sent time')
    instant=aware(sent_at)
    if instant>timezone.now():raise ValidationError('Record the actual past time the version was sent')
    validate(contract.OP,str(operation_key))
    command={'dossier':d.pk,'contact':contact_id,'sent_at':instant.isoformat(),'previous':previous_id,
             'gate':expected_gate_id,'replace':replace_existing}
    validate(contract.TARGET_COMMAND,command);command_hash=digest(command)
    old=_old(actor,d,contract.TARGET,str(operation_key),command_hash)
    if old:return old
    previous=head(d,contract.TARGET);_expect(previous,previous_id)
    gate=d.candidate.gates.filter(kind='uat_client').order_by('-pk').first();_expect(gate,expected_gate_id)
    if gate and replace_existing is not True:raise ValidationError('Explicitly review replacing the earlier client-check context')
    person=contact(actor,case,contact_id)
    payload={'format':'psl.client-uat-target/v1','number':previous.payload['number']+1 if previous else 1,
        'predecessor_id':previous_id,'operation_key':str(operation_key),'command_sha256':command_hash,
        'candidate':candidate_pin(d),'contact':contact_pin(person),'sent_at':instant.isoformat(),
        'baseline':d.baseline,'replaces_gate_id':expected_gate_id,'recording_authority':authority}
    return _append(actor,case,d,contract.TARGET,payload)


def _proofs(actor,case,ids):
    if not isinstance(ids,list) or not 1<=len(ids)<=4 or len(set(ids))!=len(ids):raise ValidationError('Choose up to four distinct proof files')
    rows=list(CaseUpload.objects.filter(pk__in=ids,case=case,actor=actor).order_by('pk'))
    if len(rows)!=len(ids):raise PermissionDenied('Use your own proof uploads in this workspace')
    return [{'id':row.pk,'sha256':row.sha256,'size':row.size,'actor_id':row.actor_id} for row in rows]


@transaction.atomic
def record_response(actor,case_id,target_id,responded_at,outcome,genuine,note,workaround,source_reference,proof_ids,previous_id,operation_key,expected):
    case=lock_case(actor,case_id,'client_uat.record',expected);authority=witness(actor,case)
    target=exact(case,target_id,contract.TARGET);d,person=current_target(actor,target);delivery.ensure_open(d)
    if isinstance(responded_at,str) and len(responded_at)>64:raise ValidationError('Use a valid actual response time')
    instant=aware(responded_at)
    if not aware(target.payload['sent_at'])<=instant<=timezone.now():raise ValidationError('Response time must follow the actual test request and must not be in the future')
    validate(contract.OP,str(operation_key))
    command={'target':target.pk,'responded_at':instant.isoformat(),'outcome':outcome,'genuine':genuine,
        'note':note,'workaround':workaround,'source_reference':source_reference,'proof_ids':proof_ids,'previous':previous_id}
    validate(contract.RESPONSE_COMMAND,command);command['proof_ids']=sorted(proof_ids);command_hash=digest(command)
    old=_old(actor,d,contract.RESPONSE,str(operation_key),command_hash)
    if old:return old
    previous=head(d,contract.RESPONSE,target.pk);_expect(previous,previous_id)
    payload={'format':'psl.client-uat-response/v1','number':previous.payload['number']+1 if previous else 1,
        'predecessor_id':previous_id,'operation_key':str(operation_key),'command_sha256':command_hash,
        'target_id':target.pk,'target_sha256':digest(target.payload),'responded_at':instant.isoformat(),
        'outcome':outcome,'genuine':genuine,'note':note,'workaround':workaround,'source_reference':source_reference,
        'proofs':_proofs(actor,case,proof_ids),'recording_authority':authority}
    response=_append(actor,case,d,contract.RESPONSE,payload)
    try:
        _,value=rules(case)
        if value['agent_review_required'] is True:queue_checks(actor,response)
    except (ValidationError,PermissionDenied):
        event(actor,case,'client_uat.agent_wait',source=response.pk,reason='current_agent_scope_or_model_needed')
    return response


def queue_checks(actor,response):
    from apps.agents.upload_views import queue_draft
    current_response(actor,response)
    if actor.pk!=response.actor_id:raise PermissionDenied('Only the witness may send their own proof files for analysis')
    jobs=[]
    for pin in response.payload['proofs']:
        upload=CaseUpload.objects.get(pk=pin['id'],case=response.dossier.case,actor=actor,sha256=pin['sha256'])
        jobs.append(queue_draft(actor,upload,'A07'))
    return jobs


def private_reader(actor,response):
    current_response(actor,response);require(actor,response.dossier.case,'client_uat.proof.read')
    if actor.pk!=response.actor_id:reviewer(actor,response.dossier.case)


def proof_rows(actor,response):
    private_reader(actor,response);result=[]
    for pin in response.payload['proofs']:
        row=CaseUpload.objects.filter(pk=pin['id'],case=response.dossier.case,actor_id=pin['actor_id'],
                                     sha256=pin['sha256'],size=pin['size']).first()
        if row is None:raise ValidationError('An exact original proof file is unavailable')
        result.append(row)
    return result


def _common(source,receipt):
    return {'source_id':source.pk,'candidate_ref':source.dossier.candidate.reference,'external_ref':source.external_ref,
        'owner':'Client','evidence_sha256':source.evidence.sha256,'payload_sha256':digest(source.payload),
        'decision':'unknown','source_receipt':receipt,'purpose':'ordinary_client_uat',
        'external_authenticity_verified':False,'go_live_accepted':False,'payment_authorized':False}


def _job_pins(uploads):
    budget=ReadBudget();result=[]
    for upload in uploads:
        job=AgentJob.objects.defer('result').filter(upload=upload,actor_id=upload.actor_id,role='A07').first()
        item={'upload_id':upload.pk,'job_id':job.pk if job else None,'status':job.status if job else 'not_queued',
              'result_sha256':None,'source_sha256':None}
        if job and job.status in ['draft','reviewed']:
            from apps.agents.upload_jobs import authorize
            try:authorize(job.actor,upload)
            except PermissionDenied:
                item['status']='unavailable';result.append(item);continue
            try:value=budget.load(job,'result',ceiling=128*1024)
            except ReadLimit:
                item['status']='unavailable';result.append(item);continue
            if isinstance(value,dict):item.update(result_sha256=digest(value),source_sha256=value.get('source_sha256'))
            else:item['status']='held'
        result.append(item)
    return result


def agent_drafts(actor,response):
    """Private, current, bounded advice only; never a client decision."""
    uploads=proof_rows(actor,response);pins=_job_pins(uploads);result=[];budget=ReadBudget()
    for pin in pins:
        if pin['status'] not in ['draft','reviewed'] or pin['source_sha256'] is None:continue
        job=AgentJob.objects.defer('result').get(pk=pin['job_id'])
        try:value=budget.load(job,'result',ceiling=128*1024)
        except ReadLimit:continue
        upload=next(row for row in uploads if row.pk==pin['upload_id'])
        if not isinstance(value,dict) or value.get('source_sha256')!=upload.sha256 or digest(value)!=pin['result_sha256']:continue
        if (not isinstance(value.get('summary'),str) or not 0<len(value['summary'])<=4000
                or any(not isinstance(value.get(k),list) or len(value[k])>12 or any(not isinstance(v,str) or not 0<len(v)<=1000 for v in value[k]) for k in ['quotes','gaps'])):continue
        result.append({'summary':value['summary'],'quotes':value['quotes'],'gaps':value['gaps']})
    return result


@transaction.atomic
def inspect_proof(actor,case_id,response_id,expected):
    case=lock_case(actor,case_id,'client_uat.inspect',expected)
    readable(actor,case)
    response=exact(case,response_id,contract.RESPONSE);target,person=current_response(actor,response)
    uploads=proof_rows(actor,response)
    found_build=False;found_contact=False;codes=[]
    for upload in uploads:
        try:text=upload_text.extract(upload.name,case_uploads.read(upload))
        except (OSError,ValidationError,ValueError):codes.append('file_text_unavailable');continue
        found_build|=contract.mentions(text,target.payload['candidate']['reference'],identifier=True)
        found_contact|=contract.mentions(text,person.name)
    if not found_build:codes.append('version_not_found_in_text')
    if not found_contact:codes.append('contact_not_found_in_text')
    checks={'target_id':target.pk,'target_sha256':digest(target.payload),'proofs':response.payload['proofs'],
        'version_mentioned':found_build,'contact_mentioned':found_contact,'codes':sorted(set(codes)),
        'agent_jobs':_job_pins(uploads),'private_text_retained':False}
    receipt='psl:uat-check:'+digest(checks)
    old=response.verifications.filter(adapter=contract.INSPECTION,result__source_receipt=receipt).first()
    if old:return old
    row=DeliverySourceVerification.objects.create(source=response,adapter=contract.INSPECTION,
        result={**_common(response,receipt),'record_type':'inspection','checks':checks},actor=actor)
    event(actor,case,'client_uat.proof_checked',source=response.pk,check=row.pk,private_text_retained=False,
          external_authenticity_verified=False,client_approval_granted=False)
    bump(case);_wake(case);return row


def _inspection_current(actor,response):
    target,person=current_response(actor,response);uploads=proof_rows(actor,response)
    row=response.verifications.filter(adapter=contract.INSPECTION).order_by('-pk').first()
    if row is None:raise ValidationError('Check the current proof files first')
    value=row.result
    if any(value.get(key)!=expected for key,expected in _common(response,value.get('source_receipt')).items()):
        raise ValidationError('The evidence check no longer identifies this response')
    checks=value.get('checks',{})
    if checks.get('target_id')!=target.pk or checks.get('target_sha256')!=digest(target.payload) or checks.get('proofs')!=response.payload['proofs']:
        raise ValidationError('The evidence check belongs to an older source context')
    if checks.get('agent_jobs')!=_job_pins(uploads):raise ValidationError('The agent check changed. Check these files again.')
    private_reader(row.actor,response);require(row.actor,response.dossier.case,'client_uat.inspect')
    return row,uploads


def _qualifying_rules(value,response,uploads,checks):
    if value['qualification_mode']!='reviewed_human_attestation_v1' or any(
            value[key] is None for key in ['independent_review','agent_review_required','exact_mentions_required']) or not value['proof_formats']:
        raise ValidationError('Complete the client-response proof rules before confirming the evidence')
    if any(PurePath(upload.name).suffix.lower().lstrip('.') not in value['proof_formats'] for upload in uploads):
        raise ValidationError('The proof file format is not covered by the current rules')
    if response.payload['outcome']=='approved_with_workaround' and value['workaround_mode']!='explicit_client_approved_scope_v1':
        raise ValidationError('The workaround evidence rules still need an owner decision')
    if value['exact_mentions_required'] and (not checks.get('version_mentioned') or not checks.get('contact_mentioned')):
        raise ValidationError('Resolve the version or contact mismatch before confirming this proof')
    if value['agent_review_required'] and any(row['status'] not in ['draft','reviewed'] or
            row['source_sha256']!=pin['sha256'] for row,pin in zip(checks['agent_jobs'],response.payload['proofs'])):
        raise ValidationError('A current source-linked evidence check is still needed for every file')


@transaction.atomic
def review_proof(actor,case_id,response_id,inspection_id,verdict,proof_confirmed,note,operation_key,expected):
    case=lock_case(actor,case_id,'client_uat.review',expected)
    readable(actor,case)
    response=exact(case,response_id,contract.RESPONSE);target,_=current_response(actor,response)
    cfg,value,authority=reviewer(actor,case)
    if verdict not in ['confirm','return','withdraw'] or not isinstance(note,str) or not 1<=len(note.strip())<=2000:
        raise ValidationError('Choose an evidence decision and record its reason')
    validate(contract.OP,str(operation_key))
    if value['independent_review'] is None:raise ValidationError('Set the evidence-review independence rule first')
    if value['independent_review'] and actor.pk in {response.actor_id,target.actor_id,*[pin['actor_id'] for pin in response.payload['proofs']]}:
        raise PermissionDenied('The configured independent proof reviewer must be a different person')
    inspection,uploads=_inspection_current(actor,response)
    if inspection.pk!=inspection_id:raise ValidationError('Review the latest evidence-check result')
    if verdict=='confirm':
        if proof_confirmed is not True:raise ValidationError('A person must confirm the exact client, version and response proof')
        _qualifying_rules(value,response,uploads,inspection.result['checks'])
    elif proof_confirmed is not False:raise ValidationError('Do not confirm proof when returning or withdrawing it')
    decision='unknown'
    if verdict=='confirm':decision='accepted' if response.payload['outcome'] in ['approved','approved_with_workaround'] else 'rejected' if response.payload['outcome']=='rejected' else 'unknown'
    result={**_common(response,'psl:uat-review:'+str(operation_key)),'record_type':'human_review','decision':decision,
        'verdict':verdict,'proof_confirmed':proof_confirmed,'note':note,'inspection_id':inspection.pk,
        'inspection_sha256':digest(inspection.result),'policy_id':cfg.pk,'reviewer_role':value['reviewer_role'],
        'authority':authority,'operation_key':str(operation_key)}
    old=response.verifications.filter(adapter=contract.REVIEW,result__operation_key=str(operation_key)).first()
    if old:
        if old.actor_id!=actor.pk or old.result!=result:raise ValidationError('This evidence-decision key was already used')
        return old
    row=DeliverySourceVerification.objects.create(source=response,adapter=contract.REVIEW,result=result,actor=actor)
    event(actor,case,'client_uat.proof_reviewed',source=response.pk,review=row.pk,verdict=verdict,
          external_authenticity_verified=False,go_live_accepted=False,payment_authorized=False)
    bump(case);_wake(case);return row


@transaction.atomic
def withdraw_recording(actor,case_id,response_id,reason,operation_key,expected):
    case=lock_case(actor,case_id,'client_uat.record',expected);authority=witness(actor,case)
    response=exact(case,response_id,contract.RESPONSE)
    if response.actor_id!=actor.pk:raise PermissionDenied('Only the original witness may retract their own recording')
    if not isinstance(reason,str) or not 1<=len(reason.strip())<=2000:raise ValidationError('Record the reason for retracting this recording')
    validate(contract.OP,str(operation_key))
    result={**_common(response,'psl:uat-withdrawal:'+str(operation_key)),
        'record_type':'recording_withdrawal','reason':reason,'authority':authority,'operation_key':str(operation_key)}
    old=response.verifications.filter(adapter=contract.WITHDRAWAL,result__operation_key=str(operation_key)).first()
    if old:
        if old.actor_id!=actor.pk or old.result!=result:raise ValidationError('This withdrawal key was already used')
        return old
    row=DeliverySourceVerification.objects.create(source=response,adapter=contract.WITHDRAWAL,result=result,actor=actor)
    event(actor,case,'client_uat.recording_retracted',source=response.pk,record=row.pk,client_decision_changed=False)
    bump(case);_wake(case);return row


def current_review(actor,response):
    target,_=current_response(actor,response)
    latest=response.verifications.filter(adapter__in=[contract.REVIEW,contract.WITHDRAWAL]).order_by('-pk').first()
    if latest is None or latest.adapter!=contract.REVIEW or latest.result.get('verdict')!='confirm':
        raise ValidationError('Current human confirmation of the client proof is required')
    cfg,value,authority=reviewer(latest.actor,response.dossier.case)
    if (latest.result.get('policy_id'),latest.result.get('authority'),latest.result.get('reviewer_role'))!=(cfg.pk,authority,value['reviewer_role']):
        raise ValidationError('The proof-review authority or rules changed')
    if value['independent_review'] and latest.actor_id in {response.actor_id,target.actor_id,*[pin['actor_id'] for pin in response.payload['proofs']]}:
        raise PermissionDenied('Current independent proof review required')
    inspection,uploads=_inspection_current(latest.actor,response)
    if (latest.result.get('inspection_id'),latest.result.get('inspection_sha256'))!=(inspection.pk,digest(inspection.result)):
        raise ValidationError('Review the current evidence check before using this response')
    _qualifying_rules(value,response,uploads,inspection.result['checks'])
    return latest


def _snapshot(response,review,actor):
    return {'purpose':'ordinary_client_uat','source_id':response.pk,'payload_sha256':digest(response.payload),
            'target_id':response.payload['target_id'],'review_id':review.pk,'review_sha256':digest(review.result),
            'export_actor_id':actor.pk,'external_authenticity_verified':False,'go_live_accepted':False,'payment_authorized':False}


@transaction.atomic
def export_gate(actor,case_id,response_id,review_id,expected,*,previous_binding_id=None,correction_reason=None):
    case=lock_case(actor,case_id,'client_uat.export',expected);readable(actor,case)
    response=exact(case,response_id,contract.RESPONSE);review=current_review(actor,response)
    if review.pk!=review_id:raise ValidationError('Use the current exact proof review')
    if response.payload['outcome'] not in ['approved','approved_with_workaround']:
        raise ValidationError('A request for changes or rejection cannot satisfy the client acceptance gate')
    d=response.dossier
    if delivery.latest(d,'release_outcome',False):raise ValidationError('Use reviewed historical source recovery; this cannot authorise a release that already happened')
    for action in ['pmo.gate_record','pmo.gate_verify']:require(actor,case,action)
    old=ClientUATGateBinding.objects.filter(review__source__dossier=d,review__source__kind=contract.RESPONSE,
        review__source__payload__target_id=response.payload['target_id']).order_by('-pk').first()
    if old:
        try:
            from .approvals import gate_current as full_gate_current
            full_gate_current(d.candidate,'uat_client',old.verification)
        except (PermissionDenied,ValidationError):
            if old.pk!=previous_binding_id or not isinstance(correction_reason,str) or not 1<=len(correction_reason.strip())<=2000:
                raise ValidationError('Review the earlier delivery handoff and give a reason for replacing it')
        else:return old
    from .approvals import candidate_requests
    requests=candidate_requests(d.candidate,'uat_client')
    if requests:
        gate=d.candidate.gates.filter(kind='uat_client').order_by('-pk').first()
        verification=gate.verifications.order_by('-pk').first() if gate else None
        if verification is None:raise ValidationError('The existing department-owned source still needs its own verification')
        # Preserve its original owner/contract and actual source decision. The
        # human witness path cannot replace that department's authority.
        from .approval_models import ApprovalGateBinding
        binding=ApprovalGateBinding.objects.filter(verification=verification).select_related('observation__receipt').first()
        if binding is None:raise ValidationError('The existing department-owned source must be verified first')
        from .approvals import current_observation
        current_observation(binding.observation)
        source=binding.observation.receipt
        if (verification.result.get('decision')!='accepted' or source.request_id not in {row.pk for row in requests} or
                response.payload['source_reference']!=source.external_ref or
                source.payload['subject']['candidate_ref']!=d.candidate.reference or
                aware(source.payload['decided_at'])!=aware(response.payload['responded_at'])):
            raise ValidationError('The human record must identify the exact existing client decision, version and time')
    else:
        target=exact(case,response.payload['target_id'],contract.TARGET)
        previous=d.candidate.gates.filter(kind='uat_client').order_by('-pk').first()
        expected_gate=old.verification.record_id if old else target.payload['replaces_gate_id']
        if (previous.pk if previous else None)!=expected_gate:
            raise ValidationError('Another client gate was recorded; review its current source context')
        from .gates import record_gate
        reference=f'psl:client-response:{response.pk}:review:{review.pk}:after:{old.pk if old else 0}'
        gate=record_gate(actor,case.pk,d.candidate_id,'uat_client',reference,response.evidence_id,None)
        case.refresh_from_db(fields=['revision'])
        result={'candidate_ref':d.candidate.reference,'requirements_sha256':d.candidate.requirements.sha256,
            'external_ref':gate.external_ref,'source_owner':'Client','evidence_sha256':gate.evidence.sha256,
            'decision':'accepted','critical_defects':None,'source_receipt':'psl:client-proof-review:'+str(review.pk)}
        verification=GateVerification.objects.create(record=gate,adapter=contract.GATE,result=result,actor=actor)
    row=ClientUATGateBinding.objects.create(review=review,verification=verification,actor=actor,snapshot=_snapshot(response,review,actor))
    event(actor,case,'client_uat.gate_bound',source=response.pk,review=review.pk,binding=row.pk,
          witness_is_not_client=True,deployment_authorized=False,financial_controls='independent',
          previous_binding=old.pk if old else None,correction_reason=correction_reason)
    bump(case);_wake(case);return row


def gate_current(candidate,verification):
    if verification is None:raise ValidationError('Client proof still needs a current verified reference')
    binding=ClientUATGateBinding.objects.select_related('review__source__dossier__case','review__source__actor').filter(
        verification=verification).order_by('-pk').first()
    if binding is None:raise ValidationError('Use the current human-recorded client response and proof review')
    head_gate=candidate.gates.filter(kind='uat_client').order_by('-pk').first()
    head_verification=head_gate.verifications.order_by('-pk').first() if head_gate else None
    if head_verification is None or head_verification.pk!=verification.pk:
        raise ValidationError('Use the latest exact client delivery gate reference')
    response=binding.review.source
    if response.dossier.candidate_id!=candidate.pk:raise ValidationError('The client proof belongs to a different version')
    review=current_review(binding.review.actor,response)
    if review.pk!=binding.review_id or binding.snapshot!=_snapshot(response,review,binding.actor):raise ValidationError('The client proof binding changed')
    if response.payload['outcome'] not in ['approved','approved_with_workaround'] or review.result.get('decision')!='accepted':
        raise ValidationError('Only an explicitly approved client response can satisfy this gate')
    readable(binding.actor,candidate.case);require(binding.actor,candidate.case,'client_uat.export')
    for action in ['pmo.gate_record','pmo.gate_verify']:require(binding.actor,candidate.case,action)
    return binding


def context(candidate):
    target=DeliverySource.objects.select_related('dossier__case').filter(dossier__candidate=candidate,kind=contract.TARGET).order_by('-pk').first()
    if target is None:return None
    response=head(target.dossier,contract.RESPONSE,target.pk)
    result={'target_id':target.pk,'target_sha256':digest(target.payload),'response_id':response.pk if response else None,
            'response_sha256':digest(response.payload) if response else None,'review_id':None,'review_sha256':None,'status':'awaiting_response'}
    if response:
        latest=response.verifications.filter(adapter__in=[contract.REVIEW,contract.WITHDRAWAL]).order_by('-pk').first()
        result.update(review_id=latest.pk if latest else None,review_sha256=digest(latest.result) if latest else None,status='needs_proof_review')
        if latest:
            try:current_review(latest.actor,response)
            except (PermissionDenied,ValidationError):result['status']='unavailable'
            else:result['status']='current'
    return result
