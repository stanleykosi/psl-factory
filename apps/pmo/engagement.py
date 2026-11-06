"""Pre-planning P03/P16 evidence; formal identity is separate from a Case UUID."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from apps.core.services import lock_case,event,bump,add_evidence
from apps.core.evidence_access import public_evidence
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.services import active_component,reference_values,decision_authority,resolve
from apps.policy.engagement_validators import ASSIGN,REGISTER
from apps.documents.contracts import validate
from adapters.forecast import KEY
from adapters.project_identity import normalize
from .engagement_models import EngagementRecord as Record,ProjectIdentifier as Identifier

def scope(a,case_id,purpose):
    c=lock_case(a,case_id,'engagement.'+purpose)
    require(a,c,'case.read');require(a,c,'engagement.read')
    if c.kind!='project':raise ValidationError('Project engagement scope required')
    list(get_user_model().objects.select_for_update().order_by('pk'))
    list(Grant.objects.select_for_update().filter(case=c).order_by('pk'))
    a.refresh_from_db();require(a,c,'engagement.'+purpose)
    return c

def proof(c,evidence_id):
    e=public_evidence(c.evidence.all()).filter(pk=evidence_id).first()
    if not e or e.kind not in ['engagement_source','engagement_assignment','engagement_registration','product_input','rfp_outcome','plan']:raise ValidationError('Same-case engagement/assignment/registration source evidence required')
    return e

def latest(c,kind):return Record.objects.filter(case=c,kind=kind).order_by('-pk').first()

def record(a,c,kind,key,data,e):
    validate(KEY,key);old=Record.objects.filter(case=c,operation_key=key).first()
    if old:
        if old.kind!=kind or old.data!=data or old.evidence_id!=e.pk or old.actor_id!=a.pk:raise ValidationError('Operation key binds other immutable engagement evidence')
        return old
    r=Record.objects.create(case=c,kind=kind,operation_key=key,data=data,evidence=e,actor=a)
    event(a,c,'engagement.'+kind,record=r.pk);bump(c);return r

@transaction.atomic
def capture(a,case_id,route,evidence_id,reference,key,rfp_disposition=None):
    c=scope(a,case_id,'capture');e=proof(c,evidence_id);validate(KEY,reference)
    if route not in ['A','B','C']:raise ValidationError('Explicit engagement Route A/B/C required')
    if route=='A':
        from .models import RFPDisposition
        if not RFPDisposition.objects.filter(pk=rfp_disposition,rfp__case=c,kind='route_a').exists():raise ValidationError('Route A requires actual same-case won RFP conversion')
    elif rfp_disposition is not None:raise ValidationError('Only Route A links an RFP disposition')
    if route=='C' and e.kind!='product_input':raise ValidationError('Route C requires Product paper source evidence')
    return record(a,c,'capture',key,{'route':route,'reference':reference,'rfp_disposition':rfp_disposition},e)

def authority(a,c,component,role,purpose):
    cfg=active_component(component,c);v=reference_values(cfg)[0]
    if role not in v[purpose+'_roles']:raise PermissionDenied('Configured source-role ownership required')
    return cfg,v,decision_authority(a,c,role)

def current_capture(c):
    r=latest(c,'capture')
    if not r:raise ValidationError('Capture initial engagement before assignment or registration')
    return r

@transaction.atomic
def assign(a,case_id,pm_id,role,evidence_id,key):
    c=scope(a,case_id,'assign');e=proof(c,evidence_id);capture=current_capture(c)
    cfg,v,owner=authority(a,c,ASSIGN,role,'assignment')
    pm=get_user_model().objects.get(pk=pm_id,is_active=True);require(pm,c,'engagement.read');pm_role=decision_authority(pm,c,'PM')
    return record(a,c,'assignment',key,{'capture':capture.pk,'pm_id':pm.pk,'policy':cfg.pk,'role':role,'authority':owner,'pm_authority':pm_role},e)

def current_assignment(c):
    r=latest(c,'assignment');capture=current_capture(c)
    if not r or r.data['capture']!=capture.pk:raise ValidationError('Current engagement PM assignment required')
    require(r.actor,c,'engagement.assign');cfg,v,owner=authority(r.actor,c,ASSIGN,r.data['role'],'assignment')
    pm=get_user_model().objects.get(pk=r.data['pm_id'],is_active=True);require(pm,c,'engagement.read')
    if cfg.pk!=r.data['policy'] or owner!=r.data['authority'] or decision_authority(pm,c,'PM')!=r.data['pm_authority']:raise ValidationError('Assignment authority changed; record fresh source evidence')
    return r

@transaction.atomic
def register(a,case_id,value,role,evidence_id,plan_id,key):
    c=scope(a,case_id,'register');e=proof(c,evidence_id);assignment=current_assignment(c)
    plan=public_evidence(c.evidence.all()).filter(pk=plan_id,kind='plan').first()
    if plan is None:raise ValidationError('Planning evidence required for formal project registration; signature is not required')
    cfg,v,owner=authority(a,c,REGISTER,role,'registration');normalized=normalize(value,v)
    contract={k:v[k] for k in ['format','case_sensitive','max_length']}
    namespace=Identifier.objects.filter(tenant=c.tenant,namespace=v['namespace']).first()
    if namespace and namespace.rules!=contract:raise ValidationError('Namespace normalization contract conflicts with existing identity history; use a reviewed namespace version')
    old=Identifier.objects.filter(tenant=c.tenant,namespace=v['namespace'],normalized=normalized).first()
    if old and old.case_id!=c.pk:raise ValidationError('Identifier already belongs to another case; resolve the identity conflict explicitly')
    data={'capture':current_capture(c).pk,'assignment':assignment.pk,'namespace':v['namespace'],'value':value,'normalized':normalized,'plan':plan.pk,'plan_sha256':plan.sha256,'policy':cfg.pk,'role':role,'authority':owner,'previous_registration':latest(c,'registration').pk if latest(c,'registration') else None}
    prior=Record.objects.filter(case=c,operation_key=key,kind='registration').first()
    if prior:data['previous_registration']=prior.data['previous_registration']
    r=record(a,c,'registration',key,data,e)
    if old is None:Identifier.objects.create(case=c,tenant=c.tenant,namespace=v['namespace'],value=value,normalized=normalized,rules=contract,record=r)
    return r

def current_registration(c):
    r=latest(c,'registration');assignment=current_assignment(c)
    if not r or r.data['assignment']!=assignment.pk:raise ValidationError('Current assignment and registration required')
    require(r.actor,c,'engagement.register');cfg,v,owner=authority(r.actor,c,REGISTER,r.data['role'],'registration')
    if cfg.pk!=r.data['policy'] or owner!=r.data['authority']:raise ValidationError('Registration authority changed; reaffirm source registration')
    return r

@transaction.atomic
def export_registration(a,case_id,key):
    import json
    c=scope(a,case_id,'export');r=current_registration(c);validate(KEY,key)
    old=Record.objects.filter(case=c,operation_key=key).first()
    if old:
        if old.kind!='export' or old.data['registration']!=r.pk or old.actor_id!=a.pk:raise ValidationError('Export key binds another registration')
        return old.evidence
    e=add_evidence(a,c.pk,'engagement_registration',json.dumps({'format':'psl.project-registration/v1','case_id':str(c.pk),'registration':r.pk,**r.data},sort_keys=True),'psl:engagement-registration')
    record(a,c,'export',key,{'registration':r.pk},e);return e

@transaction.atomic
def link_delivery(a,case_id,dossier_id,key):
    from .delivery import capture_source
    from apps.documents.contracts import digest
    c=scope(a,case_id,'export');r=current_registration(c);validate(KEY,key)
    old=Record.objects.filter(case=c,operation_key=key).first()
    if old:
        if old.kind!='delivery_link' or old.actor_id!=a.pk or old.data['registration']!=r.pk or old.data['dossier']!=dossier_id:raise ValidationError('Delivery link key binds other registration evidence')
        return old
    e=export_registration(a,c.pk,'registration-'+digest(key));c.refresh_from_db()
    source=capture_source(a,c.pk,dossier_id,'registration',r.data['namespace']+':'+r.data['value'],e.pk,{},c.revision)
    return record(a,c,'delivery_link',key,{'registration':r.pk,'dossier':dossier_id,'source':source.pk},e)

@transaction.atomic
def report(a,case_id):
    from .identity_resolution import report as identity_report
    c=scope(a,case_id,'read');r=latest(c,'registration');assignment_status='missing';registration_status='missing'
    try:current_assignment(c);assignment_status='current'
    except (ValidationError,PermissionDenied,get_user_model().DoesNotExist):assignment_status='held_or_stale'
    try:current_registration(c);registration_status='current'
    except (ValidationError,PermissionDenied,get_user_model().DoesNotExist):registration_status='held_or_stale'
    return {'case_id':str(c.pk),'capture':latest(c,'capture').pk if latest(c,'capture') else None,'assignment_status':assignment_status,
        'assignment_policy':resolve(ASSIGN,c).status,'registration_policy':resolve(REGISTER,c).status,'registration_status':registration_status,
        'historical_registration':r.data if r else None,'identifier_history':list(Identifier.objects.filter(case=c).values('namespace','value')),
        'next_steps':['Preserve route provenance and investigate possible duplicate identities.','Record PM assignment with current source-role authority.','Register a source identifier during Planning; prior aliases remain immutable.'],
        'identity_resolution':identity_report(a,c.pk),'effect_tools':[]}
