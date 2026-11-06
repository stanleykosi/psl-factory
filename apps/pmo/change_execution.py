from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from apps.core.services import lock_case, event, bump
from apps.documents.controlled import create_version
from apps.documents.models import Template, PublicationReceipt
from apps.policy.services import decision_authority
from .models import (ChangeAuthorization, ChangeDocumentBinding, ChangeExecutionEvent,
    ChangeClosure, BaselineAdoption)
from .changes import authorization_inputs
from .commercial import note_required, valid_approvals
from .services import subject


def validate_authorization(case, authorization):
    adopted = BaselineAdoption.objects.filter(revision_id=authorization.commercial_id).first() if authorization.commercial_id else None
    from .recoveries import active_recovery
    recovered=active_recovery(case,'signed_adoption',adopted.pk) if adopted else None
    ids, flags, decisions = authorization_inputs(case, authorization.version, adopted.after if adopted else None,check_authority=not bool(recovered))
    from .standard_changes import validate_snapshot
    validate_snapshot(case,authorization,flags)
    if ids != authorization.assessment_ids or decisions != authorization.decision_ids:
        raise ValidationError('Change assessment or decision snapshot changed; authorize a new revision')
    if authorization.commercial_id:
        if not adopted:
            raise ValidationError('Adopt the signed controlled commercial baseline before implementation tracking')
        valid_approvals(authorization.commercial,check_authority=not bool(recovered))
    return flags


def get_authorization(case, pk):
    auth = ChangeAuthorization.objects.select_related('version__change__case','commercial').filter(pk=pk, version__change__case=case).first()
    if not auth:raise ValidationError('Change authorization must belong to this case')
    validate_authorization(case,auth)
    return auth


def authorization_recovery(case,auth):
    from .recoveries import active_recovery
    adoption=BaselineAdoption.objects.filter(revision_id=auth.commercial_id).first() if auth.commercial_id else None
    return active_recovery(case,'signed_adoption',adoption.pk) if adoption else None


def execution_manifest(auth):
    from .change_impacts import deviation_hold
    deviation_hold(auth)
    latest = {}
    for e in auth.execution.order_by('pk'):latest[e.kind]=e
    if set(latest)!={'plan_updated','implemented','testing_validated','documentation_updated'}:
        raise ValidationError('Updated plan, implementation, validated testing and documentation evidence required')
    if latest['testing_validated'].pk < latest['implemented'].pk:
        raise ValidationError('Latest implementation has not been validated')
    from .change_impacts import validate_execution
    validate_execution(auth, latest)
    return [latest[k].pk for k in sorted(latest)]


@transaction.atomic
def record_execution(actor, case_id, authorization_id, kind, evidence_id, note, expected, *, scope_items=None, dossier_id=None, candidate_id=None):
    actions={'plan_updated':'change.manage','implemented':'change.progress:Engineering','testing_validated':'change.progress:QA','documentation_updated':'change.manage'}
    if kind not in actions:raise ValidationError('Choose an explicit implementation evidence category')
    case=lock_case(actor,case_id,actions[kind],expected)
    auth=get_authorization(case,authorization_id)
    if ChangeClosure.objects.filter(authorization=auth).exists():raise ValidationError('Closed changes are historical; log a new change')
    note_required(note)
    kinds={'plan_updated':'plan','implemented':'change_implementation','testing_validated':'change_validation','documentation_updated':'document'}
    evidence=subject(case,evidence_id,kinds[kind])
    prior=set(auth.execution.values_list('kind',flat=True))
    if kind=='implemented' and 'plan_updated' not in prior:raise ValidationError('Record the updated plan before implementation evidence')
    if kind=='testing_validated' and 'implemented' not in prior:raise ValidationError('Record completed implementation before testing validation')
    from .change_impacts import execution_details
    details,evidence=execution_details(actor,case,auth,kind,evidence,scope_items,dossier_id,candidate_id)
    result=ChangeExecutionEvent.objects.create(impact_details=details,authorization=auth,kind=kind,evidence=evidence,note=note,actor=actor)
    event(actor,case,'change.execution_evidence',execution=result.pk,authorization=auth.pk,kind=kind)
    bump(case)
    return result


@transaction.atomic
def draft_change_document(actor,case_id,authorization_id,template_id,purpose,expected,audience='client'):
    case=lock_case(actor,case_id,'change.manage',expected)
    auth=get_authorization(case,authorization_id)
    if purpose not in ['notice','go_live']:raise ValidationError('Choose a notice or change go-live document')
    if ChangeClosure.objects.filter(authorization=auth).exists():raise ValidationError('Closed change history requires a new revision')
    if audience not in ['internal','client'] or purpose=='go_live' and audience!='client':
        raise ValidationError('Go-live acceptance is a client document; notices use an explicit internal or client audience')
    template=Template.objects.filter(case=case,pk=template_id,definition__document_type__in=['status_report','project_artifact']).first()
    if not template:raise ValidationError('Select this case reviewed change template')
    v=auth.version
    from .change_impacts import timeline_text, timeline_required
    approved_timeline=timeline_text(auth)
    if purpose=='notice' and timeline_required(auth) and 'timeline' not in template.definition['audience_fields'].get(audience,[]):
        raise ValidationError('Timeline-impact notice template must display the approved timeline')
    execution_ids = execution_manifest(auth) if purpose=='go_live' else []
    fields={'executive_summary':{'text':v.description,'evidence_ids':[v.evidence_id]},
        'scope':{'text':v.module+': '+v.description,'evidence_ids':[v.evidence_id]},
        'status':{'text':'Authorized '+v.category+' change '+v.change.reference+'. This document does not authorize deployment.','evidence_ids':[v.evidence_id]},
        'timeline':{'text':approved_timeline or 'See the exact linked owner impact and agreed timeline evidence.','evidence_ids':sorted(set(v.assessments.filter(pk__in=auth.assessment_ids).values_list('evidence_id',flat=True)))},
        'next_steps':{'text':'Coordinate implementation, validate testing and capture signed change go-live acceptance.','evidence_ids':[v.evidence_id]}}
    if purpose=='go_live':
        fields['status']={'text':'Completed implementation and validated testing recorded for '+v.change.reference+'. Capture PM and Client acceptance of this exact version.',
            'evidence_ids':sorted(set(auth.execution.filter(pk__in=execution_ids).values_list('evidence_id',flat=True)))}
    if v.evidence.source=='psl:p56-confirmed-request/v1':
        from apps.identity.services import require
        from apps.documents.controlled import _create_version
        require(actor,case,'change.read')
        version=_create_version(actor,case.pk,template.pk,'Change '+v.change.reference+' v'+str(v.number)+' '+purpose,audience,fields,case.revision,authorized_restricted_source_ids=(v.evidence_id,))
    else:
        version=create_version(actor,case.pk,template.pk,'Change '+v.change.reference+' v'+str(v.number)+' '+purpose,audience,fields,case.revision)
    ChangeDocumentBinding.objects.create(version=version,authorization=auth,purpose=purpose,execution_ids=execution_ids,
        authority_recovery=authorization_recovery(case,auth))
    return version


def change_binding_findings(binding):
    try:
        validate_authorization(binding.authorization.version.change.case,binding.authorization)
        from .change_impacts import notice_has_timeline
        if binding.purpose=='notice' and not notice_has_timeline(binding.authorization,binding.version):
            return ['Notice must display the exact approved timeline impact']
        recovered=authorization_recovery(binding.authorization.version.change.case,binding.authorization)
        if binding.authority_recovery_id!=(recovered.pk if recovered else None):
            return ['Historical authority recovery changed; prepare and review a fresh document version']
        if binding.purpose=='go_live' and binding.execution_ids!=execution_manifest(binding.authorization):
            return ['Implementation or testing evidence changed; prepare and review a new go-live document']
    except (ValidationError,PermissionDenied) as exc:return ['Controlled change source is stale: '+str(exc)]
    return []


@transaction.atomic
def close_change(actor,case_id,authorization_id,receipt_id,pm_signature_id,client_signature_id,note,expected):
    case=lock_case(actor,case_id,'change.manage',expected)
    auth=get_authorization(case,authorization_id)
    decision_authority(actor,case,'PM')
    note_required(note)
    if ChangeClosure.objects.filter(authorization=auth).exists():raise ValidationError('Change is already closed')
    execution_ids=execution_manifest(auth)
    receipt=PublicationReceipt.objects.filter(pk=receipt_id,publication__version__changedocumentbinding__authorization=auth,
        publication__version__changedocumentbinding__purpose='go_live',publication__version__audience='client').first()
    _, flags, _ = authorization_inputs(case,auth.version,
        BaselineAdoption.objects.get(revision=auth.commercial).after if auth.commercial_id else None)
    notices=PublicationReceipt.objects.filter(publication__version__changedocumentbinding__authorization=auth,
        publication__version__changedocumentbinding__purpose='notice')
    if flags['client_facing'] or flags['timeline_impact']:
        notices=notices.filter(publication__version__audience='client')
    from .change_impacts import notice_has_timeline
    notice=any(notice_has_timeline(auth,r.publication.version) for r in notices.select_related('publication__version'))
    if not receipt or not notice:raise ValidationError('Recorded delivery of change notice and exact change go-live document required')
    binding=ChangeDocumentBinding.objects.get(version=receipt.publication.version)
    if binding.execution_ids!=execution_ids:raise ValidationError('Signed go-live document is stale for current implementation evidence')
    pm=subject(case,pm_signature_id,'signature');client=subject(case,client_signature_id,'signature')
    if pm.pk==client.pk:raise ValidationError('Capture each PM and Client signature reference explicitly')
    closure=ChangeClosure.objects.create(authorization=auth,receipt=receipt,pm_signature=pm,client_signature=client,
        execution_ids=execution_ids,note=note,actor=actor)
    event(actor,case,'change.closed',closure=closure.pk,authorization=auth.pk,receipt=receipt.pk)
    bump(case)
    return closure
