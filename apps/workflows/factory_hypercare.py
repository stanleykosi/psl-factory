"""Observed release/go-live facts to native stability assessment; no deployment or closure."""
from datetime import timedelta
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from apps.core.models import Evidence
from apps.core.services import lock_case,event
from apps.core.evidence_access import public_evidence
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.services import resolve,decision_authority
from apps.documents.contracts import digest
from apps.documents.models import PublicationReceipt
from apps.pmo import delivery,delivery_closure as closure
from apps.pmo.models import DeliveryRecord
from adapters.delivery import LocalDeliveryAdapter
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt
from .factory_delivery import subject,investigation_key

DEFINITION='delivery-hypercare/v1'
TITLES={'release':('Actual release','Record the observed release and its actual source evidence.'),
    'acceptance':('Go-live acceptance','Link the reviewed client report and distinct PM/Client acceptance evidence.'),
    'stability':('Stability observations','Obtain the current Engineering/Infrastructure observations and configured stability criteria.')}

def start(actor,case_id,key,dossier_id,reference,expected=None):
    from .factory_delivery import start as intake
    return intake(actor,case_id,key,dossier_id,reference,expected,envelope=DEFINITION)

def checks(d):
    result={}
    for name,fn in [('release',lambda x:{'outcome_id':delivery.valid_release(x).pk}),
        ('acceptance',lambda x:{'acceptance_id':closure.accepted_go_live(x).pk}),('stability',closure.hypercare_inputs)]:
        title,summary=TITLES[name]
        try:result[name]={'status':'ready','title':title,'inputs':fn(d)}
        except (ValidationError,PermissionDenied) as exc:
            if name=='release' and d.records.filter(kind='release_outcome').exists():
                summary='Review the recorded release exception with its source owner. Prior readiness cannot be supplied retrospectively.'
            result[name]={'status':'held','title':title,'summary':summary,'finding':'; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)}
    return result

def assessed(work):
    pk=Attempt.objects.filter(activity__work=work,phase='observed',result__head=work.source_head_id,result__has_key='hypercare').order_by('-pk').values_list('result__hypercare',flat=True).first()
    return DeliveryRecord.objects.filter(pk=pk,dossier_id=work.request['dossier'],kind='hypercare').first() if pk else None

def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor
    access(actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION);d=subject(work,actor);native=LocalDeliveryAdapter().read_current(d)
    rows=list(public_evidence(Evidence.objects.filter(case=work.case,pk__in=native['source_evidence_ids'])).order_by('pk'))
    latest={work.source_head.kind:work.source_head}
    for e in rows:
        if e.kind not in latest or e.version>latest[e.kind].version:latest[e.kind]=e
    missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    p=resolve('D11.hypercare_criteria_ref',work.case)
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(e.pk,e.sha256) for e in latest.values()],
        'native':native,'checks':checks(d),'criteria':[p.status,p.configuration.pk if p.configuration else None],
        'assessed':assessed(work).pk if assessed(work) else None}
    state['hash']=digest(state);state['work_revision']=work.revision
    return state,latest,missing,stale,[],[]

def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Investigate actual release, acceptance and stability evidence'
    if missing or stale:return [],'Current required source evidence is missing or stale: '+', '.join(missing+stale)
    for name in ['release','acceptance']:
        if state['checks'][name]['status']=='held':return [],state['checks'][name]['summary']
    if state['criteria'][0]!='ACTIVE':return ['ACT10'],'Resolve the current stability rule before qualification'
    if state['checks']['stability']['status']=='held':return [],state['checks']['stability']['summary']
    inputs=state['checks']['stability']['inputs'];row=assessed(work)
    if not row or row.snapshot!=inputs:return ['ACT08'],'Record the native stability assessment from current observations'
    if inputs['qualified'] is not True:return [],'Stability remains unknown or does not meet the configured criteria. Obtain corrected source observations.'
    return ['ACT13'],'Verify the current qualified stability assessment'

def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    case=lock_case(work.execution_actor,work.case_id,'factory.execute');access(work.execution_actor,case,'factory.execute',DEFINITION)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    if case.revision!=work.case.revision:raise ValidationError('STALE_VERSION: stability sources changed before the command')
    d=subject(work,work.execution_actor);kind=choice['activity']
    if kind=='ACT04':return {'head':work.source_head_id,'dossier':d.pk,'checks':{k:v['status'] for k,v in checks(d).items()},'deployment_dispatched':False}
    if kind=='ACT10':
        if resolve('D11.hypercare_criteria_ref',case).status!='ACTIVE':raise ValidationError('configuration_needed: Reviewed stability period, confirmations, metrics and units are not configured')
        return {'head':work.source_head_id,'stability_rule_available':True}
    if kind=='ACT08':
        inputs=closure.hypercare_inputs(d)
        # The exact native observation is the citation, never an invented confirmation.
        source_ids=[pins[0] for pins in inputs['sources'].values()]
        source=d.sources.filter(pk__in=source_ids).order_by('pk').first()
        evidence_id=source.evidence_id if source else delivery.valid_release(d).evidence_id
        old=delivery.latest(d,'hypercare',False)
        if old and old.snapshot==inputs:require(old.actor,case,'delivery.manage');row=old
        else:row=closure.evaluate_hypercare(work.execution_actor,case.pk,d.pk,evidence_id,'Deterministic assessment of exact native source observations; no deployment, payment or closure authority',case.revision)
        return {'head':work.source_head_id,'dossier':d.pk,'hypercare':row.pk,'qualified':row.snapshot['qualified']}
    if kind=='ACT13':result=verify(work,actor=work.execution_actor);work.status='verified';return result
    raise ValidationError('FORBIDDEN: unregistered stability activity')

def verify(work,actor=None):
    d=subject(work,actor);row=assessed(work)
    if not row or row.snapshot!=closure.hypercare_inputs(d) or row.snapshot['qualified'] is not True:raise ValidationError('Current source-bound qualified stability assessment required')
    require(row.actor,work.case,'delivery.manage')
    return {'head':work.source_head_id,'dossier':d.pk,'hypercare':row.pk,'verified':True,'qualified':True,
        'verification_scope':'synthetic_native_hypercare_qualification','deployment_authorized':False,'deployment_dispatched':False,
        'financial_release_granted':False,'closure_approved':False,'external_authenticity_verified':False}

def receipts(d):
    rows=list(PublicationReceipt.objects.filter(publication__version__deliverydocumentbinding__dossier=d,
        publication__version__deliverydocumentbinding__purpose='go_live',publication__version__audience='client',
        publication__version__document__current_id=F('publication__version_id')).select_related('publication__version__deliverydocumentbinding').order_by('pk')[:101])
    if len(rows)>100:raise ValidationError('Narrow the go-live receipt history before acceptance')
    return rows

def projection(actor,work):
    from .factory import access
    access(actor,work.case,envelope=DEFINITION)
    try:d=subject(work,actor,current=False);subject(work,actor);intake_valid=True
    except (ValidationError,PermissionDenied):
        d=delivery.dossier_for(work.case,work.request['dossier'],current=False);intake_valid=False
    observed=checks(d);can_release=can_accept=False;packet=None;current_receipts=[]
    stopped=work.cancel_requested or work.status in ['verified','cancelled','followup_needed']
    if not stopped and not d.records.filter(kind='release_outcome').exists():
        try:require(actor,work.case,'delivery.release_record');can_release=True
        except PermissionDenied:pass
    if not stopped and observed['release']['status']=='ready' and observed['acceptance']['status']=='held':
        try:
            require(actor,work.case,'delivery.manage');authority=decision_authority(actor,work.case,'PM')
            current_receipts=receipts(d)
            from apps.pmo.delivery_documents import binding_findings
            current_receipts=[r for r in current_receipts if not binding_findings(r.publication.version.deliverydocumentbinding)]
            if current_receipts:
                packet=digest({'release':observed['release']['inputs'],'authority':authority,
                    'receipts':[(r.pk,r.publication.version_id,r.payload_sha256,r.publication.version.deliverydocumentbinding.snapshot) for r in current_receipts]})
                can_accept=True
        except (ValidationError,PermissionDenied):pass
    changed=False
    if work.status=='verified':
        try:verify(work,actor=actor)
        except (ValidationError,PermissionDenied):changed=True
    coverage=None
    try:
        current_sources=LocalDeliveryAdapter().read_current(d);public_ids=current_sources['source_evidence_ids'];coverage=current_sources['coverage']
    except (ValidationError,PermissionDenied):public_ids=[]
    from .factory_delivery import reaffirmation,intake_authority
    instruction_packet=None
    try:_,instruction_packet=reaffirmation(actor,work)
    except (ValidationError,PermissionDenied):pass
    author_current=True
    try:intake_authority(work)
    except PermissionDenied:author_current=False
    from apps.pmo.go_live_attestations import declaration_draft
    for receipt in current_receipts:receipt.attestation_draft=declaration_draft(d,receipt,actor)
    return {'dossier':d,'checks':observed,'assessment':assessed(work),'source_coverage':coverage,'intake_valid':intake_valid,'can_record_release':can_release,
        'can_reaffirm':instruction_packet is not None,'intake_authority_current':author_current,
        'can_accept_go_live':can_accept,'acceptance_packet':packet,'go_live_receipts':current_receipts,'readiness_changed':changed,
        'public_sources':list(public_evidence(Evidence.objects.filter(case=work.case,pk__in=public_ids))),
        'decision_evidence':list(public_evidence(Evidence.objects.filter(case=work.case))) if can_release or can_accept else [],
        'readiness_records':list(d.records.filter(kind='release_ready').order_by('-pk')[:100]) if can_release else []}

@transaction.atomic
def observe(actor,work_id,expected,case_expected,kind,data):
    from .factory import access
    work=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,work.case,envelope=DEFINITION)
    if type(case_expected) is not int or case_expected<1:raise ValidationError('Exact rendered project version required')
    case=lock_case(actor,work.case_id,'delivery.read',case_expected);work.case=case
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    if work.revision!=expected or work.cancel_requested:raise ValidationError('STALE_VERSION: refresh current stability work')
    panel=projection(actor,work);d=panel['dossier']
    if kind=='release':
        if not panel['can_record_release']:raise PermissionDenied('Current actual-release recording authority required')
        if not public_evidence(Evidence.objects.filter(case=case,pk=data['evidence'])).exists():raise ValidationError('Available public event evidence required')
        result=delivery.capture_release(actor,case.pk,d.pk,data['readiness'],data['released_at'],data['reference'],data['evidence'],data['note'],case.revision)
    elif kind=='acceptance':
        if not panel['can_accept_go_live'] or data['packet']!=panel['acceptance_packet']:raise ValidationError('STALE_VERSION: exact current go-live receipt and authority required')
        if data['receipt'] not in [r.pk for r in panel['go_live_receipts']]:raise ValidationError('Select an available current go-live receipt')
        result=closure.accept_go_live(actor,case.pk,d.pk,data['receipt'],data['pm_signature'],data['client_signature'],data['note'],case.revision,attestation=data.get('attestation'))
    else:raise ValidationError('Choose an actual event or go-live acceptance observation')
    work.revision+=1
    if work.status not in ['configuration_needed','owner_needed','blocked']:work.status='ready';work.finding=''
    work.save();return result

@transaction.atomic
def reassess(actor,work_id,expected,reason):
    from .factory import access
    work=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,work.case,'factory.manage',DEFINITION)
    if work.revision!=expected or work.status!='verified' or work.cancel_requested:raise ValidationError('STALE_VERSION: select verified stability work')
    if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: current worker owns this work')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the reviewed reassessment in at most2000 characters')
    try:verify(work,actor=actor)
    except (ValidationError,PermissionDenied):pass
    else:raise ValidationError('The exact stability assessment remains current')
    work.status='ready';work.finding='';work.revision+=1;work.save();event(actor,work.case,'factory.reassessment',work=work.pk,reason=reason,spent=work.budget_used);return work

def attempt_projection(attempt):
    allowed={'head','dossier','checks','hypercare','qualified','verified','verification_scope','deployment_authorized','deployment_dispatched','financial_release_granted','closure_approved','external_authenticity_verified','stability_rule_available'}
    return {k:v for k,v in attempt.result.items() if k in allowed}
