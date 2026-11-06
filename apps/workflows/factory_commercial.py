"""Commercial coordination; costing, source owners and controlled documents keep authority."""
from datetime import timedelta
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Evidence
from apps.core.services import lock_case,event
from apps.core.evidence_access import public_evidence
from apps.documents.contracts import digest
from apps.identity.services import require
from apps.identity.models import Grant
from apps.policy.services import decision_authority
from apps.pmo import commercial,costing,commercial_intake as intake
from apps.pmo.models import CommercialCase,CommercialRevision,CommercialDecision,CommercialDocumentBinding
from apps.pmo.costing_models import CostingRun,CostingBinding,CostingRule,CostingOracle
from apps.documents.models import Publication,PublicationJob,PublicationReceipt,ControlledReview,Template
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt,HumanTask

DEFINITION='commercial/v1'
CALC=['plan','engineering_estimate','security_estimate','inputs']

@transaction.atomic
def start(actor,case_id,key,head_id,reference,expected=None):
    from .factory import access
    case=lock_case(actor,case_id,'factory.start',expected);access(actor,case,'factory.start',DEFINITION)
    head=Evidence.objects.filter(case=case,pk=head_id).first();intake.read(actor,case,head)
    if intake.latest(case).pk!=head.pk:raise ValidationError('Current commercial intake required')
    if not isinstance(key,str) or not 1<=len(key)<=100 or not key.isascii() or not isinstance(reference,str) or not reference.strip() or len(reference)>100:raise ValidationError('Bounded work identity and reference required')
    value={'intake':head.pk,'reference':reference};sha=digest(value);business=digest([str(case.pk),DEFINITION,'commercial-sow'])
    old=Work.objects.filter(case=case).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.key==key and old.request_hash!=sha:raise ValidationError('IDEMPOTENCY_CONFLICT: same commercial intent has changed payload or initiator')
        return old
    work=Work.objects.create(case=case,actor=actor,key=key,definition=DEFINITION,request=value,request_hash=sha,business_key=business,source_head=head)
    event(actor,case,'factory.started',work=work.pk,definition=DEFINITION);return work

def observed(work,kind):
    row=Attempt.objects.filter(activity__work=work,activity__kind=kind,phase='observed',result__head=work.source_head_id).order_by('-pk').first()
    return row.result if row else {}

def calculation(work):
    pk=observed(work,'ACT08').get('costing_run')
    return CostingRun.objects.filter(case=work.case,pk=pk).first() if pk else None

def proposal(work):
    pk=Attempt.objects.filter(activity__work=work,phase='observed',result__head=work.source_head_id,result__has_key='commercial_revision').order_by('-pk').values_list('result__commercial_revision',flat=True).first()
    return CommercialRevision.objects.select_related('dossier__case').filter(dossier__case=work.case,pk=pk).first() if pk else None

def document(work):
    revision=proposal(work)
    binding=CommercialDocumentBinding.objects.filter(revision=revision).select_related('version__document').order_by('-pk').first() if revision else None
    return binding.version if binding else None

def rules(work,data):
    config,rule,oracle,value=costing.configured(work.case)
    if data['rule_id'] not in [None,rule.pk] or data['oracle_id'] not in [None,oracle.pk]:raise ValidationError('Intake rule/oracle differs from the active independently reviewed costing contract')
    return config,rule,oracle

def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor
    access(actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION);costing.readable(actor,work.case,True)
    head=intake.latest(work.case);data=intake.read(actor,work.case,head)
    records=list(public_evidence(Evidence.objects.filter(case=work.case,pk__in=[data[k] for k in intake.PUBLIC if data[k] is not None])).order_by('pk'))
    latest={head.kind:head};latest.update({e.kind:e for e in records})
    missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    try:policy,rule,oracle=rules(work,data);model={'status':'configured','policy':policy.pk,'rule':rule.pk,'oracle':oracle.pk}
    except (ValidationError,PermissionDenied) as exc:model={'status':'unconfigured','finding':'; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)}
    revision=proposal(work);version=document(work)
    publications=Publication.objects.filter(version=version) if version else Publication.objects.none()
    jobs=list(PublicationJob.objects.filter(publication__in=publications).order_by('pk'))
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(e.pk,e.sha256) for e in latest.values()],
        'source_head':work.source_head_id,'current_head':head.pk,'intake':data,'model':model,
        'calculation':calculation(work).pk if calculation(work) else None,'commercial_revision':revision.pk if revision else None,
        'commercial_current':CommercialCase.objects.filter(case=work.case).values_list('current_id',flat=True).first(),
        'decisions':list(CommercialDecision.objects.filter(revision=revision).values_list('pk','verdict')) if revision else [],
        'document':version.pk if version else None,'reviews':list(ControlledReview.objects.filter(version=version).values_list('pk','verdict')) if version else [],
        'jobs':[(j.pk,j.status) for j in jobs],'receipts':list(PublicationReceipt.objects.filter(publication__in=publications).values_list('pk','payload_sha256'))}
    state['hash']=digest(state);state['work_revision']=work.revision
    return state,latest,missing,stale,[],jobs

def eligible(work,value,observed_state,latest,missing,stale,tasks,jobs):
    if work.source_head_id!=observed_state['current_head']:
        if any(j.status in ['pending','unknown','leased'] for j in jobs):return [],'Resolve the original document delivery before adopting changed commercial inputs'
        return ['ACT07'],'Link the current commercial inputs without resetting the work allowance'
    key=digest(['ACT04',observed_state['sources'],work.source_head_id])
    if not Activity.objects.filter(work=work,key=key,status='succeeded').exists():return ['ACT04'],'Investigate commercial sources and independent costing evidence'
    if stale:return [],'Required source evidence is stale: '+', '.join(stale)
    data=observed_state['intake']
    needed=[k for k in CALC if data[k] is None]
    if needed:return [],'Costing awaits source information: '+', '.join(needed)
    if observed_state['model']['status']!='configured':return ['ACT10'],'Resolve native rule/oracle confirmation and configuration'
    row=calculation(work)
    if not row:return ['ACT08'],'Calculate through the reviewed native costing rule'
    try:costing.current_run(row,require_known=False)
    except (ValidationError,PermissionDenied):return ['ACT08'],'Recalculate from current reviewed rule/oracle versions'
    if row.result['status']!='known':return [],'Declared costing has unknown or invalid operands; correct the source inputs'
    if any(j.status in ['pending','unknown','leased','held'] for j in jobs):
        publication=Publication.objects.filter(version=document(work)).first()
        if publication:
            if publication.factory_work_id==work.pk:
                pending=next((j for j in jobs if j.status in ['pending','unknown']),None)
                if pending:return ['ACT12' if pending.status=='unknown' else 'ACT11'],'Reconcile original client receipt' if pending.status=='unknown' else 'Deliver the approved client document'
            if len(observed_state['receipts'])==len(publication.recipient_ids):pass
            else:return [],'Resolve the original native document delivery before preparing another outward version'
    needed=[k for k in ['requirements','sow'] if data[k] is None]
    if needed or missing:return [],'Commercial preparation awaits source information: '+', '.join(needed+missing)
    revision=proposal(work)
    if not revision:return ['ACT11'],'Bind native costing and prepare a source-referenced commercial proposal'
    if not CostingBinding.objects.filter(run=row,costing_id=revision.sources['costing']).exists():return ['ACT11'],'Prepare a genuinely revised proposal from the changed native costing contract'
    commercial.current_revision(work.case,revision.pk)
    if commercial.terminal(revision):return [],'Commercial proposal was returned, rejected or withdrawn; record revised intake sources'
    try:commercial.valid_approvals(revision)
    except (ValidationError,PermissionDenied):return [],'Waiting for current commercial costing and document-quality decisions'
    if data['template_id'] is None:return [],'Select a controlled SOW template before preparing the client version'
    version=document(work)
    if not version:return ['ACT09'],'Prepare the exact controlled client SOW and its native review task'
    from apps.documents.controlled import validate_review
    try:validate_review(work.case,version)
    except (ValidationError,PermissionDenied):return [],'Waiting for review of the exact client document version'
    publication=Publication.objects.filter(version=version).first()
    if publication:
        if len(observed_state['receipts'])==len(publication.recipient_ids):return ['ACT13'],'Verify all native recipient receipts and source lineage'
        return [],'The native document delivery remains outstanding; use its controlled publication worker'
    return ['ACT11'],'Reserve the exact reviewed client publication under current execution authority'

def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    case=costing.locked(work.execution_actor,work.case_id,'factory.execute');access(work.execution_actor,case,'factory.execute',DEFINITION)
    if case.revision!=work.case.revision:raise ValidationError('STALE_VERSION: commercial sources changed before the command')
    head=intake.latest(case);data=intake.read(work.execution_actor,case,head);kind=choice['activity']
    if kind=='ACT07':
        if head.version<=work.source_head.version:raise ValidationError('Forward commercial intake successor required')
        previous=work.source_head_id;work.source_head=head
        event(work.execution_actor,case,'factory.source_adopted',work=work.pk,previous=previous,current=head.pk)
        return {'head':head.pk,'previous_head':previous,'budget_reset':False}
    if head.pk!=work.source_head_id:raise ValidationError('Current commercial intake required')
    if kind=='ACT04':return {'head':head.pk,'investigation':{'unknown_sources':[k for k in intake.PUBLIC if data[k] is None],
        'inputs_known':data['inputs'] is not None,'rule_selected':data['rule_id'] is not None,'oracle_selected':data['oracle_id'] is not None,
        'financial_values_disclosed':False,'case_cost_approved':False,'native_workbook_verified':False}}
    if kind=='ACT10':
        try:rules(work,data)
        except (ValidationError,PermissionDenied) as exc:raise ValidationError('owner_needed: Current independent costing rule/oracle confirmation and human policy activation are required') from exc
        return {'head':head.pk,'native_rule_contract_current':True}
    if kind=='ACT08':
        policy,_,_=rules(work,data)
        row=costing.run(work.execution_actor,case.pk,data['plan'],data['engineering_estimate'],data['security_estimate'],data['inputs'],f'factory:{work.pk}:head:{head.pk}:policy:{policy.pk}')
        return {'head':head.pk,'costing_run':row.pk,'cost_policy':policy.pk,'recorded_status':row.result['status'],'native_workbook_verified':False}
    row=calculation(work);revision=proposal(work);version=document(work)
    publication=Publication.objects.filter(version=version).first() if version else None
    original_dispatch=publication and any(j.publication_id==publication.pk and j.status in ['pending','unknown'] for j in jobs)
    current_document=version and row and revision and CostingBinding.objects.filter(run=row,costing_id=revision.sources['costing']).exists()
    # ACT11 also prepares a revised proposal. A historical document must not
    # intercept that command after the native costing contract has changed.
    if kind in ['ACT11','ACT12'] and version and (original_dispatch or current_document):
        if publication:
            pending=next((j for j in jobs if j.publication_id==publication.pk and j.status in ['pending','unknown']),None)
            if not pending or publication.factory_work_id!=work.pk:raise ValidationError('Only the exact bound native publication can be dispatched by this factory work')
            return {'head':head.pk,'publication_job':pending.pk}
        executor=value['executor_id']
        if executor is None:raise ValidationError('owner_needed: Controlled document publisher is not configured')
        from django.contrib.auth import get_user_model
        from apps.documents.controlled import reserve_publication
        publisher=get_user_model().objects.get(pk=executor)
        publication=reserve_publication(publisher,case.pk,version.pk,case.revision,factory_work_id=work.pk)
        return {'head':head.pk,'publication':publication.pk,'publisher':publisher.pk}
    if not row:raise ValidationError('Current native costing calculation required')
    if kind=='ACT11':
        binding=costing.bind(work.execution_actor,case.pk,row.pk)
        current=CommercialCase.objects.filter(case=case).values_list('current_id',flat=True).first()
        previous=proposal(work)
        if current!=data['predecessor_id'] and (not previous or previous.pk!=current):raise ValidationError('Commercial predecessor changed; capture reviewed successor intake')
        sources={key:data[key] for key in intake.PUBLIC};sources['costing']=binding.costing_id
        case.refresh_from_db()
        revision=commercial.propose(work.execution_actor,case.pk,sources,data['context_id'] or data['requirements'],'Source-referenced proposal from declared costing; native human decisions remain required',case.revision)
        return {'head':head.pk,'costing_binding':binding.pk,'commercial_revision':revision.pk,'cost_approved':False}
    revision=proposal(work)
    if not revision:raise ValidationError('Exact native commercial proposal required')
    if kind=='ACT09':
        version=commercial.draft_submission(work.execution_actor,case.pk,revision.pk,data['template_id'],case.revision)
        from apps.documents.controlled import request_review
        case.refresh_from_db();task=request_review(work.execution_actor,case.pk,version.pk,case.revision)
        return {'head':head.pk,'commercial_revision':revision.pk,'document_version':version.pk,'native_review_task':task.pk}
    if kind=='ACT13':
        result=verify(work,actor=work.execution_actor);work.status='verified';return result
    raise ValidationError('FORBIDDEN: unregistered commercial activity')

def verify(work,actor=None):
    data=intake.read(actor or work.actor,work.case,work.source_head)
    if intake.latest(work.case).pk!=work.source_head_id:raise ValidationError('Commercial inputs changed after publication')
    row=calculation(work);revision=proposal(work);version=document(work)
    if not row or not revision or not version:raise ValidationError('Exact costing, proposal and controlled document required')
    costing.current_run(row);commercial.current_revision(work.case,revision.pk);commercial.valid_approvals(revision)
    if any(revision.sources[k]!=data[k] for k in intake.PUBLIC) or row.evidence_id!=data['inputs']:raise ValidationError('Commercial source versions differ from intake')
    costing.verify_costing(Evidence.objects.get(case=work.case,pk=revision.sources['costing']),data['plan'])
    from apps.documents.controlled import current_version,validate_review,publication_requirements
    current_version(work.case,version.pk);review=validate_review(work.case,version)
    publication=Publication.objects.filter(version=version).first()
    if not publication:raise ValidationError('Native publication required')
    policies,recipients,_=publication_requirements(work.case,version)
    if publication.policies!=policies or publication.recipient_ids!=recipients or publication.review_id!=review.pk:raise ValidationError('Publication review, destination or policy changed')
    receipts=list(PublicationReceipt.objects.filter(publication=publication))
    if {r.recipient_id for r in receipts}!=set(recipients) or any(r.payload!=version.payload or r.payload_sha256!=version.payload_sha256 for r in receipts):raise ValidationError('Every exact recipient receipt is required')
    return {'verified':True,'verification_scope':'declared_costing_and_reviewed_commercial_submission','head':work.source_head_id,'costing_run':row.pk,
        'commercial_revision':revision.pk,'document_version':version.pk,'publication':publication.pk,'receipt_ids':[r.pk for r in receipts],
        'native_workbook_verified':False,'signed_baseline_adopted':False,'invoice_created':False,'environment':'synthetic_internal_receipt'}

def publication_scope(actor,case,version,work_id):
    """Current authority for a new dispatch; past receipts are reconciled separately."""
    from .factory import access,profile
    work=Work.objects.select_related('actor','case').filter(pk=work_id,case=case,definition=DEFINITION).first()
    if not work:raise ValidationError('Exact commercial factory work required')
    access(actor,case,'factory.execute',DEFINITION);require(actor,case,'document.publish')
    config,value=profile(work)
    if work.policy_id!=config.pk or value['executor_id']!=actor.pk:raise PermissionDenied('Current exact factory publisher and profile required')
    if work.cancel_requested or work.status in ['verified','cancelled','followup_needed']:raise ValidationError('Commercial factory publication is stopped')
    if not intake.latest(case) or intake.latest(case).pk!=work.source_head_id:raise ValidationError('Commercial intake changed before publication')
    intake.read(work.execution_actor,case,work.source_head)
    expected=document(work)
    if not expected or expected.pk!=version.pk:raise ValidationError('Exact source-bound commercial document required')
    revision=proposal(work);commercial.current_revision(case,revision.pk);commercial.valid_approvals(revision)
    return {'factory_work_id':work.pk,'factory_policy_id':config.pk,'factory_source_id':work.source_head_id}

def projection(actor,work):
    """Public commercial subjects plus optional native private costing readback."""
    from .factory import access
    access(actor,work.case,envelope=DEFINITION)
    revision=proposal(work);version=document(work);row=calculation(work)
    result={'commercial_revision':revision,'client_version':version,'decision_roles':[], 'can_document_review':False,'costing_report':None,'intake_sources':None,'owner_reviews':[]}
    current_head=intake.latest(work.case)
    current=not work.cancel_requested and work.status not in ['verified','cancelled','followup_needed'] and current_head and current_head.pk==work.source_head_id
    try:
        data=intake.read(actor,work.case,work.source_head);result['intake_sources']=data
        if row:result['costing_report']=costing.report(actor,work.case_id,row.pk)
        rule=costing.rule_for(work.case,data['rule_id']) if data['rule_id'] else None
        oracle=costing.oracle_for(rule,data['oracle_id']) if rule and data['oracle_id'] else None
        for target in ([None]+([oracle] if oracle else [])) if rule else []:
            try:
                costing.authority(actor,rule,target)
                try:costing.confirmed(rule,target);continue
                except (ValidationError,PermissionDenied):pass
                if target:costing.confirmed(rule)
                if current:result['owner_reviews'].append({'rule':rule,'oracle':target,'kind':'Independent example set' if target else 'Calculator rule'})
            except (ValidationError,PermissionDenied):pass
    except (ValidationError,PermissionDenied):pass
    if current and revision:
        try:
            commercial.current_revision(work.case,revision.pk);require(actor,work.case,'commercial.decide')
            costing.verify_costing(Evidence.objects.get(case=work.case,pk=revision.sources['costing']),revision.sources['plan'])
            decisions=commercial.latest_decisions(revision)
            for role in commercial.ROLES:
                try:
                    decision_authority(actor,work.case,role)
                    if role!='PMO Lead':commercial.valid_approvals(revision,commercial.ROLES[:commercial.ROLES.index(role)])
                    old=decisions.get(role)
                    if old and old.verdict=='approve':commercial.check_decision(old);continue
                    if not commercial.terminal(revision):result['decision_roles'].append(role)
                except (ValidationError,PermissionDenied):continue
        except (ValidationError,PermissionDenied):pass
    if current and version and HumanTask.objects.filter(case=work.case,version=version,status='open').exists():
        try:require(actor,work.case,'document.review_controlled');decision_authority(actor,work.case,'PMO Lead');result['can_document_review']=True
        except (ValidationError,PermissionDenied):pass
    result['public_sources']=list(public_evidence(Evidence.objects.filter(case=work.case,pk__in=revision.sources.values()))) if revision else []
    result['review_evidence']=Evidence.objects.filter(case=work.case,kind='p14_review') if result['owner_reviews'] else []
    result['jobs']=list(PublicationJob.objects.filter(publication__version=version).order_by('pk')) if version else []
    if work.status=='verified':
        try:verify(work)
        except (ValidationError,PermissionDenied):result['readiness_changed']=True
    return result

@transaction.atomic
def reassess(actor,work_id,expected,reason):
    from .factory import access
    work=Work.objects.select_for_update().select_related('case').get(pk=work_id,definition=DEFINITION)
    access(actor,work.case,'factory.manage',DEFINITION)
    if work.revision!=expected or work.status!='verified' or work.cancel_requested:raise ValidationError('STALE_VERSION: select a previously verified commercial submission')
    if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: current worker owns this work')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the reviewed reassessment in at most2000 characters')
    try:verify(work)
    except (ValidationError,PermissionDenied):pass
    else:raise ValidationError('The exact recorded submission remains current')
    work.status='ready';work.finding='';work.revision+=1;work.save()
    event(actor,work.case,'factory.reassessment',work=work.pk,reason=reason,spent=work.budget_used)
    return work

def reconcile(actor,work_id,expected):
    from .factory import access,cancellation_status
    from apps.documents.delivery import run_publication_once
    with transaction.atomic():
        work=Work.objects.select_for_update().select_related('case').get(pk=work_id,definition=DEFINITION)
        access(actor,work.case,'factory.execute',DEFINITION)
        from .factory_execution import require_control
        require_control(actor,work)
        if not work.case.synthetic:raise ValidationError('Only synthetic factory publication is currently enabled')
        if work.revision!=expected or work.lease_until and work.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh after the current worker stops')
        job=PublicationJob.objects.filter(publication__factory_work=work,status='unknown').order_by('pk').first()
        if not job:raise ValidationError('No exact uncertain factory publication to reconcile')
        event(actor,work.case,'factory.reconciliation_requested',work=work.pk,publication_job=job.pk)
    # Lookup is first. A missing local receipt still reaches the original native scope
    # guard before any send; this command grants no replacement authority.
    run_publication_once(case_id=work.case_id,job_id=job.pk)
    with transaction.atomic():
        work=Work.objects.select_for_update().get(pk=work_id);job.refresh_from_db()
        work.status=cancellation_status(work) if work.cancel_requested else 'waiting_effect' if job.status=='unknown' else 'blocked' if job.status=='held' else 'ready'
        work.finding='Original client delivery remains uncertain' if job.status=='unknown' else job.error if job.status=='held' else ''
        work.observation_hash='';work.revision+=1;work.save()
    return work

@transaction.atomic
def decide(actor,work_id,expected,kind,target,verdict,evidence_id,note):
    from .factory import access
    work=Work.objects.select_for_update().select_related('case').get(pk=work_id,definition=DEFINITION)
    access(actor,work.case,envelope=DEFINITION)
    case=lock_case(actor,work.case_id,'case.read');list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    if work.revision!=expected or work.cancel_requested:raise ValidationError('STALE_VERSION: refresh the exact commercial work')
    panel=projection(actor,work)
    if kind=='commercial':
        if target not in panel['decision_roles'] or not panel['commercial_revision']:raise PermissionDenied('Current native commercial role and exact subject required')
        result=commercial.decide_proposal(actor,case.pk,panel['commercial_revision'].pk,target,verdict,note,case.revision)
    elif kind=='document':
        if not panel['can_document_review'] or str(panel['client_version'].pk)!=str(target):raise PermissionDenied('Current exact controlled document review required')
        from apps.documents.controlled import review_version
        result=review_version(actor,case.pk,panel['client_version'].pk,verdict,note,case.revision)
    elif kind=='costing':
        selected=next((r for r in panel['owner_reviews'] if str(r['oracle'].pk if r['oracle'] else 'rule')==str(target)),None)
        if not selected:raise PermissionDenied('Exact current independent costing evidence owner required')
        result=costing.review(actor,case.pk,selected['rule'].pk,selected['oracle'].pk if selected['oracle'] else None,verdict,
            f'factory:{work.pk}:head:{work.source_head_id}:rev:{work.revision}:review',evidence_id,case.revision)
    else:raise ValidationError('Choose a native decision type')
    work.revision+=1
    if work.status=='waiting':work.status='ready';work.finding=''
    work.save();event(actor,case,'factory.native_decision',work=work.pk,decision=result.pk,kind=kind)
    return result

def attempt_projection(attempt):
    if attempt.phase=='failed':return {'status':'held','next_action':'Review current native costing/commercial source authority'}
    allowed={'head','previous_head','costing_run','cost_policy','recorded_status','costing_binding','commercial_revision','cost_approved','document_version','native_review_task','verified','verification_scope','publication','publication_job','publisher','receipt_ids','native_workbook_verified','signed_baseline_adopted','invoice_created','environment','budget_reset','native_rule_contract_current'}
    return {key:value for key,value in attempt.result.items() if key in allowed}
