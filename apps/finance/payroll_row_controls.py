"""Draft-only successor source controls; never an appointment or approval."""
from copy import deepcopy

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.shortcuts import render,redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from adapters.forecast import obj
from apps.core.models import Evidence
from apps.core.services import lock_case,event
from apps.core.views import accessible_case
from apps.documents.contracts import validate
from apps.identity.services import require
from apps.policy.impact import configuration
from apps.policy.models import Configuration
from apps.policy.payroll_drafts import draft_payroll_policy
from apps.policy.payroll_validators import ACCESS,MERGE,schema_for
from apps.policy.services import active_component,reference_values

HANDLING=[('', 'Not decided'),('reject_export','Reject the whole export'),
          ('hold_conflicting_rows','Hold affected rows and continue valid draft rows')]
CURRENCY=[('', 'Not decided'),('request_currency','One agreed currency for the export'),
          ('row_currency','Currency supplied on each row')]
COMMAND=obj({'access_id':{'type':'integer','minimum':1},'merge_id':{'type':'integer','minimum':1},
             'access_head':{'type':'integer','minimum':1},'merge_head':{'type':'integer','minimum':1},
             'row_handling':{'enum':[None,'reject_export','hold_conflicting_rows']},
             'currency_mode':{'enum':[None,'request_currency','row_currency']},
             'headers':{'type':'object','maxProperties':4,'additionalProperties':{'type':'string','maxLength':100}}})


def prepare(actor,case):
    for action in ['policy.read','policy.configure']:require(actor,case,action)
    access=active_component(ACCESS,case);merge=active_component(MERGE,case)
    # Reuse current source-owner checks before copying any registered content.
    for cfg in [access,merge]:configuration(actor,case.pk,cfg.pk)
    source=reference_values(access)[0];rules=reference_values(merge)[0]
    headers=[]
    for provider in source['providers']:
        for layout in provider.get('spreadsheet_layouts',[]):
            headers.append({'key':str(len(headers)),'provider':provider['provider'],'format':layout['format'],
                            'value':layout['columns'].get('currency','')})
    heads={key:Configuration.objects.filter(case=case,component=key).order_by('-revision').values_list('pk',flat=True).first()
           for key in [ACCESS,MERGE]}
    return {'access':access,'merge':merge,'source':source,'rules':rules,'headers':headers,
            'access_head':heads[ACCESS],'merge_head':heads[MERGE]}


@transaction.atomic
def draft(actor,case_id,expected,command,evidence_id):
    validate(COMMAND,command)
    case=lock_case(actor,case_id,'policy.configure',expected);current=prepare(actor,case)
    if (command['access_id'],command['merge_id'])!=(current['access'].pk,current['merge'].pk):
        raise ValidationError('Source or combination rules changed. Review their current versions.')
    if any(command[key]!=current[key] for key in ['access_head','merge_head']):
        raise ValidationError('A newer source-control draft exists. Review the latest versions.')
    if set(command['headers'])!={item['key'] for item in current['headers']}:
        raise ValidationError('Review every displayed spreadsheet source layout.')
    source=deepcopy(current['source']);rules=deepcopy(current['rules'])
    source.update(format='psl.payroll-access/v2',row_handling=command['row_handling'],currency_mode=command['currency_mode'])
    position=0
    for provider in source['providers']:
        for layout in provider.get('spreadsheet_layouts',[]):
            header=command['headers'][str(position)];position+=1
            if header:layout['columns']['currency']=header
            else:layout['columns'].pop('currency',None)
    rules.update(format='psl.payroll-merge/v2',duplicate_within_source={
        None:None,'reject_export':'reject','hold_conflicting_rows':'hold_conflicting_rows'}[command['row_handling']])
    now=timezone.now()
    # Separate native validation and activation remain explicit human steps.
    results=[draft_payroll_policy(actor,case.pk,key,value,evidence_id,now)
             for key,value in [(ACCESS,source),(MERGE,rules)]]
    event(actor,case,'payroll.row_control_drafts',previous_access=current['access'].pk,previous_merge=current['merge'].pk,
          reviewed_heads={key:command[key] for key in ['access_head','merge_head']},
          drafts=[row.pk for row in results],activated=False)
    return results


def saved_versions(actor,case,prepared):
    result=[]
    for component,head,current,title in [(ACCESS,prepared['access_head'],prepared['access'].pk,'Source row checks'),
                                         (MERGE,prepared['merge_head'],prepared['merge'].pk,'Source combination')]:
        if head==current:continue
        try:row=configuration(actor,case.pk,head)
        except (PermissionDenied,ValidationError):
            result.append({'title':title,'access_held':True});continue
        state=row.states.order_by('-pk').first().state
        item={'title':title,'revision':row.revision,'state':state.capitalize(),'choices':[]}
        try:
            content=reference_values(row)[0];validate(schema_for(component,content)[1],content)
            if component==ACCESS:
                item['choices']=[('Conflicting rows',dict(HANDLING).get(content.get('row_handling') or '','Needs review')),
                                 ('Currency source',dict(CURRENCY).get(content.get('currency_mode') or '','Needs review'))]
            else:
                item['choices']=[('Duplicate rows',{None:'Not decided','reject':'Reject the source',
                                  'hold_conflicting_rows':'Hold affected rows'}[content['duplicate_within_source']])]
        except (ValidationError,KeyError,TypeError):item['needs_review']=True
        result.append(item)
    return result


class RowControlsForm(forms.Form):
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    access_id=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    merge_id=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    access_head=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    merge_head=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    row_handling=forms.ChoiceField(required=False,choices=HANDLING,label='When a source contains conflicting rows')
    currency_mode=forms.ChoiceField(required=False,choices=CURRENCY,label='Where is the currency supplied?')
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Recorded source-control decision')

    def __init__(self,case,prepared,*args,**kwargs):
        initial={'revision':case.revision,'access_id':prepared['access'].pk,'merge_id':prepared['merge'].pk,
                 'access_head':prepared['access_head'],'merge_head':prepared['merge_head'],
                 'row_handling':prepared['source'].get('row_handling') or '',
                 'currency_mode':prepared['source'].get('currency_mode') or ''}
        super().__init__(*args,initial=initial,**kwargs)
        self.headers=[]
        proofs=Evidence.objects.filter(case=case,kind='policy_decision').order_by('-pk').values('pk')[:50]
        self.fields['evidence'].queryset=Evidence.objects.defer('body').filter(pk__in=proofs).order_by('-pk')
        for item in prepared['headers']:
            name='currency_header_'+item['key']
            self.fields[name]=forms.CharField(required=False,max_length=100,strip=False,label=item['provider']+' '+item['format'].upper()+' currency column',
                initial=item['value'],help_text='Use the exact source header for a row-currency layout. Leave blank for export-level currency.')
            self.headers.append((item['key'],name))

    def command(self):
        return {key:self.cleaned_data[key] or None for key in ['access_id','merge_id','access_head','merge_head','row_handling','currency_mode']}|{
            'headers':{key:self.cleaned_data[name] for key,name in self.headers}}


@login_required
@require_http_methods(['GET','HEAD','POST'])
def settings(request,case_id):
    case=accessible_case(request.user,case_id)
    for action in ['policy.read','policy.configure']:require(request.user,case,action)
    prepared=None;held=None;form=None
    try:prepared=prepare(request.user,case)
    except (PermissionDenied,ValidationError):held='Current source and combination rules are needed before drafting these changes.'
    if prepared:form=RowControlsForm(case,prepared,request.POST if request.method=='POST' else None)
    if request.method=='POST' and form and form.is_valid():
        try:
            if set(request.POST)-set(form.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Use the displayed source-control review.')
            draft(request.user,case.pk,form.cleaned_data['revision'],form.command(),form.cleaned_data['evidence'].pk)
        except (ValidationError,PermissionDenied):form.add_error(None,'Current source controls or authority changed. Review and try again.')
        else:
            messages.success(request,'Source and combination drafts saved. Review, validate and activate them separately.')
            return redirect('payroll_row_controls',case_id=case.pk)
    versions=saved_versions(request.user,case,prepared) if prepared else []
    response=render(request,'finance/payroll_row_controls.html',{'case':case,'form':form,'held':held,'prepared':prepared,'versions':versions})
    response['Cache-Control']='no-store';return response
