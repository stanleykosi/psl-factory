"""B02 selected-case summaries from current reviewed Support reports, no source bodies."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from apps.core.models import Case
from apps.core.services import event,bump
from apps.identity.models import Grant
from apps.identity.services import require
from apps.documents.contracts import digest,validate
from adapters.forecast import KEY
from adapters.hrfinance import timestamp
from adapters.support import LocalSupportReportAdapter
from apps.policy.services import active_component,reference_values,decision_authority,resolve
from apps.policy.summary_validators import SCOPE,REVIEW
from . import support as source
from .summary_models import ComplaintSummaryRequest as Request,ComplaintSummaryVersion as Version,ComplaintSummaryReview as Review
FLAGS={'source_bodies_included':False,'financial_execution_authorized':False,'corrective_credit_authorized':False}
REQUEST_EVIDENCE='agent_private_support_summary_request';REVIEW_EVIDENCE='agent_private_support_summary_review'

def access(a,c,purpose='read'):
    source.readable(a,c);require(a,c,'support.summary.'+purpose)
    if c.kind!='support':raise ValidationError('Support summary workspace required')

def cases(a,c,ids):
    if not isinstance(ids,list) or not 1<=len(ids)<=100 or any(not isinstance(pk,str) for pk in ids) or len(set(ids))!=len(ids):raise ValidationError('Select 1–100 distinct explicitly authorized Support case IDs')
    rows=list(Case.objects.filter(pk__in=ids).order_by('pk'))
    if len(rows)!=len(ids):raise PermissionDenied('Exact authorized case selection required')
    for row in rows:
        source.readable(a,row)
        if row.tenant!=c.tenant or row.synthetic!=c.synthetic or row.kind!='support':raise PermissionDenied('Exact same-tenant Support classification required')
    return rows

def locked(a,case_id,purpose,ids):
    c=Case.objects.get(pk=case_id);access(a,c,purpose);selected=cases(a,c,ids)
    list(Case.objects.select_for_update().filter(pk__in=[c.pk]+[r.pk for r in selected]).order_by('pk'))
    list(get_user_model().objects.select_for_update().order_by('pk'))
    list(Grant.objects.select_for_update().filter(case_id__in=[c.pk]+[r.pk for r in selected]).order_by('pk'))
    a.refresh_from_db();access(a,c,purpose);cases(a,c,ids);return c

def proof(c,pk,kind):
    e=c.evidence.filter(pk=pk,kind=kind).first()
    if not e:raise ValidationError('Exact same-workspace private summary evidence required')
    return e

def current_request(r):
    if Request.objects.filter(case=r.case,reference=r.reference,version__gt=r.version).exists():raise ValidationError('Summary selection changed; use its successor request')

@transaction.atomic
def capture(a,case_id,reference,source_case_ids,start,end,membership,audience,evidence_id,key):
    validate(KEY,key);validate(KEY,reference);validate(KEY,audience)
    if not isinstance(source_case_ids,list) or any(not isinstance(pk,str) for pk in source_case_ids):raise ValidationError('Explicit string case IDs required')
    ids=sorted(source_case_ids);c=locked(a,case_id,'capture',ids);e=proof(c,evidence_id,REQUEST_EVIDENCE)
    begin,finish=timestamp(start),timestamp(end)
    if begin>=finish or membership not in ['linked_receipt_half_open_v1','event_activity_half_open_v1']:raise ValidationError('Explicit aware nonempty half-open period and supported membership required')
    payload={'source_case_ids':ids,'start':begin.isoformat(),'end':finish.isoformat(),'membership':membership,'audience':audience}
    old=Request.objects.filter(case=c,operation_key=key).first()
    if old:
        if old.reference!=reference or old.payload!=payload or old.evidence_id!=e.pk or old.actor_id!=a.pk:raise ValidationError('Request key binds another immutable definition')
        return old
    last=Request.objects.filter(case=c,reference=reference).order_by('-version').first()
    r=Request.objects.create(case=c,reference=reference,version=last.version+1 if last else 1,operation_key=key,payload=payload,evidence=e,actor=a)
    event(a,c,'support.summary_request',request=r.pk);bump(c);return r

def compose(a,r):
    current_request(r);access(a,r.case,'prepare');selected=cases(a,r.case,r.payload['source_case_ids'])
    cfg=active_component(SCOPE,r.case);v=reference_values(cfg)[0]
    if len(selected)>v['max_cases'] or r.payload['membership']!=v['membership']:raise ValidationError('Current summary count/membership criteria differ; revise request or criteria')
    start,end=timestamp(r.payload['start']),timestamp(r.payload['end']);pins={};rows=[];omitted=[];excluded=[];refs=0;identities={};uncertainty=[]
    for c in selected:
        latest=source.SupportReport.objects.filter(case=c).order_by('-pk').first();last=source.head(c)
        marker={'report':latest.pk if latest else None,'head':last.pk if last else None,'merge':source.SupportMerge.objects.filter(source=c).values_list('pk',flat=True).first()}
        try:
            if not latest:raise ValidationError('No reviewed report')
            report=LocalSupportReportAdapter().read(a,c.pk,latest.pk);value=report['result'];marker['review']=report['review_id'];marker['sha256']=report['report_sha256']
        except (ValidationError,PermissionDenied,get_user_model().DoesNotExist):
            pins[str(c.pk)]=marker
            if v['missing_source_behavior']=='hold':raise ValidationError('A selected current reviewed case report is unavailable') from None
            omitted.append({'case_id':str(c.pk),'finding':'current_case_report_unavailable','period_membership':'unknown'});continue
        pins[str(c.pk)]=marker;source_refs=value['sources'];refs+=len(source_refs)
        if refs>v['max_references']:raise ValidationError('Summary source-reference inspection budget exceeded')
        if v['membership']=='event_activity_half_open_v1':member=source.SupportEvent.objects.filter(case=c,occurred_at__gte=start,occurred_at__lt=end).exists()
        else:
            receipts=source.SupportIntake.objects.filter(case=c,pk__in=[x['intake_id'] for x in source_refs]).values_list('payload',flat=True)
            member=any(start<=timestamp(x['received_at'])<end for x in receipts)
        if not member:excluded.append({'case_id':str(c.pk),'finding':'outside_requested_period'});continue
        if marker['merge'] and v['merged_case_behavior']=='omit_with_reason':omitted.append({'case_id':str(c.pk),'finding':'merged_case_omitted','canonical_target_disclosed':False});continue
        row={'case_id':str(c.pk),'report_id':latest.pk,'review_id':report['review_id'],'report_sha256':report['report_sha256'],'merged':bool(marker['merge'])}
        fields={'meaning':value['meaning'],'reopened':value['reopened'],'source_references':source_refs,'metrics':value['metrics'],'unlinked_intake_count':value['unlinked_intake_count']}
        row.update({key:fields[key] for key in v['allowed_fields']});rows.append(row)
        identity=source.canonical(c)
        if identity['transaction_ref'] is None:uncertainty.append({'case_ids':[str(c.pk)],'finding':'unknown_transaction_identity'})
        elif not marker['merge']:identities.setdefault(digest(identity),[]).append(str(c.pk))
    uncertainty += [{'case_ids':ids,'finding':'same_supplied_identity_unmerged'} for ids in identities.values() if len(ids)>1]
    result={'format':'psl.complaint-summary/v1','request_id':r.pk,'workspace_case_id':str(r.case_id),'period':{k:r.payload[k] for k in ['start','end','membership']},'audience':r.payload['audience'],
        'status_basis':'current_reviewed_case_snapshot; period selects membership and is not a historical end-of-period status',
        'coverage':'Only the explicitly selected accessible cases and their supplied reviewed references; no exhaustive channel or unselected-case claim',
        'selected_count':len(selected),'included_count':len(rows),'omitted_count':len(omitted),'rows':rows,'omissions':omitted,'outside_period':excluded,'merge_uncertainty':uncertainty,**FLAGS}
    return {'scope_policy':cfg.pk,'sources':pins},result

@transaction.atomic
def prepare(a,case_id,request_id,key):
    r=Request.objects.select_related('case').get(pk=request_id,case_id=case_id);c=locked(a,case_id,'prepare',r.payload['source_case_ids']);validate(KEY,key)
    pin,result=compose(a,r);old=Version.objects.filter(request=r,operation_key=key).first()
    if old:
        if old.pin!=pin or old.result!=result or old.actor_id!=a.pk:raise ValidationError('Draft key binds other source evidence')
        return old
    last=Version.objects.filter(request=r).order_by('-version').first()
    v=Version.objects.create(request=r,version=last.version+1 if last else 1,operation_key=key,pin=pin,result=result,sha256=digest(result),actor=a)
    event(a,c,'support.summary_prepared',version=v.pk);bump(c);return v

def current(v):
    pin,result=compose(v.actor,v.request)
    if pin!=v.pin or result!=v.result or digest(result)!=v.sha256:raise ValidationError('Summary source evidence or scope changed; prepare a successor')
    if Version.objects.filter(request=v.request,version__gt=v.version).exists():raise ValidationError('Use the successor summary version')

def review_controls(a,v):
    c=v.request.case;access(a,c,'review');cfg=active_component(REVIEW,c);rules=reference_values(cfg)[0]
    require(a,c,'support.summary.draft_read')
    if a.pk!=rules['reviewer_id'] or rules['independent_review'] and a.pk==v.actor_id:raise PermissionDenied('Configured current independent human summary reviewer required')
    role=decision_authority(a,c,'Support');cases(a,c,v.request.payload['source_case_ids'])
    audience=next((x for x in rules['audiences'] if x['key']==v.request.payload['audience']),None)
    if not audience:raise ValidationError('Requested summary audience is not configured')
    scope=reference_values(active_component(SCOPE,c))[0]
    if not set(audience['fields'])<=set(scope['allowed_fields']):raise ValidationError('Audience fields exceed the configured composition field set')
    return {'review_policy':cfg.pk,'authority':role,'version_sha256':v.sha256},rules,audience

@transaction.atomic
def review(a,case_id,version_id,verdict,evidence_id,key):
    v=Version.objects.select_related('request__case','actor').get(pk=version_id,request__case_id=case_id);c=locked(a,case_id,'review',v.request.payload['source_case_ids']);validate(KEY,key)
    if verdict not in ['approve','return','withdraw']:raise ValidationError('Explicit human summary review verdict required')
    current(v);pin,_,_=review_controls(a,v);e=proof(c,evidence_id,REVIEW_EVIDENCE)
    old=Review.objects.filter(version=v,operation_key=key).first()
    if old:
        if old.verdict!=verdict or old.pin!=pin or old.actor_id!=a.pk or old.evidence_id!=e.pk:raise ValidationError('Review key binds another immutable verdict')
        return old
    r=Review.objects.create(version=v,verdict=verdict,operation_key=key,pin=pin,evidence=e,actor=a);event(a,c,'support.summary_reviewed',review=r.pk,verdict=verdict);bump(c);return r

@transaction.atomic
def read(a,case_id,version_id,reviewed=False):
    v=Version.objects.select_related('request__case','actor').get(pk=version_id,request__case_id=case_id);locked(a,case_id,'read',v.request.payload['source_case_ids'])
    if not reviewed:require(a,v.request.case,'support.summary.draft_read')
    current(v)
    if not reviewed:
        return {'version':v.pk,'sha256':v.sha256,'result':v.result,'effect_tools':[]}
    r=v.reviews.select_related('actor').order_by('-pk').first()
    if not r or r.verdict!='approve':raise ValidationError('Current approved human summary review required')
    pin,_,audience=review_controls(r.actor,v)
    if pin!=r.pin or a.pk not in audience['recipient_ids']:raise PermissionDenied('Current exact audience and human review required')
    fixed={'case_id','report_id','review_id','report_sha256','merged'}
    result={**v.result,'rows':[{k:x for k,x in row.items() if k in fixed or k in audience['fields']} for row in v.result['rows']]}
    return {'version':v.pk,'review':r.pk,'sha256':digest(result),'result':result,'effect_tools':[]}

def visible_requests(a,c):
    ids=[]
    for r in Request.objects.filter(case=c).order_by('-pk')[:100]:
        try:cases(a,c,r.payload['source_case_ids']);ids.append(r.pk)
        except PermissionDenied:pass
    return Request.objects.filter(pk__in=ids)
