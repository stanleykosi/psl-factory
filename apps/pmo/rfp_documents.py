from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.policy.services import active_component,reference_values,decision_authority
from apps.documents.controlled import create_version
from apps.documents.models import Template,PublicationReceipt
from .models import RFPDocumentBinding,RFPSubmission
from .rfp import current_response,reviewed,public_terms_for
from .commercial import valid_approvals
from .services import subject

def inputs(v,key,*,dispatch=False):
    case=v.rfp.case;current_response(case,v.pk)
    public_terms_for(v)
    reviews=reviewed(v);decisions=valid_approvals(v.commercial,['PM','Head of PMO','CEO'])
    c=active_component('D11.adapter_configuration_refs',case)
    routes=[r for r in reference_values(c) if r['key']==key]
    if len(routes)!=1:raise ValidationError('Select one verified configured RFP route')
    route=routes[0];i=v.intake
    if dispatch and i.deadline_status=='unknown':raise ValidationError('Verify the actual submission deadline or attest explicitly that none is stated')
    if dispatch and i.deadline_status=='stated' and timezone.now()>i.deadline_at:raise ValidationError('Submission deadline has passed; record an evidenced revised intake before new dispatch')
    return {'response':v.pk,'sources':v.snapshot,'reviews':reviews,'costing_decisions':decisions,'route_config':c.pk,'route':route,
        'deadline_status':i.deadline_status,'deadline_at':i.deadline_at.isoformat() if i.deadline_at else None}

def sender(actor,version):
    b=RFPDocumentBinding.objects.filter(version=version).first()
    if not b:return
    case=version.document.case;require(actor,case,'rfp.submit')
    errors=[]
    for role in b.snapshot['route']['sender_roles']:
        try:decision_authority(actor,case,role);return
        except (ValidationError,PermissionDenied) as exc:errors.append(str(exc))
    raise PermissionDenied('Publisher needs a current configured RFP sender role')

@transaction.atomic
def draft(actor,case_id,response_id,template_id,route_key,expected):
    case=lock_case(actor,case_id,'rfp.submit',expected);v=current_response(case,response_id);snapshot=inputs(v,route_key)
    t=Template.objects.filter(case=case,pk=template_id,definition__document_type__in=['rfp_response','project_artifact']).first()
    mapping='requirements_mapping' if t and t.definition['document_type']=='rfp_response' else 'risks'
    terms='commercial_terms' if t and t.definition['document_type']=='rfp_response' else 'next_steps'
    required={'executive_summary','scope',mapping,terms}
    if not t or not required.issubset(t.definition['audience_fields'].get('client',[])):raise ValidationError('Select a client project-artifact template containing summary, technical scope, requirements mapping and commercial terms')
    if t.definition.get('internal_review_required',True) is not True:raise ValidationError('RFP client responses require final controlled document review')
    e=v.evidence;public_terms=public_terms_for(v);plan=subject(case,v.commercial.sources['plan'])
    fields={'executive_summary':{'text':'RFP '+v.rfp.reference+' response '+str(v.number),'evidence_ids':[e.pk]},
        'scope':{'text':e.body,'evidence_ids':[e.pk]},
        mapping:{'text':'\n'.join(row['key']+': '+row['disposition']+' — '+row['response'] for row in v.matrix),'evidence_ids':sorted(set(row['evidence_id'] for row in v.matrix))},
        terms:{'text':public_terms.body+'\nTimeline: '+plan.body,'evidence_ids':[public_terms.pk,plan.pk]}}
    version=create_version(actor,case.pk,t.pk,'RFP response '+v.rfp.reference,'client',fields,case.revision)
    RFPDocumentBinding.objects.create(version=version,response=v,snapshot=snapshot);sender(actor,version);return version

def binding_findings(b):
    try:
        if b.version.template.definition.get('internal_review_required',True) is not True:return ['RFP client responses require final controlled document review']
        if b.snapshot!=inputs(b.response,b.snapshot['route']['key']):return ['RFP sources, reviews or route changed; draft and review a new exact response']
    except (ValidationError,PermissionDenied) as exc:return ['RFP publication held: '+str(exc)]
    return []


def dispatch_requirements(version):
    """Deadline checks hold new transmission, not preparation, human review or receipt lookup."""
    binding=RFPDocumentBinding.objects.filter(version=version).select_related('response__rfp__case').first()
    if binding and binding.snapshot!=inputs(binding.response,binding.snapshot['route']['key'],dispatch=True):
        raise ValidationError('Review the current RFP submission sources and destination before sending')

def recipient_requirements(b,recipients):
    if sorted(b.snapshot['route']['recipient_ids'])!=recipients:raise ValidationError('RFP route must equal the exact configured client recipients')
    c=active_component('D05.role_principal_assignments',b.response.rfp.case)
    return {'D11.adapter_configuration_refs':b.snapshot['route_config'],c.component:c.pk}

@transaction.atomic
def capture_submission(actor,case_id,version_id,expected):
    case=lock_case(actor,case_id,'rfp.submit',expected)
    b=RFPDocumentBinding.objects.filter(version_id=version_id,response__rfp__case=case).first()
    if not b:raise ValidationError('Select this case exact RFP response document')
    old=RFPSubmission.objects.filter(version_id=version_id).first()
    if old:return old
    from adapters.rfp import LocalRFPAdapter
    receipts=LocalRFPAdapter().receipts(b)
    if not receipts:raise ValidationError('Actual matching delivered receipts for every route recipient are required')
    at=max(r.created_at for r in receipts);deadline=b.response.intake.deadline_at
    s=RFPSubmission.objects.create(response=b.response,version=b.version,snapshot=b.snapshot,receipt_ids=[r.pk for r in receipts],submitted_at=at,late=bool(deadline and at>deadline),actor=actor)
    event(actor,case,'rfp.submission_recorded',submission=s.pk,receipts=s.receipt_ids,late=s.late,transport='local_recipient_inbox');bump(case);return s
