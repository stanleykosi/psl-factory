"""Human identity findings. No case merge, permission copy or financial transfer."""
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,connection
from django.contrib.auth import get_user_model
from apps.core.models import Case
from apps.core.services import event,bump
from apps.identity.models import Grant
from apps.identity.services import require
from apps.documents.contracts import validate
from adapters.forecast import KEY
from apps.policy.services import active_component,reference_values,decision_authority
from apps.policy.identity_resolution_validators import COMPONENT
from . import engagement as e
from .identity_resolution_models import ProjectIdentityDecision as Decision

FLAGS={'access_transferred':False,'business_records_transferred':False,'financial_authority':False}

def readable(a,c):
    if not get_user_model().objects.filter(pk=a.pk,is_active=True).exists():raise PermissionDenied('Current active identity reader required')
    require(a,c,'case.read');require(a,c,'engagement.read')

def authority(a,c,role):
    readable(a,c);require(a,c,'engagement.resolve_identity')
    cfg=active_component(COMPONENT,c);v=reference_values(cfg)[0]
    if role not in v['resolution_roles']:raise PermissionDenied('Configured current PMO identity role required')
    return cfg,v,decision_authority(a,c,role)

def pin(a,c,other,role):
    cfg,v,source=authority(a,c,role);target,tv,destination=authority(a,other,role)
    return {'source_policy':cfg.pk,'target_policy':target.pk,'source_authority':source,'target_authority':destination,
        'source_capture':e.current_capture(c).pk,'target_capture':e.current_capture(other).pk,'role':role,**FLAGS},min(v['max_decisions'],tv['max_decisions'])

def graph(tenant,limit):
    rows=list(Decision.objects.filter(case__tenant=tenant).order_by('-pk')[:limit+1])
    if len(rows)>limit:raise ValidationError('Identity graph exceeds configured inspection budget')
    latest={}
    for r in rows:latest.setdefault((r.case_id,r.other_case_id),r)
    edges={}
    for r in latest.values():
        if r.relation=='alias':
            if r.case_id in edges and edges[r.case_id]!=r.other_case_id:raise ValidationError('Existing ambiguous aliases need explicit source-owner resolution')
            edges[r.case_id]=r.other_case_id
    return edges

@transaction.atomic
def resolve(a,case_id,other_case_id,relation,role,evidence_id,other_evidence_id,reason,key):
    c=Case.objects.get(pk=case_id);readable(a,c)
    other=Case.objects.get(pk=other_case_id);readable(a,other)
    if c.pk==other.pk or c.kind!='project' or other.kind!='project' or c.tenant!=other.tenant or c.synthetic!=other.synthetic:raise ValidationError('Distinct authorized projects in one tenant/classification required')
    # All identity decisions for this tenant serialize before ordered case/user
    # locks, so two connections cannot introduce opposite aliases concurrently.
    with connection.cursor() as cursor:cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',['psl.project-identity:'+c.tenant])
    list(Case.objects.select_for_update().filter(pk__in=[c.pk,other.pk]).order_by('pk'))
    list(get_user_model().objects.select_for_update().order_by('pk'))
    list(Grant.objects.select_for_update().filter(case_id__in=[c.pk,other.pk]).order_by('pk'))
    a.refresh_from_db();validate(KEY,key)
    if relation not in ['alias','distinct','unresolved'] or not isinstance(reason,str) or not 1<=len(reason)<=1000 or not reason.strip():raise ValidationError('Explicit human relation and bounded rationale required')
    evidence=e.proof(c,evidence_id);other_evidence=e.proof(other,other_evidence_id)
    values,limit=pin(a,c,other,role);values['reason']=reason
    old=Decision.objects.filter(case=c,operation_key=key).first()
    if old:
        if old.other_case_id!=other.pk or old.relation!=relation or old.data!=values or old.evidence_id!=evidence.pk or old.other_evidence_id!=other_evidence.pk or old.actor_id!=a.pk:raise ValidationError('Identity decision key binds other immutable evidence')
        return old
    if relation=='alias':
        edges=graph(c.tenant,limit)
        if c.pk in edges and edges[c.pk]!=other.pk:raise ValidationError('Explicitly retire the prior alias before selecting another target')
        node=other.pk;seen={c.pk}
        while node in edges:
            if node in seen:raise ValidationError('Alias would form an identity cycle')
            seen.add(node);node=edges[node]
        if node in seen:raise ValidationError('Alias would form an identity cycle')
    r=Decision.objects.create(case=c,other_case=other,relation=relation,operation_key=key,data=values,evidence=evidence,other_evidence=other_evidence,actor=a)
    event(a,c,'engagement.identity_resolution',decision=r.pk,relation=relation,**FLAGS);bump(c)
    event(a,other,'engagement.identity_resolution_reference',decision=r.pk,relation=relation,**FLAGS);bump(other)
    return r

def current(r):
    fresh,_=pin(r.actor,r.case,r.other_case,r.data['role']);fresh['reason']=r.data['reason']
    return fresh==r.data and not Decision.objects.filter(case=r.case,other_case=r.other_case,pk__gt=r.pk).exists()

@transaction.atomic
def report(a,case_id):
    c=Case.objects.get(pk=case_id);readable(a,c);rows=[]
    for r in Decision.objects.filter(case=c).select_related('case','other_case','actor').order_by('-pk')[:100]:
        try:readable(a,r.other_case)
        except PermissionDenied:
            rows.append({'id':r.pk,'status':'other_case_access_held'});continue
        accepted=False
        try:accepted=current(r)
        except (ValidationError,PermissionDenied,get_user_model().DoesNotExist):pass
        rows.append({'id':r.pk,'status':'current' if accepted else 'held_or_superseded','other_case_id':str(r.other_case_id),'relation':r.relation,'currently_accepted':accepted,'evidence_id':r.evidence_id,'other_evidence_id':r.other_evidence_id,**FLAGS})
    return {'decisions':rows,'effect_tools':[],**FLAGS}
