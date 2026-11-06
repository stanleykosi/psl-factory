"""Explicit technical provisioning. Never appoints a business decision owner."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import event
from apps.identity.models import Grant
from apps.identity.services import require
from apps.documents.contracts import validate
from adapters.forecast import obj,KEY
from .intake_models import TenantAuthority as Authority,CaseIntake as Intake,AccessChange

SCHEMA=obj({'format':{'enum':['psl.tenant-access/v1','psl.tenant-access/v2']},'create_cases':{'type':'boolean'},'manage_access':{'type':'boolean'},
    'kinds':{'type':'array','uniqueItems':True,'maxItems':2,'items':{'enum':['project','support']}},
    'allowed_actions':{'type':'array','uniqueItems':True,'maxItems':1000,'items':{'type':'string','minLength':1,'maxLength':100}},
    'initial_actions':{'type':'array','uniqueItems':True,'maxItems':1000,'items':{'type':'string','minLength':1,'maxLength':100}},
    'classification':{'enum':['synthetic','operational']}})

def source_system(action):
    prefix='approval.source.read:'
    if not isinstance(action,str) or not action.startswith(prefix) or len(action)>100:return None
    value=action[len(prefix):]
    if value!=value.strip():return None
    try:validate(KEY,value)
    except ValidationError:return None
    return value

def checked(v):
    validate(SCHEMA,v)
    from apps.identity.actions import ACTIONS
    initial=set(v['initial_actions']);allowed=set(v['allowed_actions']);fixed=set(ACTIONS)
    if not initial<=allowed or not initial<=fixed:raise ValidationError('Initial actions must be fixed registered actions explicitly delegated')
    if any(action not in fixed and not(v['format']=='psl.tenant-access/v2' and source_system(action)) for action in allowed):raise ValidationError('Only fixed actions or exact v2 approval source-read literals may be delegated; no wildcard')
    if v['create_cases'] and ('case.read' not in v['initial_actions'] or not v['kinds']):raise ValidationError('Case creation requires an explicit kind and initial case.read')

def text(v,maximum):
    if not isinstance(v,str) or not v.strip() or v!=v.strip() or len(v)>maximum:raise ValidationError('Provide bounded nonempty text without surrounding whitespace')

def lock_users(ids):
    list(get_user_model().objects.select_for_update().filter(pk__in=ids).order_by('pk'))

def current(actor,tenant,purpose):
    fresh=get_user_model().objects.get(pk=actor.pk)
    if not fresh.is_active or not actor.is_authenticated:raise PermissionDenied('Active technical principal required')
    cfg=Authority.objects.filter(user=actor,tenant=tenant).order_by('-version').first()
    if not cfg or not cfg.enabled or cfg.expires_at<=timezone.now():raise PermissionDenied('Current explicit tenant authority required')
    checked(cfg.value)
    if not cfg.value[purpose]:raise PermissionDenied('This technical purpose was not delegated')
    return cfg

@transaction.atomic
def provision(actor,subject,tenant,value,expires_at,enabled,reason):
    lock_users([actor.pk,subject.pk]);fresh=get_user_model().objects.get(pk=actor.pk)
    if not fresh.is_active or not fresh.is_superuser:raise PermissionDenied('Current Django superuser required for technical tenant bootstrap')
    text(tenant,100);text(reason,1000);checked(value)
    if not isinstance(enabled,bool) or timezone.is_naive(expires_at) or expires_at<=timezone.now():raise ValidationError('Explicit future validity and enabled flag required')
    subject_query=get_user_model().objects.filter(pk=subject.pk)
    if not subject_query.exists() or enabled and not subject_query.filter(is_active=True).exists():raise ValidationError('Existing subject required; enabling requires an active account')
    old=Authority.objects.filter(user=subject,tenant=tenant).order_by('-version').first()
    return Authority.objects.create(user=subject,tenant=tenant,version=old.version+1 if old else 1,enabled=enabled,value=value,expires_at=expires_at,actor=fresh,reason=reason)

@transaction.atomic
def create_case(actor,tenant,reference,title,kind):
    lock_users([actor.pk]);cfg=current(actor,tenant,'create_cases');validate(KEY,reference);text(title,240)
    if kind not in cfg.value['kinds']:raise PermissionDenied('Case kind not delegated')
    payload={'title':title,'kind':kind,'synthetic':cfg.value['classification']=='synthetic'}
    old=Intake.objects.filter(tenant=tenant,reference=reference).first()
    if old:
        require(actor,old.case,'case.read')
        if old.actor_id!=actor.pk or old.payload!=payload:raise ValidationError('Reference already binds another intake')
        return old.case
    # TenantAuthority locks serialize only this principal. Unique tenant/reference
    # additionally rejects conflicting concurrent intake by another principal.
    c=Case.objects.create(tenant=tenant,**payload)
    Intake.objects.create(case=c,tenant=tenant,reference=reference,authority=cfg,payload=payload,actor=actor)
    for action in cfg.value['initial_actions']:
        Grant.objects.create(case=c,user=actor,action=action)
        AccessChange.objects.create(case=c,subject=actor,action=action,enabled=True,authority=cfg,actor=actor,reason='Explicit initial actions from technical tenant authority')
    event(actor,c,'intake.created',reference=reference,authority=cfg.pk,formal_project_id=None,business_owner_assigned=False)
    return c

@transaction.atomic
def change_access(actor,case_id,subject_id,action,enabled,reason):
    c=Case.objects.select_for_update().get(pk=case_id)
    lock_users([actor.pk,subject_id]);cfg=current(actor,c.tenant,'manage_access')
    require(actor,c,'case.read');text(reason,1000)
    if action not in cfg.value['allowed_actions'] or not isinstance(enabled,bool):raise PermissionDenied('Explicit delegated record action required')
    subject=get_user_model().objects.get(pk=subject_id)
    if enabled and not subject.is_active:raise ValidationError('Granting requires an active account; inactive accounts can still have grants revoked')
    if c.synthetic!=(cfg.value['classification']=='synthetic'):raise PermissionDenied('Exact technical classification required')
    system=source_system(action)
    if enabled and system:
        from apps.policy.services import active_component,reference_values
        from apps.policy.approval_validators import ROUTES
        if c.kind!='project':raise ValidationError('Approval source-read grants require a project case')
        routes=reference_values(active_component(ROUTES,c))[0]['routes']
        if not any(r['system']==system for r in routes):raise ValidationError('Source-read grant requires this exact case configured system route')
    Grant.objects.update_or_create(case=c,user=subject,action=action,defaults={'active':enabled})
    r=AccessChange.objects.create(case=c,subject=subject,action=action,enabled=enabled,authority=cfg,actor=actor,reason=reason)
    event(actor,c,'intake.access_changed',change=r.pk,subject=subject.pk,grant_action=action,enabled=enabled,authority=cfg.pk)
    return r

def options(actor):
    tenants=Authority.objects.filter(user=actor).values_list('tenant',flat=True).distinct();rows=[]
    for tenant in tenants:
        try:rows.append(current(actor,tenant,'create_cases'))
        except PermissionDenied:pass
    return rows

def investigate(actor,case_id):
    c=Case.objects.get(pk=case_id);require(actor,c,'case.read')
    from apps.identity.services import visible_cases
    candidates=list(visible_cases(actor).filter(tenant=c.tenant,title__iexact=c.title).exclude(pk=c.pk).order_by('pk').values_list('pk',flat=True)[:20])
    return {'case_id':str(c.pk),'intake_recorded':Intake.objects.filter(case=c).exists(),
        'possible_duplicate_case_ids':[str(pk) for pk in candidates],
        'formal_project_id':'not_recorded_by_technical_intake','business_authority_granted':False,
        'next_steps':['Capture engagement source evidence and route before planning.','Use configured PMO authority for PM assignment and formal registration.','Planning and costing precede signed SOW.'],
        'effect_tools':[]}
