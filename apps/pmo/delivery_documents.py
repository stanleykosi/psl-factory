from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from apps.core.services import lock_case
from apps.documents.controlled import create_version
from apps.documents.models import Template
from apps.policy.services import decision_authority
from .delivery import dossier_for,ensure_open
from .delivery_closure import go_live_inputs,handover_inputs,closure_inputs
from .models import DeliveryDocumentBinding
from .services import subject

INPUTS={'go_live':go_live_inputs,'handover':handover_inputs,'closure':closure_inputs}


@transaction.atomic
def draft_delivery_document(actor,case_id,dossier_id,purpose,template_id,data,expected):
    case=lock_case(actor,case_id,'delivery.manage',expected);d=dossier_for(case,dossier_id);ensure_open(d);decision_authority(actor,case,'PM')
    if purpose not in INPUTS:raise ValidationError('Choose go_live, handover or closure')
    snapshot=INPUTS[purpose](d,data)
    template=Template.objects.filter(case=case,pk=template_id,definition__document_type='project_artifact').first()
    if not template:raise ValidationError('Select this case controlled project artifact template')
    if purpose=='go_live':
        fields={key:{'text':subject(case,pk).body,'evidence_ids':[pk]} for key,pk in zip(['scope','risks','next_steps'],[data['checklist'],data['incident_reporting'],data['rollback']])}
        source=d.evidence_id;audience='client'
    elif purpose=='handover':
        fields={key:{'text':subject(case,pk).body,'evidence_ids':[pk]} for key,pk in zip(['scope','next_steps'],[data['support_document'],data['escalation_document']])}
        source=d.evidence_id;audience='internal'
    else:
        source=data['report_evidence_id'];audience='internal'
        fields={'scope':{'text':subject(case,source).body,'evidence_ids':[source]},
            'next_steps':{'text':'Archive and Support/Operations receipts, retrospective and Finance notification coverage are bound to this exact report. This does not settle debt or authorize deployment.','evidence_ids':[source]}}
    fields.update(executive_summary={'text':f'{purpose.replace("_"," ").title()} for {d.candidate.reference}; source-bound evidence, no deployment dispatch.','evidence_ids':[source]},
        status={'text':'Actual '+purpose.replace('_',' ')+' evidence; independent financial and release controls remain.','evidence_ids':[source]})
    if purpose=='handover':
        fields['executive_summary']['text']=f'Support and Operations handover for {d.candidate.reference}.'
        fields['status']['text']='Handover package prepared. Actual recipient receipt and any gaps are recorded separately.'
    if purpose=='go_live':
        fields['executive_summary']['text']=f'Go-live and business acceptance report for {d.candidate.reference}.'
        fields['status']['text']='Prepared for actual PM and Client sign-off. Acceptance is recorded separately.'
    if purpose=='closure':
        fields['executive_summary']['text']=f'Project closure report for {d.candidate.reference}.'
        fields['status']['text']='PM report prepared for the prescribed closure decision.'
    if purpose=='go_live' and not {'scope','risks','next_steps'}.issubset(template.definition['audience_fields'].get('client',[])):
        raise ValidationError('Go-live client projection must contain checklist, incident reporting and rollback sections')
    if purpose=='handover' and not {'scope','next_steps'}.issubset(template.definition['audience_fields'].get('internal',[])):
        raise ValidationError('Handover projection must contain support and escalation documents')
    title='Go-live report' if purpose=='go_live' else purpose.replace('_',' ').title()
    from apps.documents.pmo_sections import complete_native_client_sections
    fields = complete_native_client_sections(fields, audience, [source])
    v=create_version(actor,case.pk,template.pk,title+': '+d.candidate.reference,audience,fields,case.revision)
    DeliveryDocumentBinding.objects.create(version=v,dossier=d,purpose=purpose,data=data,snapshot=snapshot)
    return v


def binding_findings(binding):
    try:
        d=dossier_for(binding.dossier.case,binding.dossier_id)
        if binding.snapshot!=INPUTS[binding.purpose](d,binding.data):return ['Delivery source/policy changed; draft and review a fresh exact version']
        if binding.purpose=='handover':
            from apps.documents.controlled import publication_requirements
            # Validate intended recipients directly, avoiding recursive document preflight.
            from apps.policy.services import active_component,reference_values
            from apps.identity.services import require
            c=active_component('D11.recipient_grant_refs',d.case)
            recipients=[r['user_id'] for r in reference_values(c) if r['audience']=='internal']
            from django.contrib.auth import get_user_model
            if not recipients:raise ValidationError('No configured internal Support/Operations recipient')
            for pk in recipients:require(get_user_model().objects.get(pk=pk),d.case,'delivery.support_receive')
    except (ValidationError,PermissionDenied) as exc:return ['Delivery control held: '+str(exc)]
    return []
