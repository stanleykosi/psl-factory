from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.services import lock_case
from apps.documents.controlled import create_version
from apps.documents.models import Template
from adapters.emergencies import LocalEmergencyEvidenceAdapter
from .emergencies import outcome_for, timing
from .models import EmergencyDocumentBinding


@transaction.atomic
def draft_retrospective(actor,case_id,outcome_id,template_id,audience,expected):
    case=lock_case(actor,case_id,'emergency.manage',expected);outcome=outcome_for(case,outcome_id)
    if audience not in ['internal','client']:raise ValidationError('Choose an explicit emergency report audience')
    template=Template.objects.filter(case=case,pk=template_id,definition__document_type__in=['project_artifact','status_report']).first()
    if not template:raise ValidationError('Choose this case controlled report template')
    source=LocalEmergencyEvidenceAdapter().read(case,outcome)
    clock=timing(case,outcome);ref=outcome.profile.version.change.reference
    ids=source['source_evidence_ids']
    if len(ids)>20:raise ValidationError('Emergency report source budget exceeded; narrow or summarize its evidence before drafting')
    from .models import EmergencyRetrospectiveRecord
    reconciled=EmergencyRetrospectiveRecord.objects.filter(outcome=outcome).first()
    status=reconciled.snapshot['status'] if reconciled else 'not reconciled'
    late='unknown' if clock['log_late'] is None else 'yes' if clock['log_late'] else 'no'
    fields={'executive_summary':{'text':'Emergency '+ref+': actual implementation '+outcome.implemented_at.isoformat()+'. '+outcome.note,'evidence_ids':[outcome.evidence_id]},
        'status':{'text':f"P61/P62 evidence: {status}. {source['review_count']} post-implementation reviews and {source['decision_count']} retrospective decision records. Log late: {late}. This evidence report grants no scope, financial or deployment approval.",'evidence_ids':ids},
        'next_steps':{'text':'Human owners review recorded outcomes, missing authority and deadline exceptions; no retrospective decision substitutes for preauthorization. Ordinary scope/cost follow-ups: '+str(source['manifest']['followups']),'evidence_ids':ids}}
    version=create_version(actor,case.pk,template.pk,'Emergency retrospective: '+ref,audience,fields,case.revision)
    EmergencyDocumentBinding.objects.create(version=version,outcome=outcome,manifest=source['manifest'])
    return version


def binding_findings(binding):
    outcome=binding.outcome;case=outcome.profile.version.change.case
    if LocalEmergencyEvidenceAdapter().read(case,outcome)['manifest']!=binding.manifest:
        return ['Emergency source/authority/policy changed; prepare a new exact reviewed report']
    return []
