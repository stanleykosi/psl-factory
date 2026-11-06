"""RFP production coordination; native reviews, customer outcomes and receipts own truth."""
import json
from datetime import timedelta
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Evidence
from apps.core.evidence_access import public_evidence
from apps.core.services import lock_case,add_evidence,event
from apps.identity.services import require
from apps.identity.models import Grant
from apps.documents.contracts import digest
from apps.documents.models import Publication,PublicationJob,PublicationReceipt
from apps.documents.controlled import current_version,validate_review,reserve_publication,request_review,guard_reserve_publication
from apps.pmo import rfp,rfp_documents,commercial
from apps.pmo.models import RFPCase,RFPResponse,RFPDocumentBinding,RFPSubmission,RFPOutcome,RFPDisposition
from adapters.factory_rfp import NativeRFPAdapter
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt,HumanTask

DEFINITION='rfp-response/v1'
FIELDS={'response_evidence','public_terms','sources','matrix','lessons'}

def subject(work):
    root=RFPCase.objects.filter(case=work.case,pk=work.request['rfp']).select_related('current_intake').first()
    if not root:raise ValidationError('Exact native RFP workspace required')
    return root

def validate_payload(case,payload,received_id=None):
    if not isinstance(payload,dict) or set(payload)!=FIELDS:raise ValidationError('Closed RFP source selection required')
    if not isinstance(payload['sources'],dict) or set(payload['sources'])!={'requirements','plan','costing'}:raise ValidationError('Declare requirements, plan and costing sources')
    selected={'response_evidence':('rfp_response',payload['response_evidence']),'public_terms':('rfp_commercial_terms',payload['public_terms']),
        'lessons':('rfp_lessons',payload['lessons']),**{k:(k,v) for k,v in payload['sources'].items()}}
    for _,(kind,pk) in selected.items():
        if pk is not None and (type(pk) is not int or pk<1 or not public_evidence(Evidence.objects.filter(case=case,pk=pk,kind=kind)).exists()):
            raise ValidationError('Select exact current workspace public source references')
    matrix=payload['matrix']
    if not isinstance(matrix,list) or len(matrix)>100:raise ValidationError('Declare at most100 requirement mappings')
    seen=set();root=rfp.root(case);received_id=received_id or root.current_intake.evidence_id
    for row in matrix:
        if not isinstance(row,dict) or set(row)!={'key','evidence_id','response','disposition'}:raise ValidationError('Closed requirement mapping required')
        if not isinstance(row['key'],str) or not row['key'].strip() or len(row['key'])>100 or row['key'] in seen:raise ValidationError('Unique bounded requirement names required')
        seen.add(row['key']);rfp.note(row['response'])
        if type(row['evidence_id']) is not int or row['evidence_id'] not in [payload['sources']['requirements'],received_id]:raise ValidationError('Map selected requirements or the exact received RFP instruction')
        if row['disposition'] not in ['addressed','clarification','out_of_scope']:raise ValidationError('Explicit requirement disposition required')
    return json.loads(json.dumps(payload))

def record(actor,case,payload,intake_id=None):
    root=rfp.root(case)
    intake=root.intakes.filter(pk=intake_id).first() if intake_id is not None else root.current_intake
    if not intake:raise ValidationError('Exact received RFP source required')
    value={'schema':'factory-rfp-intake/v1','rfp':root.pk,'intake':intake.pk,**validate_payload(case,payload,intake.evidence_id)}
    head=add_evidence(actor,case.pk,'agent_private_rfp_intake',json.dumps(value,sort_keys=True),'derived:factory-rfp-inputs',case.revision)
    event(actor,case,'factory.rfp_inputs_recorded',evidence_id=head.pk,sha256=head.sha256)
    case.refresh_from_db();return head

def inputs(work):
    head=work.source_head
    if not head or head.case_id!=work.case_id or head.kind!='agent_private_rfp_intake':raise ValidationError('Typed native RFP instruction required')
    try:value=json.loads(head.body)
    except (ValueError,TypeError):raise ValidationError('Typed RFP instruction required') from None
    if set(value)!=FIELDS|{'schema','rfp','intake'} or value['schema']!='factory-rfp-intake/v1' or value['rfp']!=work.request['rfp']:raise ValidationError('Closed same-RFP instruction required')
    if type(value['intake']) is not int or not isinstance(value['sources'],dict) or set(value['sources'])!={'requirements','plan','costing'} or not isinstance(value['matrix'],list) or len(value['matrix'])>100:raise ValidationError('Typed RFP source inventory required')
    if any(pk is not None and (type(pk) is not int or pk<1) for pk in [value['response_evidence'],value['public_terms'],value['lessons'],*value['sources'].values()]):raise ValidationError('Exact RFP evidence references required')
    return value

@transaction.atomic
def start(actor,case_id,key,payload,reference,expected):
    from .factory import access
    if type(expected) is not int or expected<1:raise ValidationError('Exact source revision required')
    case=lock_case(actor,case_id,'factory.start');access(actor,case,'factory.start',DEFINITION);require(actor,case,'evidence.add')
    root=rfp.root(case)
    if not isinstance(key,str) or not 1<=len(key)<=100 or not key.isascii() or not isinstance(reference,str) or not reference.strip() or len(reference)>100:raise ValidationError('Bounded work identity and reference required')
    if not isinstance(payload,dict) or set(payload)!=FIELDS or not isinstance(payload['sources'],dict) or set(payload['sources'])!={'requirements','plan','costing'} or not isinstance(payload['matrix'],list):raise ValidationError('Closed typed RFP source selection required')
    request={'rfp':root.pk,'reference':reference};business=digest([DEFINITION,str(case.pk),root.pk])
    try:request_hash=digest([request,payload])
    except (ValueError,TypeError):raise ValidationError('Typed JSON RFP instruction required') from None
    old=Work.objects.filter(case=case).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.definition!=DEFINITION or old.actor_id!=actor.pk or old.request!=request:raise ValidationError('IDEMPOTENCY_CONFLICT: RFP scope or initiator differs')
        legacy=old.request_hash==digest(request) and {k:inputs(old)[k] for k in FIELDS}==payload
        if old.request_hash!=request_hash and not legacy:raise ValidationError('IDEMPOTENCY_CONFLICT: RFP sources differ')
        return old
    if case.revision!=expected:raise ValidationError('STALE_VERSION: refresh the current RFP intake')
    rfp.ensure_open(root);validate_payload(case,payload)
    head=record(actor,case,payload)
    work=Work.objects.create(case=case,actor=actor,key=key,definition=DEFINITION,request=request,request_hash=request_hash,business_key=business,source_head=head)
    event(actor,case,'factory.started',work=work.pk,definition=DEFINITION);return work

def native_publications(work):
    return Publication.objects.filter(version__rfpdocumentbinding__response__rfp=subject(work))

def pending_jobs(work):return PublicationJob.objects.filter(publication__in=native_publications(work),status__in=['pending','unknown','leased','held'])

def uncaptured(work):
    return native_publications(work).filter(job__status='confirmed',version__rfpsubmission__isnull=True).select_related('version').order_by('pk').first()

@transaction.atomic
def correct(actor,work_id,expected,case_revision,payload,reason):
    from .factory import access
    from apps.agents.factory_coordinator import pending,has_receipt
    if type(work_id) is not int or type(expected) is not int or type(case_revision) is not int:raise ValidationError('Exact work and source revisions required')
    work=Work.objects.select_for_update(of=('self',)).select_related('case','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,work.case,'factory.start',DEFINITION);require(actor,work.case,'factory.manage');rfp.note(reason)
    case=lock_case(actor,work.case_id,'evidence.add',case_revision);work.case=case
    if type(expected) is not int or work.revision!=expected:raise ValidationError('STALE_VERSION: refresh the current work')
    if work.cancel_requested or work.status in ['cancelled','followup_needed','verified']:raise ValidationError('Stopped or verified RFP work needs native follow-up')
    if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: current worker owns this instruction')
    original=pending(work)
    if pending_jobs(work).exists() or uncaptured(work) or original and not has_receipt(original):raise ValidationError('Resolve original effects and submission records before changing the instruction')
    rfp.ensure_open(subject(work));previous=work.source_head_id;old=inputs(work)
    # Loss-lesson follow-up must not rewrite the received source of a delivered bid.
    retained_intake=old['intake'] if submission_for(work) and isinstance(payload,dict) and {k:payload.get(k) for k in FIELDS if k!='lessons'}=={k:old[k] for k in FIELDS if k!='lessons'} else None
    work.source_head=record(actor,case,payload,retained_intake)
    event(actor,case,'factory.rfp_instruction_changed',work=work.pk,previous=previous,current=work.source_head_id,reason=reason)
    work.revision+=1;work.fence+=1;work.status='ready';work.finding='';work.save();return work

def matching_response(row,value):
    if not row or row.evidence_id!=value['response_evidence'] or row.matrix!=value['matrix']:return None
    if any(row.commercial.sources[k]!=pk for k,pk in value['sources'].items()):return None
    try:
        if rfp.public_terms_for(row).pk!=value['public_terms']:return None
    except (ValidationError,PermissionDenied):return None
    return row

def latest_outcome(work):
    return RFPOutcome.objects.filter(submission__response__rfp=subject(work)).select_related('submission__response__commercial','submission__version').order_by('-pk').first()

def response_for(work):
    root=subject(work);value=inputs(work)
    disposition=RFPDisposition.objects.select_related('outcome__submission__response__commercial','outcome__submission__response__rfp').filter(rfp=root).first()
    if disposition:return disposition.outcome.submission.response
    actual=latest_outcome(work)
    if actual and actual.result in ['won','lost']:return actual.submission.response
    row=RFPResponse.objects.select_related('commercial','rfp').filter(pk=root.current_response_id,rfp=root).first()
    if row and row.intake_id==value['intake'] and matching_response(row,value):return row
    for row in RFPResponse.objects.select_related('commercial','rfp').filter(rfp=root,intake_id=value['intake'],submissions__isnull=False).distinct().order_by('-pk')[:100]:
        if matching_response(row,value):return row
    return None

def submission_for(work):
    disposition=RFPDisposition.objects.select_related('outcome__submission__version').filter(rfp=subject(work)).first()
    if disposition:return disposition.outcome.submission
    actual=latest_outcome(work)
    if actual and actual.result in ['won','lost']:return actual.submission
    row=response_for(work)
    return RFPSubmission.objects.filter(response=row).select_related('version').order_by('-pk').first() if row else None

def document_hold(version):
    task=HumanTask.objects.filter(version=version,status__in=['returned','rejected','withdrawn']).order_by('-pk').first()
    if not task:return None
    last=task.events.order_by('-pk').first()
    return last.created_at if last else task.created_at

def usable_document(work,binding):
    if Publication.objects.filter(version=binding.version,job__status='cancelled').exists():return False
    held=document_hold(binding.version)
    if held and work.source_head.created_at>held:return False
    try:current_version(work.case,binding.version_id)
    except (ValidationError,PermissionDenied):return False
    return not rfp_documents.binding_findings(binding)

def document_for(work,value):
    row=response_for(work)
    if not row:return None
    for binding in RFPDocumentBinding.objects.select_related('version__document').filter(response=row,version__template_id=value.get('template_id')).order_by('-pk')[:100]:
        if binding.snapshot['route']['key']!=value.get('route_key'):continue
        if usable_document(work,binding):return binding.version
    return None

def review_document(work):
    """Select native human review without requiring an active agent coordinator."""
    root=subject(work)
    disposition=RFPDisposition.objects.select_related('outcome__submission__version__document').filter(rfp=root).first()
    if disposition:return disposition.outcome.submission.version
    submission=submission_for(work)
    if submission:return submission.version
    if work.policy_id:
        from apps.policy.services import reference_values
        return document_for(work,reference_values(work.policy)[0])
    row=response_for(work)
    if row:
        for binding in RFPDocumentBinding.objects.select_related('version__document').filter(response=row).order_by('-pk')[:100]:
            if usable_document(work,binding):return binding.version
    return None

def document_observed(work,version):
    return Attempt.objects.filter(activity__work=work,activity__kind='ACT09',phase='observed',result__head=work.source_head_id,result__document_version=version.pk).exists()

def investigation_key(work,state):return digest(['rfp_investigation',work.source_head_id,state['sources'],state['native_sources']])

def needs_preparation(work,row):
    if not row:return True
    try:rfp.current_response(work.case,row.pk)
    except (ValidationError,PermissionDenied):return work.source_head.created_at>row.created_at
    return False

def instruction_current(work):
    actions={'factory.start','rfp.read','evidence.add'}
    return work.source_head.created_by.is_active and set(Grant.objects.filter(case=work.case,user_id=work.source_head.created_by_id,active=True,action__in=actions).values_list('action',flat=True))==actions

def snapshot(work,value,reader=None):
    from .factory import access
    access(reader or work.execution_actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION)
    root=subject(work);data=inputs(work)
    submission=submission_for(work);outcome=RFPOutcome.objects.filter(submission=submission).order_by('-pk').first() if submission else None
    ids=[root.current_intake.evidence_id,data['response_evidence'],data['public_terms'],data['lessons'],*data['sources'].values()]
    records=list(public_evidence(Evidence.objects.filter(case=work.case,pk__in=[pk for pk in ids if pk is not None])).order_by('pk'))
    latest={e.kind:e for e in records};latest[work.source_head.kind]=work.source_head
    if submission:
        actual_ids=[entry['id'] for entry in submission.version.source_manifest]
        if outcome:actual_ids.append(outcome.evidence_id)
        latest.update({e.kind:e for e in public_evidence(Evidence.objects.filter(case=work.case,pk__in=actual_ids)).order_by('pk')})
    missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    try:native_sources=rfp.source_snapshot(root);source_finding=''
    except (ValidationError,PermissionDenied) as exc:native_sources=None;source_finding=str(exc)
    response=response_for(work);version=submission.version if submission else document_for(work,value) if not RFPDisposition.objects.filter(rfp=root).exists() else None
    disposition=RFPDisposition.objects.filter(rfp=root).first()
    jobs=list(PublicationJob.objects.filter(Q(publication__factory_work=work)|Q(publication__in=native_publications(work))).select_related('publication__version').order_by('pk'))
    state={'case_revision':work.case.revision,'profile':work.policy_id,'head':work.source_head_id,'instruction_current':instruction_current(work),'sources':[(e.pk,e.sha256) for e in latest.values()],
        'intake':root.current_intake_id,'native_sources':native_sources,'source_finding':source_finding,'response':response.pk if response else None,
        'document':disposition.outcome.submission.version_id if disposition else version.pk if version else None,'submission':submission.pk if submission else None,'outcome':outcome.pk if outcome else None,
        'disposition':disposition.pk if disposition else None,'reviews':list(response.reviews.values_list('pk','verdict')) if response else [],
        'costing_decisions':list(response.commercial.decisions.values_list('pk','verdict')) if response else [],
        'jobs':[(j.pk,j.status,j.fence) for j in jobs],
        'receipts':list(PublicationReceipt.objects.filter(publication__job__in=jobs).values_list('pk','payload_sha256'))}
    state['hash']=digest(state);state['work_revision']=work.revision
    return state,latest,missing,stale,[],jobs

def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    original=next((job for job in jobs if job.publication.factory_work_id==work.pk and job.status in ['unknown','pending','leased','held']),None)
    if original:
        if original.status=='leased' and original.lease_until and original.lease_until<=timezone.now():return ['ACT12'],'Reconcile the expired original response attempt'
        if original.status in ['leased','held']:return [],'Original response delivery needs its native operator'
        return ['ACT12' if original.status=='unknown' else 'ACT11'],'Reconcile the original response receipt' if original.status=='unknown' else 'Deliver the exact reviewed response'
    if uncaptured(work):return ['ACT11'],'Record original delivered response receipts before new work'
    if state['disposition']:return ['ACT13'],'Verify the actual customer outcome and downstream project route'
    if state['submission']:
        outcome=RFPOutcome.objects.filter(pk=state['outcome']).select_related('submission','actor').first()
        if not outcome or outcome.result not in ['won','lost']:return [],'Waiting for an evidenced actual customer outcome'
        if outcome.result=='lost' and inputs(work)['lessons'] is None:return [],'Record source-owned loss lessons before archiving'
        from apps.pmo.rfp_outcomes import historical_submission,require_current_selection
        try:
            historical_submission(work.case,outcome.submission)
            if latest_outcome(work).pk!=outcome.pk:raise ValidationError('Review the latest actual customer outcome')
            require(outcome.actor,work.case,'rfp.outcome')
            if not rfp.outcome_authority_matches(outcome.authority,rfp.authority(outcome.actor,work.case,'outcome',outcome.role)):raise ValidationError('Current outcome authority changed; record a fresh authorised outcome')
            require_current_selection(work.case,outcome)
            require(work.execution_actor,work.case,'rfp.dispose')
        except PermissionDenied:return [],'Review current outcome-owner or processor permissions before the outcome handoff'
        except ValidationError as exc:return [],'; '.join(exc.messages)
        return ['ACT11'],'Record the native project route or loss archive from the actual human outcome'
    if not state['instruction_current']:return [],'A currently authorised source owner must reaffirm the response instruction'
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Investigate the RFP sources and outstanding decisions'
    if any(job.publication.factory_work_id!=work.pk and job.status in ['pending','unknown','leased','held'] for job in jobs):return [],'Resolve the original native response delivery before revising or submitting'
    data=inputs(work)
    if data['intake']!=state['intake']:return [],'Record a fresh source instruction for the revised received RFP'
    if missing or stale:return [],'Required source evidence needs review: '+', '.join(missing+stale)
    if not state['native_sources']:return [],state['source_finding'] or 'Waiting for accountable assignment and team inputs'
    if any(data[k] is None for k in ['response_evidence','public_terms']) or any(v is None for v in data['sources'].values()) or not data['matrix']:return [],'Select the response, public terms, source documents and requirement mappings'
    row=response_for(work)
    if needs_preparation(work,row):return ['ACT09'],'Prepare the source-referenced native RFP response'
    try:rfp.current_response(work.case,row.pk)
    except (ValidationError,PermissionDenied):return [],'Response inputs or authority changed; record a corrected instruction'
    try:rfp.reviewed(row);commercial.valid_approvals(row.commercial,['PM','Head of PMO','CEO'])
    except (ValidationError,PermissionDenied):return [],'Waiting for the prescribed response and commercial decisions'
    if value['template_id'] is None or value['route_key'] is None:return [],'Select the reviewed client response template and submission destination'
    version=document_for(work,value)
    if not version:return ['ACT09'],'Prepare the exact outward response for final human review'
    if document_hold(version):return [],'Final document review returned, rejected or withdrew this version; record a corrected source instruction'
    publication=Publication.objects.filter(version=version).first()
    if not publication and not document_observed(work,version):return ['ACT09'],'Link the exact existing native response document and its review'
    try:validate_review(work.case,version)
    except (ValidationError,PermissionDenied):return [],'Waiting for final review of this exact client response'
    if not publication:
        if value['executor_id'] is None:return [],'Configure the response publisher before submitting the reviewed response'
        from django.contrib.auth import get_user_model
        from .factory import access
        publisher=get_user_model().objects.filter(pk=value['executor_id'],is_active=True).first()
        if not publisher:return [],'Review the current response publisher before submission'
        try:
            access(publisher,work.case,'factory.execute',DEFINITION)
            guard_reserve_publication(publisher,work.case,version.pk)
        except PermissionDenied:return [],'Review current publisher, sender and recipient permissions before submission'
        except ValidationError as exc:return [],'; '.join(exc.messages)
        return ['ACT11'],'Reserve the approved client submission under current publisher authority'
    if publication.job.status!='confirmed':return [],'Resolve the existing native publication before another submission'
    return ['ACT11'],'Record the actual delivered recipient receipts as the native submission'

def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    actor=work.execution_actor;case=lock_case(actor,work.case_id,'factory.execute');access(actor,case,'factory.execute',DEFINITION)
    if case.revision!=work.case.revision:raise ValidationError('STALE_VERSION: RFP changed before the command')
    work.case=case;kind=choice['activity'];adapter=NativeRFPAdapter();data=inputs(work)
    if kind in ['ACT11','ACT12']:
        original=next((j for j in jobs if j.publication.factory_work_id==work.pk and (j.status in ['pending','unknown'] or j.status=='leased' and j.lease_until and j.lease_until<=timezone.now())),None)
        if original:return {'head':work.source_head_id,'publication_job':original.pk,'publication_lookup_only':kind=='ACT12'}
        delivered=uncaptured(work)
        if delivered:
            submission=adapter.capture_submission(work,delivered.version)
            return {'head':work.source_head_id,'submission':submission.pk,'historical_receipts_preserved':True}
    if kind=='ACT13':
        result=verify(work);work.status='verified';return result
    if kind=='ACT11':
        submission=submission_for(work)
        if submission:
            outcome=RFPOutcome.objects.filter(submission=submission).order_by('-pk').first()
            if not outcome:raise ValidationError('Actual human customer outcome required')
            disposition=adapter.dispose(work,outcome,data['lessons'])
            return {'head':work.source_head_id,'disposition':disposition.pk,'baseline_imported':False}
    for permission in ['factory.start','rfp.read','evidence.add']:require(work.source_head.created_by,case,permission)
    if data['intake']!=subject(work).current_intake_id:raise ValidationError('Current received RFP instruction required')
    if kind=='ACT04':return {'head':work.source_head_id,**adapter.investigate(work)}
    row=response_for(work)
    if kind=='ACT09':
        if needs_preparation(work,row):
            row=adapter.prepare(work,data);return {'head':work.source_head_id,'response':row.pk,'approved':False}
        rfp.current_response(case,row.pk)
        version=document_for(work,value)
        if version:
            if document_hold(version):raise ValidationError('A corrected instruction and fresh document version are required')
            try:validate_review(case,version);task=None
            except (ValidationError,PermissionDenied):
                task=HumanTask.objects.filter(case=case,version=version,status='open').first()
                if not task:task=request_review(actor,case.pk,version.pk,case.revision)
            return {'head':work.source_head_id,'document_version':version.pk,'native_review_task':task.pk if task else None,'reused_native_document':True}
        version=adapter.draft(work,row,value);case.refresh_from_db()
        task=request_review(actor,case.pk,version.pk,case.revision)
        return {'head':work.source_head_id,'document_version':version.pk,'native_review_task':task.pk,'approved':False}
    if kind=='ACT11':
        version=document_for(work,value)
        if not version:raise ValidationError('Exact current reviewed client response required')
        publication=Publication.objects.filter(version=version).first()
        if not publication:
            from django.contrib.auth import get_user_model
            if value['executor_id'] is None:raise ValidationError('owner_needed: Response publisher is not configured')
            publisher=get_user_model().objects.get(pk=value['executor_id'],is_active=True)
            publication=reserve_publication(publisher,case.pk,version.pk,case.revision,factory_work_id=work.pk)
            return {'head':work.source_head_id,'publication':publication.pk}
        submission=adapter.capture_submission(work,version)
        return {'head':work.source_head_id,'submission':submission.pk}
    raise PermissionDenied('Unregistered RFP activity')

def verify(work):
    root=subject(work);row=response_for(work);disposition=RFPDisposition.objects.select_related('outcome__submission__version').filter(rfp=root).first()
    if not row or not disposition or disposition.snapshot['response']!=row.pk:raise ValidationError('Exact native RFP disposition and actual submitted response required')
    submission=disposition.outcome.submission;version=submission.version
    if submission.response_id!=row.pk or disposition.snapshot['submission']!=submission.pk or disposition.snapshot.get('baseline_imported') is not False:raise ValidationError('Exact native outcome and fresh project contract boundary required')
    if disposition.snapshot.get('outcome')!=disposition.outcome_id or disposition.snapshot.get('case')!=str(work.case_id) or disposition.snapshot.get('sources')!=row.snapshot or disposition.snapshot.get('commercial_sources')!=row.commercial.sources:raise ValidationError('Exact historical winning or lost response requirements required')
    from apps.pmo.rfp_outcomes import historical_submission
    historical_submission(work.case,submission)
    publication=Publication.objects.filter(version=version).first()
    if not publication or publication.job.status!='confirmed':raise ValidationError('Confirmed exact response publication required')
    receipts=list(PublicationReceipt.objects.filter(publication=publication).order_by('pk'))
    if not receipts or [r.pk for r in receipts]!=submission.receipt_ids or {r.recipient_id for r in receipts}!=set(publication.recipient_ids) or any(r.payload!=version.payload or r.payload_sha256!=version.payload_sha256 for r in receipts):raise ValidationError('All exact native recipient receipts required')
    if disposition.kind not in ['route_a','loss_archive'] or disposition.kind=='loss_archive' and not disposition.lessons_id:raise ValidationError('Actual project route or evidenced loss archive required')
    if disposition.outcome.result!=('won' if disposition.kind=='route_a' else 'lost') or disposition.snapshot.get('route')!=('A' if disposition.kind=='route_a' else None):raise ValidationError('Actual customer outcome and disposition route must agree')
    if disposition.kind=='loss_archive' and disposition.lessons_id!=inputs(work)['lessons']:raise ValidationError('Exact declared loss lessons required')
    if publication.factory_work_id is not None:
        if publication.factory_work_id!=work.pk:raise ValidationError('Another production work owns this response receipt')
        origin=json.loads(publication.factory_source.body)
        if origin.get('rfp')!=root.pk:raise ValidationError('Published response belongs to another RFP instruction scope')
    return {'verified':True,'head':work.source_head_id,'response':row.pk,'document_version':version.pk,'publication':publication.pk,
        'submission':submission.pk,'outcome':disposition.outcome_id,'disposition':disposition.pk,'receipt_ids':[r.pk for r in receipts],
        'kind':disposition.kind,'signed_baseline_imported':False,'verification_scope':'historically_approved_native_submission_current_customer_outcome_and_route'}

def publication_scope(actor,case,version,work_id):
    from .factory import access,profile
    work=Work.objects.select_related('case','actor','source_head').filter(pk=work_id,case=case,definition=DEFINITION).first()
    if not work:raise ValidationError('Exact RFP factory work required')
    access(actor,case,'factory.execute',DEFINITION);require(actor,case,'document.publish');config,value=profile(work)
    if work.policy_id!=config.pk or value['executor_id']!=actor.pk:raise PermissionDenied('Current configured RFP publisher required')
    if work.cancel_requested or work.status in ['verified','cancelled','followup_needed']:raise ValidationError('RFP work is stopped')
    if inputs(work)['intake']!=subject(work).current_intake_id:raise ValidationError('Received RFP instruction changed')
    for permission in ['factory.start','rfp.read','evidence.add']:require(work.source_head.created_by,case,permission)
    exact=document_for(work,value)
    if not exact or exact.pk!=version.pk:raise ValidationError('Exact source-bound RFP response document required')
    rfp_documents.dispatch_requirements(version)
    return {'factory_work_id':work.pk,'factory_policy_id':config.pk,'factory_source_id':work.source_head_id}

def reconcile(actor,work_id,expected):
    from .factory import access,cancellation_status
    from .factory_execution import require_control
    from apps.documents.delivery import run_publication_once
    with transaction.atomic():
        work=Work.objects.select_for_update(of=('self',)).select_related('case','actor').get(pk=work_id,definition=DEFINITION)
        access(actor,work.case,'factory.execute',DEFINITION);require_control(actor,work)
        if work.revision!=expected:raise ValidationError('STALE_VERSION: refresh current work')
        if work.lease_until and work.lease_until>timezone.now():raise ValidationError('Current worker owns this work')
        job=pending_jobs(work).filter(Q(status='unknown')|Q(status='leased',lease_until__lte=timezone.now())).first()
        if not job:raise ValidationError('No uncertain original RFP delivery')
        event(actor,work.case,'factory.reconciliation_requested',work=work.pk,job=job.pk)
    run_publication_once(case_id=work.case_id,job_id=job.pk,lookup_only=True)
    with transaction.atomic():
        work=Work.objects.select_for_update().get(pk=work_id);job.refresh_from_db()
        work.status=cancellation_status(work) if work.cancel_requested else 'waiting_effect' if job.status=='unknown' else 'ready'
        work.finding='Original response receipt is still uncertain' if job.status=='unknown' else '';work.revision+=1;work.save()
    return work
