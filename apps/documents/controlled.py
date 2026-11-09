from apps.core.evidence_access import public_evidence,restricted
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from apps.core.services import lock_case, event, bump
from apps.identity.services import require
from apps.pmo.services import subject
from apps.pmo.models import Baseline
from apps.policy.services import require_operation, decision_authority, reference_values
from apps.workflows.models import HumanTask, TaskEvent
from .models import Template, Document, Version, ControlledReview, Publication, PublicationJob
from .contracts import validate_template, validate, digest, FIELDS, AUDIENCES


def baseline_manifest(case):
    baseline=Baseline.objects.filter(case=case).first()
    return {k:getattr(baseline,k) for k in ['plan_id','costing_id','sow_id','signed_id']} if baseline else {}


@transaction.atomic
def register_template(actor,case_id,name,definition,evidence_id,expected):
    case=lock_case(actor,case_id,'document.template',expected)
    validate_template(definition, case=case)
    evidence=subject(case,evidence_id,'policy_decision')
    if not name.strip() or len(name)>160:
        raise ValidationError('Template name is required and limited to 160 characters')
    number=(Template.objects.filter(case=case,name=name).order_by('-version').values_list('version',flat=True).first() or 0)+1
    template=Template.objects.create(case=case,name=name,version=number,definition=definition,evidence=evidence,created_by=actor)
    event(actor,case,'document.template_registered',template=template.pk,version=number)
    bump(case)
    return template


def project_payload(title,definition,audience,fields):
    allowed=definition['audience_fields'].get(audience)
    if not allowed:
        raise ValidationError('Template does not support the intended audience')
    return {'title':title,'type':definition['document_type'],'sections':[
        {'heading':key,'text':fields[key]['text']} for key in allowed if key in fields and fields[key]['text'].strip()]}


@transaction.atomic
def create_version(actor,case_id,template_id,title,audience,fields,expected,document_id=None,*,template_scope_id=None):
    if audience=='group':raise ValidationError('Use the native group disclosure preparation service')
    return _create_version(actor,case_id,template_id,title,audience,fields,expected,document_id,template_scope_id=template_scope_id)


@transaction.atomic
def _create_version(actor,case_id,template_id,title,audience,fields,expected,document_id=None,*,authorized_restricted_source_ids=(),template_scope_id=None):
    """Private storage primitive. Domain callers must independently authorize and
    recompute current fields plus the exact cited restricted-source set. Never
    accept this set from public forms, HTTP payloads or agent tool arguments.
    """
    case=lock_case(actor,case_id,'document.draft',expected)
    template=Template.objects.filter(case=case,pk=template_id).first()
    if not template or audience not in AUDIENCES or not title.strip() or len(title)>240:
        raise ValidationError('A case template, supported audience and document title are required')
    if template.definition['document_type']=='accepted_finance_metadata':raise ValidationError('Use native accepted Finance metadata preparation')
    from .template_current import selection, scope_for
    if template_scope_id is not None:
        from .template_access import require_scope
        require_scope(actor,scope_for(case,template_scope_id))
    template_manifest = selection(case,template,audience,template_scope_id) if template_scope_id is not None else {}
    validate({'type':'object','maxProperties':16,'properties':{key:{'type':'object','properties':{
        'text':{'type':'string','maxLength':12000},'evidence_ids':{'type':'array','uniqueItems':True,'maxItems':20,'items':{'type':'integer','minimum':1}}},
        'required':['text','evidence_ids'],'additionalProperties':False} for key in FIELDS},'additionalProperties':False},fields)
    source_ids=sorted({pk for field in fields.values() for pk in field['evidence_ids']})
    sources=[subject(case,pk) for pk in source_ids]
    if not isinstance(authorized_restricted_source_ids,(list,tuple,set)) or any(type(pk) is not int or pk<1 for pk in authorized_restricted_source_ids) or not set(authorized_restricted_source_ids).issubset(source_ids):
        raise ValidationError('Native restricted sources must be exact cited positive evidence IDs')
    if any(restricted(e) and e.pk not in authorized_restricted_source_ids for e in sources):raise ValidationError('Restricted source evidence requires its authorized domain interface')
    if document_id:
        document=Document.objects.filter(case=case,pk=document_id).first()
        if not document or document.title!=title:
            raise ValidationError('Revision must identify this case document and its existing title')
        number=document.versions.count()+1
    else:
        document=Document.objects.create(case=case,title=title,owner=actor)
        number=1
    payload=project_payload(title,template.definition,audience,fields)
    version=Version.objects.create(document=document,number=number,template=template,audience=audience,fields=fields,
        source_manifest=[{'id':e.pk,'version':e.version,'sha256':e.sha256} for e in sources],baseline_manifest={} if audience=='group' else baseline_manifest(case),
        payload=payload,payload_sha256=digest(payload),created_by=actor,template_current_manifest=template_manifest)
    for task in HumanTask.objects.filter(version__document=document,status='open'):
        task.status='obsolete';task.save(update_fields=['status'])
        TaskEvent.objects.create(task=task,actor=actor,action='obsolete',data={'replacement':version.pk})
    document.current=version;document.save(update_fields=['current'])
    event(actor,case,'document.drafted',document=document.pk,version=version.pk,number=number,audience=audience,sha256=version.payload_sha256)
    bump(case)
    return version


def preflight(version):
    from .template_current import findings as template_findings
    findings=template_findings(version)
    from apps.finance.documents import binding_for
    finance_binding=binding_for(version)
    if version.template.definition['document_type'] in ['finance_report','finance_group_report'] and not finance_binding:findings.append('Finance report requires an exact source-bound Finance output review')
    if finance_binding:
        from apps.finance.documents import binding_findings as finance_findings
        findings.extend(finance_findings(finance_binding))
    from apps.pmo.models import RFPDocumentBinding
    rfp_binding=RFPDocumentBinding.objects.filter(version=version).first()
    if version.template.definition['document_type']=='rfp_response' and not rfp_binding:
        findings.append('Client RFP response requires a source-bound reviewed RFP proposal')
    if rfp_binding:
        from apps.pmo.rfp_documents import binding_findings as rfp_findings
        findings.extend(rfp_findings(rfp_binding))
    from apps.pmo.models import EmergencyDocumentBinding
    emergency_binding=EmergencyDocumentBinding.objects.filter(version=version).select_related('outcome__profile__version__change__case').first()
    if emergency_binding:
        from apps.pmo.emergency_documents import binding_findings as emergency_findings
        findings.extend(emergency_findings(emergency_binding))
    from apps.pmo.models import EscalationDocumentBinding
    escalation_binding=EscalationDocumentBinding.objects.filter(version=version).select_related('request__profile__state__issue__case').first()
    if escalation_binding:
        from apps.pmo.escalations import binding_findings
        findings.extend(binding_findings(escalation_binding))
    from apps.pmo.models import ChangeDocumentBinding
    change_binding=ChangeDocumentBinding.objects.filter(version=version).select_related('authorization__version__change__case').first()
    if change_binding:
        from apps.pmo.change_execution import change_binding_findings
        findings.extend(change_binding_findings(change_binding))
    from apps.pmo.models import CommercialDocumentBinding
    commercial_binding=CommercialDocumentBinding.objects.filter(version=version).select_related('revision__dossier__case').first()
    if version.audience=='client' and version.template.definition['document_type']=='sow' and not commercial_binding:
        findings.append('Client SOW publication requires an approved source-bound commercial proposal')
    if commercial_binding:
        from apps.pmo.commercial import binding_findings
        findings.extend(binding_findings(commercial_binding))
    if not Document.objects.filter(pk=version.document_id,current_id=version.pk).exists():
        findings.append('A newer document revision is current')
    if version.baseline_manifest!=({} if version.audience=='group' else baseline_manifest(version.document.case)):
        findings.append('PMO baseline changed; prepare and review a new document revision')
    from apps.pmo.models import GateDocumentBinding
    binding=GateDocumentBinding.objects.filter(version=version).select_related('candidate').first()
    if binding:
        from apps.pmo.gates import gate_manifest
        if binding.manifest!=gate_manifest(binding.candidate):
            findings.append('Candidate gate evidence changed; draft and review a new packet')
    from apps.pmo.models import MinutesReportBinding
    reporting_binding=MinutesReportBinding.objects.filter(version=version).select_related('meeting','report__case').first()
    if reporting_binding:
        from apps.pmo.reporting import binding_manifest
        if reporting_binding.manifest!=binding_manifest(reporting_binding):
            findings.append('Meeting/action/report source snapshot changed; draft and review a new revision')
    from apps.pmo.models import DeliveryDocumentBinding
    delivery_binding=DeliveryDocumentBinding.objects.filter(version=version).select_related('dossier__case').first()
    if delivery_binding:
        from apps.pmo.delivery_documents import binding_findings
        findings.extend(binding_findings(delivery_binding))
    definition=version.template.definition
    from .contracts import client_pmo_sections
    mandatory = client_pmo_sections(definition, version.audience, version.document.case)
    projected = {section['heading']: section for section in version.payload.get('sections', [])}
    for key in mandatory:
        if key not in definition['audience_fields'].get(version.audience, []) or not projected.get(key, {}).get('text', '').strip():
            findings.append('Missing mandatory client PMO projection section: ' + key)
    for key in set(definition['required_fields']) | set(mandatory):
        field=version.fields.get(key)
        if not field or not field['text'].strip():
            findings.append('Missing required section: '+key)
    for key,field in version.fields.items():
        if field['text'].strip() and not field['evidence_ids']:
            findings.append('Section has no source evidence: '+key)
    if digest(version.payload)!=version.payload_sha256:
        findings.append('Projection hash mismatch')
    return findings


def current_version(case,version_id):
    version=Version.objects.select_related('document__case','template').filter(document__case=case,pk=version_id).first()
    if not version:
        raise ValidationError('Document version is outside this case')
    if version.template.definition['document_type']=='accepted_finance_metadata':raise PermissionDenied('Use the source-authorised metadata interface')
    findings=preflight(version)
    if findings:
        raise ValidationError(findings)
    return version


@transaction.atomic
def request_review(actor,case_id,version_id,expected):
    case=lock_case(actor,case_id,'document.request_review',expected)
    version=current_version(case,version_id)
    from apps.pmo.leadership_reporting import binding_access
    binding_access(actor,version)
    if version.template.definition['document_type'] in ['finance_report','finance_group_report']:raise ValidationError('Finance reports use configured Finance output review; no PMO Lead task is required')
    if HumanTask.objects.filter(version=version).exists():
        raise ValidationError('Review was already requested; returned/rejected content needs a new version')
    from apps.pmo.leadership_reporting import review_context
    role,pins=review_context(version)
    if role is None:raise ValidationError('Internal Tuesday reporting has no separate report approval')
    task=HumanTask.objects.create(case=case,version=version,created_by=actor,required_role=role)
    TaskEvent.objects.create(task=task,actor=actor,action='requested',data={'sha256':version.payload_sha256})
    event(actor,case,'document.review_requested',task=task.pk,version=version.pk)
    bump(case)
    return task


@transaction.atomic
def review_version(actor,case_id,version_id,verdict,note,expected,delegated=False):
    case=lock_case(actor,case_id,'document.review_controlled',expected)
    if verdict not in ['approve','return','reject'] or not note.strip() or len(note)>4000:
        raise ValidationError('Choose a review decision and provide a concise rationale')
    version=current_version(case,version_id)
    from apps.pmo.leadership_reporting import binding_access
    binding_access(actor,version)
    if version.audience=='group':raise ValidationError('Use the exact native group disclosure review')
    task=HumanTask.objects.select_for_update().filter(case=case,version=version,status='open').first()
    if not task:
        raise ValidationError('This version has no open human review task')
    from apps.pmo.leadership_reporting import review_context
    role,pins=review_context(version)
    if role is None or task.required_role!=role:raise ValidationError('Current configured leadership role differs from the requested review')
    authority=dict(decision_authority(actor,case,role,verdict,delegated),**pins)
    review=ControlledReview.objects.create(version=version,actor=actor,verdict=verdict,note=note,authority=authority,
        delegated=delegated,payload_sha256=version.payload_sha256)
    task.status={'approve':'completed','return':'returned','reject':'rejected'}[verdict];task.save(update_fields=['status'])
    TaskEvent.objects.create(task=task,actor=actor,action=verdict,data={'review':review.pk,'authority':authority})
    event(actor,case,'document.controlled_review',review=review.pk,version=version.pk,verdict=verdict,authority=authority)
    bump(case)
    return review


@transaction.atomic
def withdraw_review(actor,case_id,version_id,note,expected):
    case=lock_case(actor,case_id,'document.withdraw',expected)
    version=current_version(case,version_id)
    from apps.pmo.leadership_reporting import binding_access
    binding_access(actor,version)
    task=HumanTask.objects.select_for_update().filter(case=case,version=version,status='open').first()
    if not task or not note.strip():
        raise ValidationError('An open task and withdrawal reason are required')
    authority=decision_authority(actor,case,'PM','withdraw')
    task.status='withdrawn';task.save(update_fields=['status'])
    TaskEvent.objects.create(task=task,actor=actor,action='withdraw',data={'reason':note[:4000],'authority':authority})
    event(actor,case,'document.review_withdrawn',version=version.pk,task=task.pk)
    bump(case)


def publication_requirements(case,version):
    configs=require_operation('document.publish',case)
    by_id={c.component:c.configuration for c in configs}
    storage=reference_values(by_id['D11.template_storage_retention_rules'])[0]
    if version.template_id not in storage['template_ids']:
        raise ValidationError('Selected template version is not enabled by current document policy')
    recipients=sorted({r['user_id'] for r in reference_values(by_id['D11.recipient_grant_refs']) if r['audience']==version.audience})
    if not recipients:
        raise ValidationError('No configured recipients for the intended audience')
    from django.contrib.auth import get_user_model
    for recipient in get_user_model().objects.filter(pk__in=recipients):
        require(recipient,case,'document.receive:'+version.audience)
    if get_user_model().objects.filter(pk__in=recipients,is_active=True).count()!=len(recipients):
        raise ValidationError('A selected recipient is inactive')
    policies={c.component:c.configuration.pk for c in configs}
    from apps.pmo.models import EscalationDocumentBinding
    binding=EscalationDocumentBinding.objects.filter(version=version).select_related('request').first()
    if binding:
        from apps.pmo.escalations import recipient_requirements
        policies.update(recipient_requirements(binding,case,recipients))
    from apps.pmo.models import RFPDocumentBinding
    rfp_binding=RFPDocumentBinding.objects.filter(version=version).first()
    if rfp_binding:
        from apps.pmo.rfp_documents import recipient_requirements
        policies.update(recipient_requirements(rfp_binding,recipients))
    from apps.finance.documents import binding_for
    finance_binding=binding_for(version)
    if finance_binding:
        from apps.finance.documents import publication_requirements as finance_requirements
        policies.update(finance_requirements(finance_binding,recipients))
    from apps.pmo.leadership_reporting import recipient_access
    policies.update(recipient_access(version,recipients))
    return policies,recipients,storage['retention_days']


def validate_review(case,version):
    if version.audience=='group':
        from apps.finance.group_forecast import approved
        return approved(version)
    from apps.pmo.leadership_reporting import review_context
    role,pins=review_context(version)
    if role is None:return None
    review=version.reviews.order_by('-pk').first()
    if not review and version.audience!='client' and version.template.definition.get('internal_review_required') is False:
        return None
    if not review or review.verdict!='approve' or review.payload_sha256!=version.payload_sha256:
        raise ValidationError('A PMO Lead approval of this exact outward projection is required')
    require(review.actor,case,'document.review_controlled')
    if dict(decision_authority(review.actor,case,role,'approve',review.delegated),**pins)!=review.authority:
        raise ValidationError('Review authority changed; create a fresh version and review')
    return review


def guard_reserve_publication(actor,case,version_id):
    require(actor,case,'document.publish')
    version=current_version(case,version_id)
    from apps.pmo.leadership_reporting import binding_access
    binding_access(actor,version)
    from apps.pmo.rfp_documents import sender,dispatch_requirements
    sender(actor,version)
    dispatch_requirements(version)
    from apps.finance.documents import sender as finance_sender
    finance_sender(actor,version)
    review=validate_review(case,version)
    policies,recipients,retention=publication_requirements(case,version)
    if Publication.objects.filter(version=version).exists():
        raise ValidationError('Publication already reserved for this exact version; inspect its delivery status')
    return version,{'policies':policies,'review_authority':review.authority if review else {},
        'review':review.pk if review else None,'recipients':recipients,'retention_days':retention,
        'version':version.pk,'payload_sha256':version.payload_sha256},None


@transaction.atomic
def reserve_publication(actor,case_id,version_id,expected,factory_work_id=None):
    case=lock_case(actor,case_id,'document.publish',expected)
    version,context,_=guard_reserve_publication(actor,case,version_id)
    scope={}
    if factory_work_id is not None:
        from apps.workflows.factory_publications import publication_scope
        scope=publication_scope(actor,case,version,factory_work_id)
    review=ControlledReview.objects.get(pk=context['review']) if context['review'] else None
    policies,recipients,retention=context['policies'],context['recipients'],context['retention_days']
    publication=Publication.objects.create(version=version,review=review,actor=actor,policies=policies,recipient_ids=recipients,
          retention_days=retention,operation_key=f'document:{version.document_id}:v{version.number}:{version.audience}:v1',**scope)
    PublicationJob.objects.create(publication=publication)
    event(actor,case,'document.publication_reserved',publication=publication.pk,version=version.pk,policies=policies,sha256=version.payload_sha256)
    bump(case)
    return publication
