import json
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction,DatabaseError
from django.http import JsonResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from apps.core.views import accessible_case
from apps.core.services import add_evidence
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.native_finance_validators import COMPONENT,VALUE
from apps.policy.services import resolve
from apps.agents import native_finance as agent
from . import native_finance as d
from . import finance_readback as readback
from . import followup_transport as transport
from apps.policy.followup_transport_validators import OUTBOUND

def commands(c,actor,data=None):
    mappings=d.visible_mappings(actor,c).order_by('-pk');packets=d.Packet.objects.filter(mapping__in=mappings).order_by('-pk')
    definitions={
      'evidence':('Record Finance-owned mapping evidence',{'body':forms.CharField(max_length=4000,widget=forms.Textarea),'source':forms.CharField(max_length=500)}),
      'capture':('Capture original Finance receipt mapping',{'plan':forms.ModelChoiceField(d.d.Plan.objects.filter(case=c)),
          'reference':forms.CharField(max_length=100),'effect_key':forms.CharField(max_length=64),'provider_ref':forms.CharField(max_length=100),
          'evidence':forms.ModelChoiceField(c.evidence.filter(kind='integration_contract')),'predecessor':forms.ModelChoiceField(mappings,required=False)}),
      'policy':('Draft native Finance criteria',{'content':forms.JSONField(widget=forms.Textarea),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='policy_decision'))}),
      'variants_policy':('Draft allowed invoice receipt variants',{'content':forms.JSONField(widget=forms.Textarea),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='policy_decision'))}),
      'followup':('Export published invoice metadata for current Finance owner',{'packet':forms.ModelChoiceField(packets)}),
      'readback_policy':('Draft native follow-up readback criteria',{'content':forms.JSONField(widget=forms.Textarea),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='policy_decision'))}),
      'readback':('Read current source acknowledgement and owner disposition',{'packet':forms.ModelChoiceField(packets),'operation_key':forms.CharField(max_length=100)}),
      'transport_policy':('Draft authenticated source transport criteria',{'content':forms.JSONField(widget=forms.Textarea),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='policy_decision'))}),
      'transport_reserve':('Queue signed metadata delivery to current source intake',{'packet':forms.ModelChoiceField(packets),'operation_key':forms.CharField(max_length=100)}),
      'transport_retry':('Reconcile original signed intake delivery',{'job':forms.ModelChoiceField(transport.Job.objects.filter(packet__mapping__in=mappings))}),
      'transport_investigate':('Investigate signed intake acknowledgement and holds',{'job':forms.ModelChoiceField(transport.Job.objects.filter(packet__mapping__in=mappings))}),
      'readback_successors':('Read native source successor lineage and separate receipts',{'packet':forms.ModelChoiceField(packets),'operation_key':forms.CharField(max_length=100)}),
      'readback_review':('Independently review exact native follow-up evidence',{'observation_id':forms.ModelChoiceField(readback.Observation.objects.filter(packet__mapping__in=mappings)),
          'verdict':forms.ChoiceField(choices=[('approve','Approve evidence'),('hold','Hold')]),'rationale':forms.CharField(max_length=1000,widget=forms.Textarea),'operation_key':forms.CharField(max_length=100)}),
      'readback_investigate':('Investigate acknowledgement and current authority holds',{'observation_id':forms.ModelChoiceField(readback.Observation.objects.filter(packet__mapping__in=mappings))}),
      'probe':('Verify original operation/payload in current Finance provider',{'mapping':forms.ModelChoiceField(mappings),'operation_key':forms.CharField(max_length=100)}),
      'packet':('Capture companion evidence packet',{'mapping':forms.ModelChoiceField(mappings),'observation':forms.ModelChoiceField(d.Observation.objects.filter(mapping__in=mappings)),
          'destination':forms.ModelChoiceField(d.domains.Observation.objects.filter(contract__plan__case=c,contract__kind='destination')),
          'reference':forms.CharField(max_length=100),'predecessor':forms.ModelChoiceField(packets,required=False)}),
      'review':('Independently review mapping, native observation or companion packet',{'mapping':forms.ModelChoiceField(mappings),
          'observation':forms.ModelChoiceField(d.Observation.objects.filter(mapping__in=mappings),required=False),
          'packet':forms.ModelChoiceField(packets,required=False),'verdict':forms.ChoiceField(choices=[('approve','Approve exact evidence'),('hold','Hold')]),
          'rationale':forms.CharField(max_length=1000,widget=forms.Textarea),'operation_key':forms.CharField(max_length=100)}),
      'reserve':('Queue exact reviewed companion publication',{'packet':forms.ModelChoiceField(packets),'operation_key':forms.CharField(max_length=100)}),
      'retry':('Reconcile original held publication',{'job':forms.ModelChoiceField(d.Job.objects.filter(packet__mapping__in=mappings))}),
      'investigate':('Investigate native Finance evidence and holds',{'mapping':forms.ModelChoiceField(mappings)}),
    }
    return [(action,label,type('NativeFinanceCommand',(forms.Form,),{'action':forms.CharField(initial=action,widget=forms.HiddenInput),**fields})(data if data and data.get('action')==action else None)) for action,(label,fields) in definitions.items()]

@login_required
@transaction.atomic
def workbench(request,case_id):
    c=accessible_case(request.user,case_id);d.access(request.user,c,locked=request.method=='GET');fs=commands(c,request.user,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            f=next((f for action,_,f in fs if action==request.POST.get('action')),None)
            if f is None or not f.is_valid():raise ValidationError('Typed native Finance command required')
            v=f.cleaned_data.copy();action=v.pop('action')
            if action=='evidence':
                d.access(request.user,c,'capture');add_evidence(request.user,c.pk,'integration_contract',v['body'],v['source'])
            elif action in ['policy','variants_policy','readback_policy']:
                from apps.policy.invoice_receipt_validators import VARIANTS
                from apps.policy.followup_readback_validators import COMPONENT as READBACK
                d.access(request.user,c,'configure');draft_operator_policy(request.user,c.pk,{'policy':COMPONENT,'variants_policy':VARIANTS,'readback_policy':READBACK}[action],v['content'],v['evidence'].pk,timezone.now())
            elif action=='followup':return JsonResponse(d.followup_projection(request.user,c.pk,v['packet'].pk),headers={'Cache-Control':'no-store'})
            elif action=='transport_policy':
                d.access(request.user,c,'configure');draft_operator_policy(request.user,c.pk,OUTBOUND,v['content'],v['evidence'].pk,timezone.now())
            elif action=='transport_reserve':transport.reserve(request.user,c.pk,v['packet'].pk,v['operation_key'])
            elif action=='transport_retry':transport.retry(request.user,c.pk,v['job'].pk)
            elif action=='transport_investigate':return JsonResponse(transport.report(request.user,c.pk,v['job'].pk),headers={'Cache-Control':'no-store'})
            elif action=='readback':readback.probe(request.user,c.pk,v['packet'].pk,v['operation_key'])
            elif action=='readback_successors':readback.probe(request.user,c.pk,v['packet'].pk,v['operation_key'],include_successors=True)
            elif action=='readback_review':
                v['observation_id']=v['observation_id'].pk;readback.review(request.user,c.pk,**v)
            elif action=='readback_investigate':
                from apps.agents.finance_readback import investigate
                return JsonResponse(investigate(request.user,c.pk,v['observation_id'].pk),headers={'Cache-Control':'no-store'})
            else:
                for name in ['mapping','plan','observation','destination','packet','evidence']:
                    if name in v:
                        selected=v.pop(name);v[name+'_id']=selected.pk if selected else None
                if 'predecessor' in v:v['predecessor']=v['predecessor'].pk if v['predecessor'] else None
                if action=='capture':d.capture(request.user,c.pk,**v)
                elif action=='probe':d.probe(request.user,c.pk,**v)
                elif action=='packet':d.capture_packet(request.user,c.pk,**v)
                elif action=='review':d.review(request.user,c.pk,**v)
                elif action=='reserve':d.reserve(request.user,c.pk,**v)
                elif action=='retry':d.retry(request.user,c.pk,v['job'].pk)
                else:return JsonResponse(agent.investigate(request.user,c.pk,**v),headers={'Cache-Control':'no-store'})
            messages.success(request,'Finance evidence history recorded; archived jobs and operational activation remain quarantined')
            return redirect('native_finance',case_id=c.pk)
        except (ValidationError,ValueError,KeyError,ConnectionError,OSError,DatabaseError,d.psycopg.Error,d.Observation.DoesNotExist,d.Packet.DoesNotExist):
            messages.error(request,'Command held: check current Finance scope, exact mapping/provider/destination evidence and independent reviews')
    mappings=d.visible_mappings(request.user,c)
    response=render(request,'workflows/native_finance.html',{'case':c,'commands':fs,'schema':json.dumps(VALUE,indent=2),'policy_status':resolve(COMPONENT,c).status,
        'mappings':mappings.order_by('-pk')[:30],'observations':d.Observation.objects.filter(mapping__in=mappings).order_by('-pk')[:50],
        'packets':d.Packet.objects.filter(mapping__in=mappings).order_by('-pk')[:30],'reviews':d.Review.objects.filter(mapping__in=mappings).order_by('-pk')[:50],
        'jobs':d.Job.objects.filter(packet__mapping__in=mappings).order_by('-pk')[:50],'transport_jobs':transport.Job.objects.filter(packet__mapping__in=mappings).order_by('-pk')[:50],
        'readbacks':readback.Observation.objects.filter(packet__mapping__in=mappings).order_by('-pk')[:50],
        'readback_reviews':readback.Review.objects.filter(observation__packet__mapping__in=mappings).order_by('-pk')[:50]})
    response['Cache-Control']='no-store';return response

@login_required
def report(request,case_id,mapping_id):
    c=accessible_case(request.user,case_id);get_object_or_404(d.Mapping,plan__case=c,pk=mapping_id)
    return JsonResponse(d.report(request.user,c.pk,mapping_id),headers={'Cache-Control':'no-store'})
