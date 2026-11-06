"""P56 received evidence -> bounded A01 -> PM classification -> native change.

Existing immutable Evidence/Audit/AgentRun records own source and attempt history.
The only new relation binds one confirmed intake to one native change version.
Local extraction is bounded and runs under the case lock: no external effects,
provider egress, second queue, business decisions or implementation permissions.
"""
import hashlib,json,re
from datetime import date
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.utils import timezone
from apps.core.models import Audit,Evidence
from apps.core.services import lock_case,add_evidence,event,bump
from apps.identity.services import require
from apps.policy.services import role_policy
from apps.documents.contracts import digest
from apps.agents.models import AgentRun
from apps.agents.change_intake import validate_result,LIMITS
from apps.pmo.models import ChangeRequest,ChangeVersion
from .models import ChangeIntakeConfirmation

RECEIVED='factory.change_request_received'
EXTRACTED='factory.change_request_extracted'
ATTEMPT='factory.change_request_attempt'
CANCELLED='factory.change_request_cancelled'
KIND='agent_private_change_request'
MAX_ATTEMPTS=5
MAX_SOURCE_HISTORY=100

def readable(actor,case):
    from apps.core.workbench import active
    active(actor)
    for action in ['case.read','change.read','factory.read']:require(actor,case,action)

def receipt_for(actor,case,pk):
    readable(actor,case)
    row=Audit.objects.filter(case=case,pk=pk,action=RECEIVED).first()
    if not row:raise ValidationError('Exact same-project change intake receipt required')
    source(row)
    return row

def source(receipt,*,reserve_successor=False):
    original=None;expected_root=None;case_id=receipt.case_id
    # A bounded immutable chain, not current authority for its historical author.
    for depth in range(MAX_SOURCE_HISTORY-int(reserve_successor)):
        d=receipt.data
        if receipt.action!=RECEIVED or not isinstance(d,dict) or set(d)!={'schema','key','request_hash','source','sha256','predecessor','root','reason'} or d['schema']!='p56-change-intake/v1':
            raise ValidationError('Closed authenticated P56 receipt schema required')
        if not isinstance(d['key'],str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}',d['key']) or not isinstance(d['reason'],str) or len(d['reason'])>2000:
            raise ValidationError('Typed P56 receipt identity and correction reason required')
        if type(d['source']) is not int or d['source']<1 or any(v is not None and (type(v) is not int or v<1) for v in [d['predecessor'],d['root']]):
            raise ValidationError('Exact integer P56 source and predecessor identities required')
        e=Evidence.objects.filter(case_id=case_id,pk=d['source'],kind=KIND).first()
        if not e or e.created_by_id!=receipt.actor_id or e.sha256!=d['sha256'] or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():
            raise ValidationError('Exact immutable received change source and author required')
        if d['request_hash']!=digest({'body':e.body,'origin':e.source,'predecessor':d['predecessor'],'reason':d['reason']}):
            raise ValidationError('Received request hash does not match its retained source')
        if original is None:original=e
        if d['predecessor'] is None:
            if d['root'] is not None or expected_root is not None and expected_root!=receipt.pk:
                raise ValidationError('Exact original intake root required')
            return original
        if d['root'] is None or d['predecessor']>=receipt.pk or d['root']>d['predecessor'] or not d['reason'].strip():
            raise ValidationError('Exact earlier source-correction lineage required')
        if expected_root is None:expected_root=d['root']
        if d['root']!=expected_root:raise ValidationError('Source correction changed the original intake root')
        receipt=Audit.objects.filter(case_id=case_id,action=RECEIVED,pk=d['predecessor']).first()
        if receipt is None:raise ValidationError('Same-project intake predecessor required')
    raise ValidationError('Intake history exceeds the bounded source review budget')

def root(receipt):return receipt.data.get('root') or receipt.pk

def current(receipt):
    if Audit.objects.filter(case=receipt.case,action=RECEIVED,data__predecessor=receipt.pk).exists():
        raise ValidationError('Intake source was replaced; inspect its recorded successor')
    if Audit.objects.filter(case=receipt.case,action=CANCELLED,data__receipt=receipt.pk).exists():
        raise ValidationError('This intake was stopped; it cannot create a change')

def latest_extraction(receipt):
    a=Audit.objects.filter(case=receipt.case,action=EXTRACTED,data__receipt=receipt.pk).order_by('-pk').first()
    return AgentRun.objects.filter(pk=a.data['run'],case=receipt.case,evidence_id=receipt.data['source'],process_id='P56').first() if a else None

@transaction.atomic
def receive(actor,case_id,key,body,origin,expected,predecessor=None,reason=''):
    case=lock_case(actor,case_id,'factory.start');readable(actor,case);require(actor,case,'evidence.add')
    if case.kind!='project' or not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}',key):raise ValidationError('Project and bounded submission identity required')
    if not isinstance(body,str) or not body.strip() or len(body)>16000 or not isinstance(origin,str) or not origin.strip() or len(origin)>500:raise ValidationError('Request content and source description are required within the intake budget')
    if predecessor is not None and (type(predecessor) is not int or predecessor<1):raise ValidationError('Exact predecessor required')
    if not isinstance(reason,str) or len(reason)>2000:raise ValidationError('Bounded source-correction reason required')
    request_hash=digest({'body':body,'origin':origin,'predecessor':predecessor,'reason':reason})
    old=Audit.objects.filter(case=case,action=RECEIVED,data__key=key).first()
    if old:
        if old.actor_id!=actor.pk or old.data['request_hash']!=request_hash:raise ValidationError('IDEMPOTENCY_CONFLICT: changed intake submission')
        return old
    if type(expected) is not int or case.revision!=expected:raise ValidationError('STALE_VERSION: refresh this project before intake')
    parent=None
    if predecessor is not None:
        parent=receipt_for(actor,case,predecessor);current(parent)
        if ChangeIntakeConfirmation.objects.filter(receipt=parent).exists():raise ValidationError('Confirmed change needs an explicit native revision, not intake replacement')
        require(actor,case,'factory.manage')
        if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the corrected source')
        previous=source(parent,reserve_successor=True)
        if previous.body==body and previous.source==origin:raise ValidationError('Supply a genuine source correction')
    e=add_evidence(actor,case.pk,KIND,body,origin)
    row=event(actor,case,RECEIVED,schema='p56-change-intake/v1',key=key,request_hash=request_hash,source=e.pk,sha256=e.sha256,
        predecessor=parent.pk if parent else None,root=root(parent) if parent else None,reason=reason)
    case.refresh_from_db();bump(case);return row

@transaction.atomic
def extract_once(actor,case_id,receipt_id,expected,provider=None):
    case=lock_case(actor,case_id,'agent.extract');receipt=receipt_for(actor,case,receipt_id);require(actor,case,'factory.execute');current(receipt)
    if ChangeIntakeConfirmation.objects.filter(receipt=receipt).exists():raise ValidationError('The PM has already classified this intake')
    prior=latest_extraction(receipt)
    if prior:return prior
    if type(expected) is not int or case.revision!=expected:raise ValidationError('STALE_VERSION: refresh before extraction')
    if not case.synthetic:raise ValidationError('No approved operational P56 extraction provider is connected; PM field capture remains available')
    if Audit.objects.filter(case=case,action=ATTEMPT,data__root=root(receipt)).count()>=MAX_ATTEMPTS:raise ValidationError('Local extraction attempt budget exhausted; PM can record the fields directly')
    e=source(receipt)
    from adapters.change_intake import SyntheticChangeIntakeProvider
    provider=provider or SyntheticChangeIntakeProvider()
    if not isinstance(provider.name,str) or not provider.name or len(provider.name)>100:raise ValidationError('Bounded provider identity required')
    attempt=event(actor,case,ATTEMPT,receipt=receipt.pk,root=root(receipt),source=e.pk,sha256=e.sha256,provider=provider.name)
    try:
        result=validate_result(e,provider.extract(e.body))
    except (ValidationError,ValueError,TypeError,KeyError,AttributeError,TimeoutError,ConnectionError) as exc:
        # Only a fixed safe diagnostic is stored, never arbitrary provider exception text.
        event(actor,case,'factory.change_request_extraction_failed',receipt=receipt.pk,attempt=attempt.pk,
            finding='Local extraction failed validation or was unavailable; correct the source or record the fields as PM')
        bump(case);return None
    result.update(schema='p56-extraction/v1',source={'id':e.pk,'version':e.version,'sha256':e.sha256},
        classification_recorded=False,implementation_authorized=False,synthetic=True)
    run=AgentRun.objects.create(case=case,actor=actor,evidence=e,provider=provider.name,process_id='P56',result=result)
    event(actor,case,EXTRACTED,receipt=receipt.pk,attempt=attempt.pk,run=run.pk);bump(case);return run

FIELDS=set(LIMITS)|{'category','category_basis','incident_id','template_id','predecessor_version_id'}
def validate_fields(case,fields):
    if not isinstance(fields,dict) or set(fields)!=FIELDS:raise ValidationError('Exact confirmed P56 field set required')
    for name,limit in dict(LIMITS,category_basis=2000).items():
        if not isinstance(fields[name],str) or not fields[name].strip() or len(fields[name])>limit:raise ValidationError('Supply '+name.replace('_',' ')+' within its field limit')
    try:
        raised=date.fromisoformat(fields['date_raised'])
        if raised.isoformat()!=fields['date_raised'] or raised>timezone.localdate():raise ValueError()
    except (ValueError,TypeError):raise ValidationError('Actual date raised must be YYYY-MM-DD and not in the future') from None
    if fields['category'] not in ['Normal','Standard','Emergency']:raise ValidationError('PM must select Standard, Normal or Emergency')
    for name in ['incident_id','template_id','predecessor_version_id']:
        if fields[name] is not None and (type(fields[name]) is not int or fields[name]<1):raise ValidationError('Exact source identities required')
    if fields['incident_id'] is not None and not Evidence.objects.filter(case=case,pk=fields['incident_id'],kind='incident').exists():raise ValidationError('Choose this project incident evidence')
    if fields['category']=='Emergency' and fields['incident_id'] is None:raise ValidationError('Emergency classification requires incident evidence')
    from apps.documents.models import Template
    if fields['template_id'] is not None and not Template.objects.filter(case=case,pk=fields['template_id'],definition__document_type__in=['status_report','project_artifact']).exists():raise ValidationError('Choose this project controlled template')

@transaction.atomic
def confirm(actor,case_id,receipt_id,extraction_id,fields,note,expected):
    case=lock_case(actor,case_id,'change.manage');receipt=receipt_for(actor,case,receipt_id)
    for action in ['factory.start','evidence.add']:require(actor,case,action)
    authority=role_policy(actor,case,'PM')  # Identity check, not classification approval.
    validate_fields(case,fields)
    if not isinstance(note,str) or not note.strip() or len(note)>2000:raise ValidationError('Explain the PM field confirmation or corrections')
    if extraction_id is not None and (type(extraction_id) is not int or extraction_id<1):raise ValidationError('Exact extraction identity required')
    payload={'fields':fields,'note':note,'extraction_id':extraction_id};sha=digest(payload)
    old=ChangeIntakeConfirmation.objects.filter(receipt=receipt).first()
    if old:
        if old.actor_id!=actor.pk or old.sha256!=sha:raise ValidationError('IDEMPOTENCY_CONFLICT: changed PM confirmation')
        return old
    current(receipt)
    if type(expected) is not int or case.revision!=expected:raise ValidationError('STALE_VERSION: refresh the intake and project before classification')
    run=latest_extraction(receipt)
    if extraction_id!=(run.pk if run else None):raise ValidationError('Select the exact retained extraction or explicit manual capture')
    e=source(receipt)
    existing=ChangeRequest.objects.select_for_update().filter(case=case,reference=fields['reference']).first()
    predecessor=fields['predecessor_version_id']
    if (existing is None and predecessor is not None) or (existing is not None and (predecessor is None or existing.current_id!=predecessor)):
        raise ValidationError('Existing CR reference requires its exact current native revision; do not merge requests silently')
    from apps.pmo.changes import log_change
    native_source=add_evidence(actor,case.pk,'change_request',json.dumps({'schema':'p56-confirmed-request/v1','intake':receipt.pk,
        'source_id':e.pk,'source_sha256':e.sha256,'fields':fields,'confirmation':payload,'confirmation_sha256':sha,'classification_by':'PM'},sort_keys=True),'psl:p56-confirmed-request/v1')
    case.refresh_from_db()
    version=log_change(actor,case.pk,fields['reference'],fields['category'],fields['module'],fields['description'],fields['reason'],native_source.pk,case.revision,fields['incident_id'])
    work=None
    if fields['category']!='Emergency':
        from .factory_change import start
        case.refresh_from_db()
        # A genuine revision retains the existing factory business identity and
        # requires its explicit source-correction command, never a second work.
        from .models import FactoryWork
        prior=FactoryWork.objects.filter(case=case,definition='pmo-change/v1',request__change=version.change_id).first()
        if prior is None:work=start(actor,case.pk,'p56:'+str(receipt.pk),version.pk,{'template_id':fields['template_id'],'authorization_id':None},fields['description'][:160],case.revision)
    result=ChangeIntakeConfirmation.objects.create(receipt=receipt,extraction=run,version=version,work=work,payload=payload,sha256=sha,
        authority={'D05.role_principal_assignments':authority.pk},actor=actor)
    event(actor,case,'factory.change_request_classified',receipt=receipt.pk,confirmation=result.pk,change_version=version.pk,
        work=work.pk if work else None,classification_approval_required=False,implementation_authorized=False)
    case.refresh_from_db();bump(case);return result

@transaction.atomic
def cancel(actor,case_id,receipt_id,expected,reason):
    case=lock_case(actor,case_id,'factory.manage');receipt=receipt_for(actor,case,receipt_id)
    if Audit.objects.filter(case=case,action=CANCELLED,data__receipt=receipt.pk).exists():return receipt
    current(receipt)
    if ChangeIntakeConfirmation.objects.filter(receipt=receipt).exists():raise ValidationError('Classification already recorded; use native change follow-up')
    if type(expected) is not int or case.revision!=expected:raise ValidationError('STALE_VERSION: refresh before stopping intake')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain stopped intake')
    event(actor,case,CANCELLED,receipt=receipt.pk,reason=reason);bump(case);return receipt

def projection(actor,receipt):
    readable(actor,receipt.case);e=source(receipt);run=latest_extraction(receipt)
    binding=ChangeIntakeConfirmation.objects.filter(receipt=receipt).select_related('version__change','work').first()
    status='Await PM classification';active=True
    try:current(receipt)
    except ValidationError as exc:status='; '.join(exc.messages);active=False
    if binding:status='PM classification recorded';active=False
    can_confirm=False;can_extract=False;can_manage=False
    try:
        for key in ['change.manage','factory.start','evidence.add']:require(actor,receipt.case,key)
        role_policy(actor,receipt.case,'PM');can_confirm=active
    except (PermissionDenied,ValidationError):pass
    try:
        for key in ['agent.extract','factory.execute']:require(actor,receipt.case,key)
        can_extract=active and not run and receipt.case.synthetic and Audit.objects.filter(case=receipt.case,action=ATTEMPT,data__root=root(receipt)).count()<MAX_ATTEMPTS
    except PermissionDenied:pass
    try:require(actor,receipt.case,'factory.manage');can_manage=active
    except PermissionDenied:pass
    history=Audit.objects.filter(case=receipt.case,action__startswith='factory.change_request_',data__receipt=receipt.pk).order_by('pk')
    successor=Audit.objects.filter(case=receipt.case,action=RECEIVED,data__predecessor=receipt.pk).first()
    from .models import FactoryWork
    followup_work=FactoryWork.objects.filter(case=receipt.case,definition='pmo-change/v1',request__change=binding.version.change_id).first() if binding and not binding.work_id and binding.version.category!='Emergency' else None
    followup_blocker=bool(followup_work and (followup_work.cancel_requested or followup_work.status in ['cancelled','followup_needed']))
    return {'receipt':receipt,'source':e,'run':run,'binding':binding,'status':status,'can_confirm':can_confirm,'can_extract':can_extract,
        'can_manage':can_manage,'history':list(history),'successor':successor,'followup_work':followup_work,'followup_blocker':followup_blocker,'attempts':Audit.objects.filter(case=receipt.case,action=ATTEMPT,data__root=root(receipt)).count()}

def pending_intakes(actor):
    """Bounded authorized metadata for the primary intake queue, no source bodies."""
    from apps.core.workbench import granted,active
    from django.db.models import Exists,OuterRef,Func,JSONField
    active(actor)
    as_json=Func(OuterRef('pk'),function='to_jsonb',output_field=JSONField())
    cases=granted(actor,['change.read','factory.read']).filter(kind='project')
    successors=Audit.objects.filter(case_id=OuterRef('case_id'),action=RECEIVED,data__predecessor=as_json)
    stopped=Audit.objects.filter(case_id=OuterRef('case_id'),action=CANCELLED,data__receipt=as_json)
    return list(Audit.objects.filter(case_id__in=cases,action=RECEIVED,change_confirmation__isnull=True)
        .annotate(has_successor=Exists(successors),stopped=Exists(stopped)).filter(has_successor=False,stopped=False)
        .select_related('case').order_by('-pk')[:20])
