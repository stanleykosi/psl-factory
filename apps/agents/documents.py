from apps.core.evidence_access import public_evidence,restricted
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.models import Case
from apps.core.services import lock_case, event
from apps.identity.services import require
from apps.pmo.services import subject
from apps.documents.models import Template, Version
from apps.documents.controlled import create_version, preflight
from .models import AgentRun


class SyntheticDocumentProvider:
    name='synthetic-document-extractive-v1'
    def draft(self,fields,sources):
        first=sources[0]
        quote=first.body.splitlines()[0][:1000]
        return {key:{'text':quote,'evidence_ids':[first.pk]} for key in fields}


def draft_document(actor,case_id,template_id,title,audience,evidence_ids,expected,document_id=None,provider=None):
    case=Case.objects.get(pk=case_id)
    require(actor,case,'agent.document')
    require(actor,case,'document.draft')
    template=Template.objects.filter(case=case,pk=template_id).first()
    if not template or not isinstance(evidence_ids,list) or not evidence_ids or len(evidence_ids)>10:
        raise ValidationError('Choose a case template and 1–10 source records')
    if template.definition['document_type']=='accepted_finance_metadata':raise ValidationError('Use the bounded native metadata agent')
    sources=[subject(case,pk) for pk in evidence_ids]
    if any(restricted(e) for e in sources):raise ValidationError('Restricted prerequisite source evidence must use the scoped P02 interface')
    if sum(len(e.body) for e in sources)>16000:
        raise ValidationError('Document agent input budget exceeded')
    if provider is None:
        if not case.synthetic:
            raise ValidationError('Operational document drafting requires an approved real provider')
        provider=SyntheticDocumentProvider()
    fields=template.definition['audience_fields'].get(audience)
    if not fields:
        raise ValidationError('Audience is not supported by the template')
    output=provider.draft(fields,sources)
    if not isinstance(output,dict) or set(output)-set(fields):
        raise ValidationError('Provider attempted an ungranted document field or tool')
    by_id={e.pk:e for e in sources}
    for value in output.values():
        if not isinstance(value,dict) or set(value)!={'text','evidence_ids'} or not isinstance(value['text'],str) or not isinstance(value['evidence_ids'],list) or not value['evidence_ids']:
            raise ValidationError('Malformed document provider output')
        if any(type(pk) is not int or pk not in by_id for pk in value['evidence_ids']) or not any(value['text'] and value['text'] in by_id[pk].body for pk in value['evidence_ids']):
            raise ValidationError('Provider text must be an exact quote from its granted sources')
    with transaction.atomic():
        # Provider output is untrusted; recheck current grants and revision after it returns.
        case=lock_case(actor,case_id,'agent.document',expected)
        version=create_version(actor,case_id,template_id,title,audience,output,expected,document_id)
        run=AgentRun.objects.create(case=case,actor=actor,evidence=sources[0],provider=provider.name,process_id='P52',
            result={'capability':'A02/A06 restricted draft','version_id':version.pk,'source_ids':evidence_ids,'human_review_required':True})
        event(actor,case,'agent.document_drafted',run=run.pk,version=version.pk)
        return version


@transaction.atomic
def check_document(actor,case_id,version_id):
    case=lock_case(actor,case_id,'agent.document')
    require(actor,case,'document.read')
    version=Version.objects.select_related('document__case','template').filter(pk=version_id,document__case=case).first()
    if not version or not version.source_manifest:
        raise ValidationError('Choose a case document with source evidence')
    if version.template.definition['document_type']=='accepted_finance_metadata':raise ValidationError('Use native metadata investigation')
    findings=preflight(version)
    run=AgentRun.objects.create(case=case,actor=actor,evidence_id=version.source_manifest[0]['id'],provider='deterministic-document-preflight-v1',
        process_id='P53',result={'capability':'A08 independent structural checks','version_id':version.pk,'findings':findings,'business_approval':False})
    event(actor,case,'agent.document_checked',run=run.pk,version=version.pk,findings=len(findings))
    return run


@transaction.atomic
def check_candidate(actor,case_id,candidate_id):
    case=lock_case(actor,case_id,'agent.gates')
    from apps.pmo.models import DeliveryCandidate
    from apps.pmo.gates import gate_manifest, gate_summary
    candidate=DeliveryCandidate.objects.filter(case=case,pk=candidate_id).first()
    if not candidate:
        raise ValidationError('Candidate is outside the granted case')
    summary=gate_summary(candidate,actor)
    run=AgentRun.objects.create(case=case,actor=actor,evidence=candidate.requirements,provider='deterministic-gate-preflight-v1',process_id='P31',
        result={'capability':'A07 external-owner evidence preflight','candidate_id':candidate.pk,'requirements_sha256':candidate.requirements.sha256,
            'gate_manifest':gate_manifest(candidate),'findings':summary,'release_authorized':False,
            'next_work':'Collect missing owner evidence; reported references require source verification'})
    event(actor,case,'agent.gates_checked',run=run.pk,candidate=candidate.pk,release_authorized=False)
    return run
