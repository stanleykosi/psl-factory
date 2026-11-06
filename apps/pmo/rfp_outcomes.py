"""Historical submitted evidence and explicit owner selection; never a new win approval."""
import json
import hashlib
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Evidence
from apps.documents.contracts import digest
from apps.documents.controlled import project_payload
from apps.documents.models import Publication,PublicationReceipt
from apps.policy.services import resolve,reference_values
from apps.policy.rfp_outcome_validators import COMPONENT,METHOD
from .models import (RFPCase,RFPSubmission,RFPDocumentBinding,RFPReview,RFPContribution,
    RFPOutcome,CommercialDecision)
from .services import subject

SCHEMA='rfp-outcome-selection/v1'
HISTORY_LIMIT=100


def exact_ids(values,count,label):
    if not isinstance(values,list) or len(values)!=count or any(type(pk) is not int or pk<1 for pk in values) or len(set(values))!=count:
        raise ValidationError('Exact historical '+label+' references required')
    return values


def historical_submission(case,submission):
    try:return _historical_submission(case,submission)
    except (KeyError,TypeError,ValueError,AttributeError):
        raise ValidationError('Complete exact historical RFP submission evidence required') from None


def _historical_submission(case,submission):
    """Verify immutable facts at submission, independently of today's draft and former grants."""
    if not isinstance(submission,RFPSubmission) or submission.pk is None:
        raise ValidationError('Actual recorded RFP submission required')
    actual=RFPSubmission.objects.select_related('response__rfp__case','response__intake','response__assignment',
        'response__commercial__dossier','version__document','version__template').filter(pk=submission.pk,response__rfp__case=case).first()
    immutable=['response_id','version_id','snapshot','receipt_ids','submitted_at','late']
    if not actual or any(getattr(actual,key)!=getattr(submission,key) for key in immutable):
        raise ValidationError('Exact recorded historical submission manifest required')
    submission=actual;response=submission.response;version=submission.version;snapshot=submission.snapshot
    binding=RFPDocumentBinding.objects.filter(response=response,version=version).first()
    keys={'response','sources','reviews','costing_decisions','route_config','route','deadline_status','deadline_at'}
    if not binding or not isinstance(snapshot,dict) or set(snapshot)!=keys or binding.snapshot!=snapshot or snapshot['response']!=response.pk or snapshot['sources']!=response.snapshot:
        raise ValidationError('Exact historical response document binding and source manifest required')
    if version.document.case_id!=case.pk or version.template.case_id!=case.pk or response.commercial.dossier.case_id!=case.pk or response.evidence.case_id!=case.pk:
        raise ValidationError('Same-workspace historical RFP sources required')
    if version.audience!='client' or version.template.definition.get('internal_review_required',True) is not True:
        raise ValidationError('Historical client response and final review required')
    publication=Publication.objects.select_related('review').filter(version=version).first()
    if not publication or not publication.review_id or publication.review.version_id!=version.pk or publication.review.verdict!='approve' or publication.review.payload_sha256!=version.payload_sha256 or publication.review.created_at>publication.created_at:
        raise ValidationError('Exact historical final client-document approval required')
    if version.payload_sha256!=digest(version.payload) or version.payload!=project_payload(version.payload['title'],version.template.definition,version.audience,version.fields):
        raise ValidationError('Historical outward payload and projection hash differ')
    source_ids=sorted({pk for field in version.fields.values() for pk in field['evidence_ids']})
    sources=list(Evidence.objects.filter(case=case,pk__in=source_ids).order_by('pk'))
    if len(sources)!=len(source_ids) or version.source_manifest!=[{'id':e.pk,'version':e.version,'sha256':e.sha256} for e in sources]:
        raise ValidationError('Exact historical document source evidence required')
    source=response.snapshot
    if set(source)!={'intake','assignment','assignment_authority','inputs'} or source['intake']!=response.intake_id or source['assignment']!=response.assignment_id or response.assignment.intake_id!=response.intake_id or response.assignment.pm_id!=response.actor_id or source['assignment_authority']!=response.assignment.authority:
        raise ValidationError('Historical assignment and response intake differ')
    from .rfp import TEAMS,REVIEW_ROLES,public_terms_for
    if set(source['inputs'])!=set(TEAMS):raise ValidationError('Historical RFP team input inventory required')
    for team,item in source['inputs'].items():
        contribution=RFPContribution.objects.select_related('evidence').filter(pk=item['id'],intake_id=response.intake_id,team=team).first()
        if not contribution or item!={'id':contribution.pk,'evidence':contribution.evidence_id,'sha256':contribution.evidence.sha256} or contribution.evidence.case_id!=case.pk or contribution.evidence.kind!=TEAMS[team]:
            raise ValidationError('Exact historical team input evidence required')
    for kind,pk in response.commercial.sources.items():subject(case,pk,kind)
    if response.commercial.sources['engineering_estimate']!=source['inputs']['Engineering']['evidence'] or response.commercial.sources['security_estimate']!=source['inputs']['Security']['evidence']:
        raise ValidationError('Historical commercial estimates differ from reviewed response')
    terms=public_terms_for(response)
    try:draft=json.loads(subject(case,response.commercial.sources['sow'],'sow').body)
    except (ValueError,TypeError):raise ValidationError('Historical response draft provenance required') from None
    if draft.get('rfp_response')!=response.evidence_id or draft.get('body')!=response.evidence.body or draft.get('matrix')!=response.matrix:
        raise ValidationError('Historical response wording or requirement mapping differs')
    required={response.evidence_id,terms.pk,response.commercial.sources['plan'],*(row['evidence_id'] for row in response.matrix)}
    if not required.issubset(set(source_ids)):raise ValidationError('Historical client document lacks reviewed response source references')
    review_ids=exact_ids(snapshot['reviews'],2,'response review')
    for pk,role in zip(review_ids,REVIEW_ROLES):
        review=RFPReview.objects.filter(pk=pk,response=response,role=role,verdict='approve',created_at__lte=publication.created_at).first()
        last=RFPReview.objects.filter(response=response,role=role,created_at__lte=publication.created_at).order_by('-pk').first()
        if not review or not last or last.pk!=pk:raise ValidationError('Exact approved response reviews at submission required')
    if RFPReview.objects.filter(response=response,verdict__in=['return','reject'],created_at__lte=publication.created_at).exists():
        raise ValidationError('Returned response was not an approved historical submission')
    decision_ids=exact_ids(snapshot['costing_decisions'],3,'ordered costing decision')
    if decision_ids!=sorted(decision_ids):raise ValidationError('Historical costing decisions must preserve the prescribed sequence')
    for pk,role in zip(decision_ids,['PM','Head of PMO','CEO']):
        decision=CommercialDecision.objects.filter(pk=pk,revision=response.commercial,role=role,verdict='approve',created_at__lte=publication.created_at).first()
        last=CommercialDecision.objects.filter(revision=response.commercial,role=role,created_at__lte=publication.created_at).order_by('-pk').first()
        if not decision or not last or last.pk!=pk:raise ValidationError('Exact approved commercial decisions at submission required')
    if CommercialDecision.objects.filter(revision=response.commercial,verdict__in=['return','reject','withdraw'],created_at__lte=publication.created_at).exists():
        raise ValidationError('Closed costing proposal was not an approved historical submission')
    route=snapshot['route'];recipients=route.get('recipient_ids',[]) if isinstance(route,dict) else []
    exact_ids(recipients,len(recipients),'recipient')
    receipts=list(PublicationReceipt.objects.filter(publication=publication).order_by('pk'))
    if not recipients or route.get('kind')!='rfp_submission' or sorted(recipients)!=publication.recipient_ids or publication.policies.get('D11.adapter_configuration_refs')!=snapshot['route_config']:
        raise ValidationError('Exact historical submission destination required')
    if not receipts or [r.pk for r in receipts]!=submission.receipt_ids or sorted(r.recipient_id for r in receipts)!=sorted(recipients) or any(r.payload!=version.payload or r.payload_sha256!=version.payload_sha256 for r in receipts):
        raise ValidationError('All exact historical submitted recipient receipts required')
    if submission.submitted_at!=max(r.created_at for r in receipts) or publication.created_at>submission.submitted_at:
        raise ValidationError('Historical submission time must come from actual recipient receipts')
    return response


def submission_metadata(submission):
    return {'id':submission.pk,'response':submission.response_id,'version':submission.version_id,
        'payload_sha256':submission.version.payload_sha256,'manifest_sha256':digest(submission.snapshot),'receipt_ids':submission.receipt_ids}


def stream_metadata(query,category,project):
    """Bound the display prefix while hashing every canonical, newline-framed metadata row."""
    rows=[];count=0;hasher=hashlib.sha256(('rfp-outcome-inventory/v1:'+category+'\n').encode())
    for item in query.iterator(chunk_size=100):
        row=project(item)
        hasher.update(json.dumps(row,sort_keys=True,separators=(',',':')).encode());hasher.update(b'\n')
        if len(rows)<HISTORY_LIMIT:rows.append(row)
        count+=1
    return rows,{'count':count,'visible':len(rows),'sha256':hasher.hexdigest()}


def complete_coverage(inventory):
    return {key:{'count':value['count'],'sha256':value['sha256']} for key,value in inventory['coverage'].items()}


def selection_value(state,submission):
    return {'schema':SCHEMA,'configuration':state['configuration'],'packet':state['packet'],'submission':submission.pk,
        'acknowledged':True,'selected':submission_metadata(submission),'inventory':complete_coverage(state['inventory'])}


def outcome_selection_state(case,exclude_outcome_id=None):
    """Hash actual submitted versions and prior outcome facts, never current case revisions/drafts."""
    root=RFPCase.objects.filter(case=case).first()
    submissions=RFPSubmission.objects.filter(response__rfp=root).select_related('version').only(
        'id','response_id','version_id','snapshot','receipt_ids','version__payload_sha256').order_by('pk') if root else RFPSubmission.objects.none()
    query=RFPOutcome.objects.filter(submission__response__rfp=root).exclude(pk=exclude_outcome_id).only(
        'id','submission_id','result','evidence_id','observed_at','authority').order_by('pk') if root else RFPOutcome.objects.none()
    delivered=RFPDocumentBinding.objects.filter(response__rfp=root,version__rfpsubmission__isnull=True,
        version__publication__publicationreceipt__isnull=False).select_related('version').only(
        'id','response_id','version_id','version__payload_sha256').distinct().order_by('pk') if root else RFPDocumentBinding.objects.none()
    inventory={'coverage':{}}
    inventory['submissions'],inventory['coverage']['submissions']=stream_metadata(submissions,'submissions',submission_metadata)
    inventory['earlier_outcomes'],inventory['coverage']['earlier_outcomes']=stream_metadata(query,'earlier_outcomes',lambda o:{
        'id':o.pk,'submission':o.submission_id,'result':o.result,'evidence':o.evidence_id,
        'observed_at':o.observed_at.isoformat(),'authority_sha256':digest(o.authority)})
    inventory['unrecorded_deliveries'],inventory['coverage']['unrecorded_deliveries']=stream_metadata(delivered,'unrecorded_deliveries',lambda b:{
        'response':b.response_id,'version':b.version_id,'payload_sha256':b.version.payload_sha256,
        'receipt_ids':list(PublicationReceipt.objects.filter(publication__version_id=b.version_id).order_by('pk').values_list('pk',flat=True))})
    required=inventory['coverage']['submissions']['count']>1
    configuration=None;finding=''
    try:
        resolution=resolve(COMPONENT,case)
        if resolution.status=='ACTIVE' and reference_values(resolution.configuration)[0]['method']==METHOD:configuration=resolution.configuration.pk
    except (ValidationError,PermissionDenied,KeyError):pass
    if required and configuration is None:finding='Multiple submitted responses need configured explicit owner selection before conversion; actual outcome evidence can still be recorded.'
    if inventory['coverage']['unrecorded_deliveries']['count']:finding='Record/reconcile original delivered response receipts first; actual outcome evidence can still be recorded.'
    packet=digest({'schema':SCHEMA,'case':str(case.pk),'rfp':root.pk if root else None,'configuration':configuration,'inventory':complete_coverage(inventory)})
    return {'required':required,'packet':packet,'configuration':configuration,'finding':finding,'inventory':inventory}


def selection_authority(case,submission,selection_context):
    if selection_context is None:return None
    state=outcome_selection_state(case)
    if not isinstance(selection_context,dict) or set(selection_context)!={'packet','acknowledged'} or selection_context['acknowledged'] is not True:
        raise ValidationError('Explicit current submitted-response acknowledgement required')
    if not state['required'] or state['configuration'] is None or state['finding']:
        raise ValidationError(state['finding'] or 'Submitted-response selection is not required for this inventory')
    if selection_context['packet']!=state['packet']:raise ValidationError('STALE_VERSION: submitted responses or earlier outcomes changed; review the current inventory')
    return selection_value(state,submission)


def require_current_selection(case,outcome):
    state=outcome_selection_state(case,exclude_outcome_id=outcome.pk)
    if state['finding']:raise ValidationError(state['finding'])
    if not state['required']:return
    if state['configuration'] is None or state['finding']:raise ValidationError(state['finding'])
    expected=selection_value(state,outcome.submission)
    if outcome.authority.get('_selection_context')!=expected:
        raise ValidationError('Record a fresh actual outcome with explicit current submitted-response selection before conversion')
