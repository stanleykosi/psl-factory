import json
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse,Http404
from django.shortcuts import render,redirect
from django.utils import timezone
from apps.core.views import accessible_case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.identity.services import visible_cases,require
from apps.finance.forms import CommandForm
from apps.policy.services import resolve
from apps.policy.support_drafts import draft_support_policy
from apps.policy.summary_validators import SCHEMAS
from . import summaries as d

@login_required
def workbench(request,case_id):
    c=accessible_case(request.user,case_id);d.access(request.user,c)
    grants=set(Grant.objects.filter(case=c,user=request.user,active=True).values_list('action',flat=True))
    sources=visible_cases(request.user).filter(tenant=c.tenant,kind='support',synthetic=c.synthetic,pk__in=Grant.objects.filter(user=request.user,active=True,action='support.read').values('case_id'))
    requests=d.visible_requests(request.user,c);versions=d.Version.objects.filter(request__in=requests)
    key=lambda:forms.CharField(max_length=100)
    definitions={
      'request_evidence':('Record private summary-request source','support.summary.capture',{'body':forms.CharField(max_length=100000,widget=forms.Textarea),'source':forms.CharField(max_length=500)}),
      'review_evidence':('Record private human-review evidence','support.summary.review',{'body':forms.CharField(max_length=100000,widget=forms.Textarea),'source':forms.CharField(max_length=500)}),
      'capture':('Capture period, selected scope and audience','support.summary.capture',{'reference':key(),'source_case_ids':forms.ModelMultipleChoiceField(sources),'start':forms.DateTimeField(),'end':forms.DateTimeField(),'membership':forms.ChoiceField(choices=[(x,x) for x in ['linked_receipt_half_open_v1','event_activity_half_open_v1']]),'audience':key(),'evidence_id':forms.ModelChoiceField(c.evidence.filter(kind=d.REQUEST_EVIDENCE)),'key':key()}),
      'prepare':('Prepare a source-linked summary version','support.summary.prepare',{'request_id':forms.ModelChoiceField(requests),'key':key()}),
      'agent':('Draft a bounded evidence summary','agent.support.summary',{'request_id':forms.ModelChoiceField(requests),'key':key()}),
      'review':('Review the exact summary version','support.summary.review',{'version_id':forms.ModelChoiceField(versions),'verdict':forms.ChoiceField(choices=[(x,x) for x in ['approve','return','withdraw']]),'evidence_id':forms.ModelChoiceField(c.evidence.filter(kind=d.REVIEW_EVIDENCE)),'key':key()}),
      'policy':('Draft summary scope or review criteria','policy.configure',{'component':forms.ChoiceField(choices=[(x,x) for x in SCHEMAS]),'content':forms.JSONField(widget=forms.Textarea),'evidence_id':forms.ModelChoiceField(c.evidence.filter(kind='policy_decision'))})}
    commands=[]
    for action,(title,grant,fields) in definitions.items():
        if grant not in grants:continue
        form=type('ComplaintSummary'+action,(CommandForm,),fields)(request.POST if request.method=='POST' and request.POST.get('action')==action else None,initial={'action':action,'revision':c.revision},auto_id='id_'+action+'_%s')
        commands.append({'title':title,'form':form})
        if not form.is_bound or not form.is_valid():continue
        v={k:x for k,x in form.cleaned_data.items() if k not in ['action','revision']}
        try:
            if action in ['request_evidence','review_evidence']:
                require(request.user,c,grant);add_evidence(request.user,c.pk,d.REQUEST_EVIDENCE if action=='request_evidence' else d.REVIEW_EVIDENCE,v['body'],v['source'])
            elif action=='policy':draft_support_policy(request.user,c.pk,v['component'],v['content'],v['evidence_id'].pk,timezone.now())
            else:
                if 'source_case_ids' in v:v['source_case_ids']=sorted(str(x.pk) for x in v['source_case_ids'])
                for name in ['request_id','version_id','evidence_id']:
                    if name in v:v[name]=v[name].pk
                for name in ['start','end']:
                    if name in v:v[name]=v[name].isoformat()
                if action=='agent':
                    from apps.agents.complaint_summaries import draft
                    return JsonResponse(draft(request.user,c.pk,**v),headers={'Cache-Control':'no-store'})
                getattr(d,action)(request.user,c.pk,**v)
            messages.success(request,'Summary evidence recorded; no external publication or financial action was authorized.')
            return redirect('complaint_summaries',case_id=c.pk)
        except (ValidationError,ValueError) as exc:form.add_error(None,str(exc))
    response=render(request,'baas/summaries.html',{'case':c,'commands':commands,'versions':versions.order_by('-pk')[:100],'grants':grants,'criteria':[resolve(k,c) for k in SCHEMAS],'schemas':{k:json.dumps(v[1],indent=2) for k,v in SCHEMAS.items()}})
    response['Cache-Control']='no-store';return response

@login_required
def view(request,case_id,pk,reviewed=False):
    c=accessible_case(request.user,case_id)
    try:value=d.read(request.user,c.pk,pk,reviewed=reviewed)
    except d.Version.DoesNotExist:raise Http404 from None
    except ValidationError:return JsonResponse({'status':'held','reason':'Current source scope, version, reviewer and audience evidence required'},status=409,headers={'Cache-Control':'no-store'})
    response=JsonResponse(value,headers={'Cache-Control':'no-store'})
    if reviewed:response['Content-Disposition']=f'attachment; filename="complaint-summary-{pk}.json"'
    return response
