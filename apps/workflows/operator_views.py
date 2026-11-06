from django import forms
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.http import JsonResponse,Http404,HttpResponse
from django.shortcuts import render,redirect
from apps.core.views import accessible_case
from apps.identity.models import Grant
from apps.identity.services import require
from apps.finance.forms import CommandForm
from apps.policy.services import resolve
from apps.policy.operator_validators import SCHEMAS
from apps.policy.operator_drafts import draft_operator_policy
from apps.agents.operations import investigate
from apps.agents.models import AgentRun
from adapters.operator_protection import encoded
from .operator_recovery import readable,snapshot,recover,locked
from .operator_inventory import jobs,ROUTES,readable_manifest,can_private,PRIVATE_FAMILY,PRIVATE_FAMILIES
from .operator_models import OperatorInventory,RecoveryPlan,RecoveryProof,RecoveryJob,RecoveryArtifact,RecoveryAssessment,RecoveryReview
from . import protection as d,operator_delivery as delivery,private_readiness_operations as private
from apps.agents import private_readiness_operations as private_agent
from apps.policy.operator_validators import PRIVATE_SCHEMA,PRIVATE_VALUE

def commands(a,c,data=None):
    grants=set(Grant.objects.filter(case=c,user=a,active=True).values_list('action',flat=True))
    def ev(kind):return forms.ModelChoiceField(c.evidence.filter(kind=kind))
    def plans():return forms.ModelChoiceField(visible_plans(a,c))
    from apps.finance.readiness_acceptance import visible as visible_packets,Packet
    packet_query=visible_packets(a,c) if 'validation.export' in grants else Packet.objects.none()
    from apps.documents.protection_acceptance import visible as protection_visible,Packet as ProtectionPacket
    protection_query=protection_visible(a,c) if 'validation.export' in grants else ProtectionPacket.objects.none()
    key=lambda:forms.CharField(max_length=100)
    def choice(values):return forms.ChoiceField(choices=[(k,k) for k in values])
    defs={
      'snapshot':('Record scoped workflow inventory','ops.snapshot',{'operation_key':key()}),
      'recover':('Use source workflow recovery controls','ops.recover',{'family':choice([k for k,v in ROUTES.items() if v[2] in grants and v[3] in grants and (k not in PRIVATE_FAMILIES or can_private(a,c,k))]),'job_id':forms.IntegerField(min_value=1),'operation':choice(['cancel','retry','replace_intent']),'reason':forms.CharField(max_length=400)}),
      'plan':('Capture or revise recovery evidence plan','ops.capture',{'reference':key(),'payload':forms.JSONField(widget=forms.Textarea),'evidence':ev('ops_plan'),'predecessor':forms.IntegerField(required=False,min_value=1),'private_readiness_packets':forms.ModelMultipleChoiceField(packet_query,required=False),'private_protection_packets':forms.ModelMultipleChoiceField(protection_query,required=False)}),
      'proof':('Capture supplied export/backup/restore report','ops.capture',{'plan':plans(),'evidence':ev('ops_proof')}),
      'policy':('Draft supplemental operator/protection configuration','policy.configure',{'component':choice(SCHEMAS),'content':forms.JSONField(widget=forms.Textarea),'evidence':ev('policy_decision'),'effective_from':forms.DateTimeField()}),
      'export':('Reserve scoped metadata export','ops.export',{'plan':plans()}),
      'backup':('Reserve sealed metadata file copy','ops.backup',{'plan':plans(),'artifact':forms.ModelChoiceField(RecoveryArtifact.objects.filter(job__plan__in=visible_plans(a,c),job__kind='export'))}),
      'restore':('Reserve isolated metadata restore drill','ops.restore',{'plan':plans(),'artifact':forms.ModelChoiceField(RecoveryArtifact.objects.filter(job__plan__in=visible_plans(a,c),job__kind='backup'))}),
      'operate':('Reconcile protection job intent','ops.operate',{'job':forms.ModelChoiceField(RecoveryJob.objects.filter(plan__in=visible_plans(a,c))),'operation':choice(['cancel','retry','replace_intent']),'reason':forms.CharField(max_length=400)}),
      'assess':('Assess current protection evidence','ops.assess',{'plan':plans(),'operation_key':key()}),
      'review':('Review exact protection evidence assessment','ops.review',{'assessment':forms.ModelChoiceField(RecoveryAssessment.objects.filter(plan__in=visible_plans(a,c))),'verdict':choice(['confirm','return','withdraw']),'operation_key':key(),'evidence':ev('ops_review')}),
      'investigate':('Investigate recovery and protection gaps','agent.operations',{})}
    private={'plan','proof','assess','review'}
    return [{'title':title,'form':type('OPS'+k,(CommandForm,),fields)(data if data is not None and data.get('action')==k else None,initial={'action':k,'revision':c.revision},auto_id='id_'+k+'_%s')} for k,(title,permission,fields) in defs.items() if permission in grants and (k not in private or 'ops.proof.read' in grants)]

@login_required
@transaction.atomic
def workbench(request,case_id):
    c=accessible_case(request.user,case_id);c=locked(request.user,c.pk,'ops.read');readable(request.user,c);forms=commands(request.user,c,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            f=next((x['form'] for x in forms if x['form']['action'].value()==request.POST.get('action')),None)
            if not f or not f.is_valid() or set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Valid permitted command required')
            v=f.cleaned_data;a=request.user;k=v['action'];rev=v['revision'];eid=v['evidence'].pk if v.get('evidence') else None
            if k=='snapshot':snapshot(a,c.pk,v['operation_key'],rev)
            elif k=='recover':recover(a,c.pk,v['family'],v['job_id'],v['operation'],v['reason'],rev)
            elif k=='plan':
                payload=v['payload'];selected=[p.pk for p in v['private_readiness_packets'].order_by('pk')]
                if not isinstance(payload,dict):raise ValidationError('Typed plan object required')
                if private.FIELD in payload and payload[private.FIELD]!=selected:raise ValidationError('Exact source-authorised UI packet selection required')
                if selected:payload=dict(payload,**{private.FIELD:selected})
                protection_selected=[p.pk for p in v['private_protection_packets'].order_by('pk')]
                if private.protection.FIELD in payload and payload[private.protection.FIELD]!=protection_selected:raise ValidationError('Exact source-authorised protection selection required')
                if protection_selected:payload=dict(payload,**{private.protection.FIELD:protection_selected})
                if selected or protection_selected:private_agent.prepare(a,c.pk,v['reference'],payload,eid,rev,v['predecessor'])
                else:d.capture_plan(a,c.pk,v['reference'],payload,eid,rev,v['predecessor'])
            elif k=='proof':d.capture_proof(a,c.pk,v['plan'].pk,eid,rev)
            elif k=='policy':
                from django.db import transaction
                with transaction.atomic():locked(a,c.pk,'policy.configure',rev);draft_operator_policy(a,c.pk,v['component'],v['content'],eid,v['effective_from'])
            elif k in ['export','backup','restore']:delivery.reserve(a,c.pk,v['plan'].pk,k,v['artifact'].pk if v.get('artifact') else None,rev)
            elif k=='operate':delivery.operate(a,c.pk,v['job'].pk,v['operation'],v['reason'],rev)
            elif k=='assess':d.assess(a,c.pk,v['plan'].pk,v['operation_key'],rev)
            elif k=='review':d.review(a,c.pk,v['assessment'].pk,v['verdict'],v['operation_key'],eid,rev)
            elif k=='investigate':investigate(a,c.pk,rev)
            messages.success(request,'Scoped operator/evidence history updated; no full-database restore, business replay or deployment inferred')
        except (ValidationError,ValueError,TypeError,ConnectionError):messages.error(request,'Action held by current source, configuration or target controls. Inspect the scoped workflow and typed contract; no forced retry performed.')
        return redirect('operations',case_id=c.pk)
    rows,omitted,_=jobs(request.user,c)
    response=render(request,'workflows/operations.html',{'case':c,'jobs':rows,'omitted':omitted,'policies':[resolve(k,c) for k in SCHEMAS],'plans':visible_plans(request.user,c).order_by('-pk')[:30],'inventories':visible_inventories(request.user,c),'artifacts':RecoveryArtifact.objects.filter(job__plan__in=visible_plans(request.user,c)).order_by('-pk')[:30],'assessments':[{'row':r,'report':d.report(request.user,c.pk,r.pk)} for r in RecoveryAssessment.objects.filter(plan__in=visible_plans(request.user,c)).order_by('-pk')[:20]],'reviews':RecoveryReview.objects.filter(assessment__plan__in=visible_plans(request.user,c)).order_by('-pk')[:30],'commands':forms,'schemas':{'plan':d.PLAN,'supplied_proof':d.PROOF,'policy':SCHEMAS,'private_protection':{PRIVATE_SCHEMA:PRIVATE_VALUE}},'private_guidance':private_agent.investigate(request.user,c.pk) if Grant.objects.filter(case=c,user=request.user,action='agent.operations',active=True).exists() else None,'investigations':AgentRun.objects.filter(case=c,actor=request.user,provider='deterministic-operations-v1').order_by('-pk')[:5]});response['Cache-Control']='no-store';return response

@login_required
@transaction.atomic
def artifact(request,case_id,pk):
    c=accessible_case(request.user,case_id);c=locked(request.user,c.pk,'ops.artifact.read');readable(request.user,c);require(request.user,c,'ops.artifact.read');r=RecoveryArtifact.objects.filter(job__plan__case=c,pk=pk).first()
    if not r:raise Http404
    readable_manifest(request.user,c,r.manifest)
    return HttpResponse(encoded(r.manifest),content_type='application/json',headers={'Content-Disposition':f'attachment; filename="case-metadata-{r.pk}.json"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

@login_required
@transaction.atomic
def proof(request,case_id,kind,pk):
    c=accessible_case(request.user,case_id);c=locked(request.user,c.pk,'ops.proof.read');readable(request.user,c,True);model=RecoveryPlan if kind=='plan' else RecoveryProof if kind=='proof' else None
    r=model.objects.filter(**({'case':c} if kind=='plan' else {'plan__case':c}),pk=pk).first() if model else None
    if not r:raise Http404
    plan=r if kind=='plan' else r.plan
    private.plan_access(request.user,plan)
    for artifact in RecoveryArtifact.objects.filter(job__plan=plan):readable_manifest(request.user,c,artifact.manifest)
    return JsonResponse({'id':r.pk,'payload':r.payload,'sha256':r.sha256,'native_execution_verified':False},headers={'Cache-Control':'no-store'})

@login_required
def report(request,case_id,pk):
    c=accessible_case(request.user,case_id)
    try:value=d.report(request.user,c.pk,pk)
    except ValidationError:raise Http404 from None
    return JsonResponse(value,headers={'Cache-Control':'no-store'})


def visible_plans(a,c):
    q=RecoveryPlan.objects.filter(case=c)
    hidden=set()
    for p in q:
        try:private.plan_access(a,p)
        except PermissionDenied:hidden.add(p.pk)
    for r in RecoveryArtifact.objects.filter(job__plan__case=c):
        try:readable_manifest(a,c,r.manifest)
        except PermissionDenied:hidden.add(r.job.plan_id)
    return q.exclude(pk__in=hidden)


def visible_inventories(a,c):
    rows=[]
    for r in OperatorInventory.objects.filter(case=c).order_by('-pk')[:20]:
        try:readable_manifest(a,c,dict(r.manifest,case_id=str(c.pk)))
        except PermissionDenied:continue
        rows.append(r)
    return rows
