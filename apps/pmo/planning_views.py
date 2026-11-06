import json
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render,redirect
from django.utils import timezone
from apps.core.views import accessible_case
from apps.identity.models import Grant
from apps.finance.forms import CommandForm
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.planning_validators import COMPONENT,VALUE
from adapters.planning_packet import INPUT,PURPOSES
from . import planning as d
from . import planning_forms

@login_required
def workbench(request,case_id):
    c=accessible_case(request.user,case_id);d.readable(request.user,c)
    grants=set(Grant.objects.filter(case=c,user=request.user,active=True).values_list('action',flat=True))
    report=d.report(request.user,c.pk)
    ordinary=None
    capture_data=request.POST if request.method=='POST' and request.POST.get('action')=='capture_fields' else None
    preview=bool(capture_data is not None and request.POST.get('edit_rows')=='add_question')
    row_error=None
    if preview:
        capture_data=request.POST.copy()
        try:
            total=int(capture_data.get('questions-TOTAL_FORMS',''))
            if not 0<=total<100:raise ValueError
            capture_data['questions-TOTAL_FORMS']=str(total+1)
        except (ValueError,TypeError):row_error='At most 100 question rows are available; use a valid form management count.'
    if 'planning.coordinate' in grants:
        ordinary=planning_forms.capture_forms(c,capture_data,report.get('payload'),report.get('current_packet_id'))
        if row_error:ordinary[0].add_error(None,row_error)
    if request.method=='POST' and request.POST.get('action')=='capture_fields':
        if ordinary is None:raise PermissionDenied('Current planning coordination grant required')
        validations=[form.is_valid() for form in ordinary] if not preview else []
        if not preview and all(validations):
            try:
                d.capture(request.user,c.pk,planning_forms.payload(*ordinary),ordinary[0].cleaned_data['predecessor'])
                return redirect('planning',case_id=c.pk)
            except (ValidationError,PermissionDenied) as exc:ordinary[0].add_error(None,str(exc))
    number=lambda:forms.IntegerField(min_value=1)
    commands={
        'capture':('Advanced typed JSON capture','planning.coordinate',{'payload':forms.JSONField(widget=forms.Textarea),'predecessor':forms.IntegerField(min_value=1,required=False)}),
        'align':('Link an actual formal alignment session','planning.coordinate',{'packet_id':number(),'purpose':forms.ChoiceField(choices=[(k,k) for k in PURPOSES]),'meeting_version_id':number()}),
        'open_requests':('Open separate department-owned scope/estimate requests','planning.route',{'packet_id':number()}),
        'compare':('Record signed-contract source comparison','planning.compare',{'packet_id':number(),'verdict':forms.ChoiceField(choices=[(k,k) for k in ['no_difference','difference_unresolved']]),'evidence_id':number()}),
        'prepare':('Prepare current referenced planning readiness','planning.prepare',{'packet_id':number()}),
        'bridge':('Link current readiness into delivery scope source','planning.prepare',{'readiness_id':number(),'dossier_id':number()}),
        'policy':('Draft planning/readiness criteria','policy.configure',{'content':forms.JSONField(widget=forms.Textarea),'evidence_id':number()}),
        'investigate':('Inspect current planning dependencies','agent.planning',{})}
    forms_out=[]
    for action,(title,grant,fields) in commands.items():
        if grant not in grants:continue
        form=type('Planning'+action,(CommandForm,),fields)(request.POST if request.method=='POST' and request.POST.get('action')==action else None,initial={'action':action,'revision':c.revision},auto_id='id_'+action+'_%s')
        forms_out.append({'title':title,'form':form})
        if form.is_bound and form.is_valid():
            try:
                v={k:x for k,x in form.cleaned_data.items() if k not in ['action','revision']}
                if action=='policy':draft_operator_policy(request.user,c.pk,COMPONENT,v['content'],v['evidence_id'],timezone.now())
                elif action=='investigate':
                    from apps.agents.planning import investigate
                    return JsonResponse(investigate(request.user,c.pk),headers={'Cache-Control':'no-store'})
                else:getattr(d,action)(request.user,c.pk,**v)
                return redirect('planning',case_id=c.pk)
            except (ValidationError,PermissionDenied) as exc:form.add_error(None,str(exc))
    response=render(request,'pmo/planning.html',{'case':c,'commands':forms_out,'ordinary':ordinary,'report':json.dumps(report,indent=2),'input_schema':json.dumps(INPUT,indent=2),'criteria_schema':json.dumps(VALUE,indent=2)})
    response['Cache-Control']='no-store';return response
