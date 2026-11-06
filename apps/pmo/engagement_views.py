import json
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import render,redirect
from django.utils import timezone
from apps.core.views import accessible_case
from apps.core.evidence_access import public_evidence
from apps.identity.models import Grant
from apps.identity.services import require
from apps.finance.forms import CommandForm
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.engagement_validators import SCHEMAS
from apps.policy.document_validators import ROLES
from .models import RFPDisposition,DeliveryDossier
from . import engagement as d

@login_required
def workbench(request,case_id):
    c=accessible_case(request.user,case_id);require(request.user,c,'engagement.read')
    grants=set(Grant.objects.filter(case=c,user=request.user,active=True).values_list('action',flat=True))
    evidence=lambda:forms.ModelChoiceField(public_evidence(c.evidence.all()).filter(kind__in=['engagement_source','engagement_assignment','engagement_registration','product_input','rfp_outcome','plan']))
    role=lambda:forms.ChoiceField(choices=[(r,r) for r in ROLES]);key=lambda:forms.CharField(max_length=100)
    definitions={
        'capture':('Capture engagement provenance','engagement.capture',{'route':forms.ChoiceField(choices=[(r,r) for r in ['A','B','C']]),'evidence_id':evidence(),'reference':key(),'key':key(),'rfp_disposition':forms.ModelChoiceField(RFPDisposition.objects.filter(rfp__case=c,kind='route_a'),required=False)}),
        'assign':('Record source-owned PM assignment','engagement.assign',{'pm_id':forms.ModelChoiceField(get_user_model().objects.filter(is_active=True,grant__case=c,grant__action='engagement.read',grant__active=True).distinct()),'role':role(),'evidence_id':evidence(),'key':key()}),
        'register':('Record formal project identifier during Planning','engagement.register',{'value':forms.CharField(max_length=120),'role':role(),'evidence_id':evidence(),'plan_id':forms.ModelChoiceField(public_evidence(c.evidence.filter(kind='plan'))),'key':key()}),
        'export':('Create registration evidence for downstream work','engagement.export',{'key':key()}),
        'link':('Link registration to an existing delivery dossier','engagement.export',{'dossier_id':forms.ModelChoiceField(DeliveryDossier.objects.filter(case=c)),'key':key()}),
        'policy':('Draft assignment or registration criteria','policy.configure',{'component':forms.ChoiceField(choices=[(k,k) for k in SCHEMAS]),'content':forms.JSONField(widget=forms.Textarea),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='policy_decision'))}),
        'investigate':('Investigate identity and planning gaps','agent.engagement',{})}
    commands=[]
    for action,(title,grant,fields) in definitions.items():
        if grant not in grants:continue
        form=type('Engagement'+action,(CommandForm,),fields)(request.POST if request.method=='POST' and request.POST.get('action')==action else None,initial={'action':action,'revision':c.revision},auto_id='id_'+action+'_%s')
        commands.append({'title':title,'form':form})
        if form.is_bound and form.is_valid():
            v={k:(x.pk if hasattr(x,'pk') else x) for k,x in form.cleaned_data.items() if k not in ['action','revision']}
            try:
                if action=='policy':draft_operator_policy(request.user,c.pk,v['component'],v['content'],v['evidence'],timezone.now())
                elif action=='investigate':
                    from apps.agents.engagement import investigate
                    return JsonResponse(investigate(request.user,c.pk),headers={'Cache-Control':'no-store'})
                elif action=='export':d.export_registration(request.user,c.pk,**v)
                elif action=='link':d.link_delivery(request.user,c.pk,**v)
                else:getattr(d,action)(request.user,c.pk,**v)
                messages.success(request,'Engagement evidence recorded; source authority and downstream gates remain separate.')
                return redirect('engagement',case_id=c.pk)
            except (ValidationError,IntegrityError,get_user_model().DoesNotExist) as exc:form.add_error(None,'Identifier/reference conflict; preserve history and review current source evidence.' if isinstance(exc,IntegrityError) else str(exc))
    response=render(request,'pmo/engagement.html',{'case':c,'commands':commands,'report':d.report(request.user,c.pk),'schemas':{k:json.dumps(v[1],indent=2) for k,v in SCHEMAS.items()},'records':d.Record.objects.filter(case=c).order_by('-pk')[:100]})
    response['Cache-Control']='no-store';return response
