from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from apps.core.services import lock_case, event, bump, add_evidence
from apps.identity.services import require
from apps.documents.controlled import create_version
from apps.documents.contracts import validate
from .services import subject
from .models import DeliveryCandidate, GateRecord, GateVerification, GateDocumentBinding

# Source owner labels from P29–P33; these are not assignments of people or local approval authority.
GATE_OWNERS={'qa_exit':'QA Lead','uat_product_manager':'Product Manager','uat_product_owner':'Product Owner',
    'uat_client':'Client','engineering_go':'Engineering','glpi_security':'Security','glpi_cto':'CTO','glpi_ceo':'CEO',
    'go_live_pm':'PM','go_live_client':'Client'}


@transaction.atomic
def register_candidate(actor,case_id,reference,requirements_id,expected):
    case=lock_case(actor,case_id,'pmo.candidate',expected)
    requirements=subject(case,requirements_id,'requirements')
    if case.kind!='project' or not reference.strip() or len(reference)>160:
        raise ValidationError('A project candidate reference and requirements evidence are required')
    if DeliveryCandidate.objects.filter(case=case,reference=reference).exists():
        raise ValidationError('Candidate reference already exists; preserve its history')
    candidate=DeliveryCandidate.objects.create(case=case,reference=reference,requirements=requirements,created_by=actor)
    event(actor,case,'pmo.candidate_registered',candidate=candidate.pk,requirements=requirements.pk)
    bump(case)
    return candidate


@transaction.atomic
def record_gate(actor,case_id,candidate_id,kind,external_ref,evidence_id,expected):
    case=lock_case(actor,case_id,'pmo.gate_record',expected)
    candidate=DeliveryCandidate.objects.filter(case=case,pk=candidate_id).first()
    if not candidate or kind not in GATE_OWNERS or not external_ref.strip() or len(external_ref)>240:
        raise ValidationError('Choose a case candidate, known gate and external source reference')
    evidence=subject(case,evidence_id)
    if GateRecord.objects.filter(candidate=candidate,kind=kind,external_ref=external_ref,evidence=evidence).exists():
        raise ValidationError('This exact gate source was already captured')
    record=GateRecord.objects.create(candidate=candidate,kind=kind,external_ref=external_ref,source_owner=GATE_OWNERS[kind],evidence=evidence,created_by=actor)
    event(actor,case,'pmo.gate_reported',candidate=candidate.pk,record=record.pk,owner=record.source_owner,verified=False)
    bump(case)
    return record


def verify_gate(actor,case_id,record_id,expected,adapter=None):
    from apps.core.models import Case
    from adapters.pmo_gates import SyntheticGateAdapter
    case=Case.objects.get(pk=case_id)
    require(actor,case,'pmo.gate_verify')
    record=GateRecord.objects.select_related('candidate__requirements','evidence').filter(candidate__case=case,pk=record_id).first()
    if not record:
        raise ValidationError('Gate record is outside this project')
    from .approvals import candidate_requests
    if candidate_requests(record.candidate,record.kind):raise ValidationError('Use the current department-owned P02 observation; synthetic verification cannot override it')
    if not case.synthetic:
        raise ValidationError('Operational verification requires a reviewed authoritative gate-source adapter; capture remains available')
    adapter=adapter or SyntheticGateAdapter()
    result=adapter.read(record)
    validate({'type':'object','properties':{
        'candidate_ref':{'type':'string'},'requirements_sha256':{'type':'string'},'external_ref':{'type':'string'},
        'source_owner':{'type':'string'},'evidence_sha256':{'type':'string'},'decision':{'enum':['accepted','rejected','unknown']},
        'critical_defects':{'type':['integer','null'],'minimum':0},'source_receipt':{'type':'string','minLength':1}},
        'required':['candidate_ref','requirements_sha256','external_ref','source_owner','evidence_sha256','decision','critical_defects','source_receipt'],
        'additionalProperties':False},result)
    expected_bindings={'candidate_ref':record.candidate.reference,'requirements_sha256':record.candidate.requirements.sha256,
        'external_ref':record.external_ref,'source_owner':record.source_owner,'evidence_sha256':record.evidence.sha256}
    if any(result[k]!=v for k,v in expected_bindings.items()):
        raise ValidationError('Source result does not match candidate, requirements, owner and exact evidence version')
    if record.kind=='qa_exit' and result['decision']=='accepted' and result['critical_defects']!=0:
        result=dict(result,decision='unknown' if result['critical_defects'] is None else 'rejected')
    with transaction.atomic():
        case=lock_case(actor,case_id,'pmo.gate_verify',expected)
        latest=record.candidate.gates.filter(kind=record.kind).order_by('-pk').first()
        if latest.pk!=record.pk:
            raise ValidationError('A newer gate-source record needs verification')
        verification=GateVerification.objects.create(record=record,adapter=adapter.name,result=result,actor=actor)
        event(actor,case,'pmo.gate_verified',record=record.pk,verification=verification.pk,decision=result['decision'],adapter=adapter.name)
        bump(case)
        return verification


def gate_manifest(candidate):
    result=[]
    for kind in GATE_OWNERS:
        record=candidate.gates.filter(kind=kind).order_by('-pk').first()
        if record:
            verification=record.verifications.order_by('-pk').first()
            result.append({'kind':kind,'record':record.pk,'verification':verification.pk if verification else None})
        from .approvals import gate_context
        context=gate_context(candidate,kind)
        if context is not None:result.append({'kind':kind,'p02_context':context})
    return result


def gate_summary(candidate,actor=None):
    lines=[]
    for kind,owner in GATE_OWNERS.items():
        record=candidate.gates.filter(kind=kind).order_by('-pk').first()
        verification=record.verifications.order_by('-pk').first() if record else None
        status=verification.result['decision'] if verification else 'unverified' if record else 'missing'
        from .approvals import gate_current,gate_context
        if gate_context(candidate,kind) is not None:
            try:gate_current(candidate,kind,verification)
            except (ValidationError,PermissionDenied):status='verification_unavailable'
        if actor is not None:
            from .approvals import candidate_requests,visibility
            if any(visibility(actor,r)['status']=='unavailable' for r in candidate_requests(candidate,kind)):status='verification_unavailable'
        lines.append(f'{kind}: {status} ({owner})')
    return lines


@transaction.atomic
def draft_gate_packet(actor,case_id,candidate_id,template_id,audience,expected):
    case=lock_case(actor,case_id,'pmo.gate_packet',expected)
    candidate=DeliveryCandidate.objects.filter(case=case,pk=candidate_id).first()
    if not candidate:
        raise ValidationError('Candidate is outside this project')
    summary='Candidate '+candidate.reference+'. External owners retain approval authority. This packet is evidence tracking, not release authorization.'
    status='\n'.join(gate_summary(candidate,actor))
    evidence=add_evidence(actor,case.pk,'gate_packet',summary+'\n'+status,'psl:gate-packet:'+str(candidate.pk),expected)
    case.refresh_from_db()
    from apps.documents.pmo_sections import complete_native_client_sections
    fields = complete_native_client_sections({'executive_summary': {'text': summary, 'evidence_ids': [evidence.pk]},
        'status': {'text': status, 'evidence_ids': [evidence.pk]}}, audience, [evidence.pk])
    version=create_version(actor,case.pk,template_id,'Gate evidence: '+candidate.reference,audience,fields,case.revision)
    GateDocumentBinding.objects.create(version=version,candidate=candidate,manifest=gate_manifest(candidate))
    event(actor,case,'pmo.gate_packet_drafted',candidate=candidate.pk,version=version.pk,release_authorized=False)
    return version
