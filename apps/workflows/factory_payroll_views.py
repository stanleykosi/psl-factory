"""Work-centric payroll console: references only, native private data boundaries."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from apps.core.models import Case,Evidence
from apps.core.workbench import granted
from apps.finance.payroll_models import PayrollRequest,PayrollInput
from apps.finance.hrfinance_models import HRReadSnapshot
from . import factory,factory_payroll as payroll

class InputsForm(forms.Form):
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['request_id']=forms.ModelChoiceField(queryset=PayrollRequest.objects.filter(case=case),label='Exact payroll request')
        self.fields['input_ids']=forms.ModelMultipleChoiceField(queryset=PayrollInput.objects.defer('payload').filter(request__case=case,metadata__accepted=True),label='Exactly two accepted provider versions')
        self.fields['hr_snapshot_id']=forms.ModelChoiceField(queryset=HRReadSnapshot.objects.defer('payload').filter(contract__need__case=case),required=False,label='Exact minimal HR snapshot')
    def inputs(self):return {'input_ids':sorted(i.pk for i in self.cleaned_data['input_ids']),'hr_snapshot_id':self.cleaned_data['hr_snapshot_id'].pk if self.cleaned_data['hr_snapshot_id'] else None}

class StartForm(forms.Form):
    definition=forms.CharField(initial=payroll.DEFINITION,widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none(),label='Workspace')
    reference=forms.CharField(max_length=160,label='Describe the payroll work (no employee details)')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,*args,case_id=None,**kwargs):
        super().__init__(*args,**kwargs);cases=granted(actor,['payroll.read','payroll.private.read','factory.start','evidence.add']);self.fields['case'].queryset=cases
        self.selected=cases.filter(pk=case_id).first() if case_id else None
        if self.selected:self.fields['case'].initial=self.selected;self.fields['revision'].initial=self.selected.revision
        if not self.is_bound:self.fields['key'].initial='PAYROLL-'+uuid4().hex

@require_http_methods(['GET','HEAD','POST'])
def create(request):
    case_id=request.POST.get('case') if request.method=='POST' else request.GET.get('case')
    form=StartForm(request.user,request.POST if request.method=='POST' else None,case_id=case_id)
    inputs=InputsForm(form.selected,request.POST if request.method=='POST' else None) if form.selected else None
    if request.method=='POST' and form.is_valid() and inputs and inputs.is_valid():
        try:
            d=form.cleaned_data
            if d['definition']!=payroll.DEFINITION:raise ValidationError('Choose the payroll definition')
            w=payroll.start(request.user,d['case'].pk,d['key'],inputs.cleaned_data['request_id'].pk,inputs.inputs(),d['reference'],d['revision']);return redirect('factory_detail',w.pk)
        except ValidationError as exc:form.add_error(None,payroll.finding(exc))
    response=render(request,'factory/payroll_start.html',{'form':form,'inputs_form':inputs,'case':form.selected});response['Cache-Control']='no-store';return response

def presentation(actor,work):
    from .factory_views import permitted
    factory.access(actor,work.case,'factory.read',payroll.DEFINITION)
    row={'work':work,'title':work.request['reference'],'owner':work.actor.get_full_name() or work.actor.username,'state':work.status,'next_action':'Review restricted payroll work','blocker':'','needs_me':False,'can_advance':False,'jobs':[],'tasks':[],'readiness_changed':False,'payroll':{}}
    try:q,data=payroll.source(work,actor,False)
    except (PermissionDenied,ValidationError):
        p=payroll.publication(work)
        readable=False
        if p:
            try:payroll.native.read_publication(actor,p.pk);readable=True
            except (PermissionDenied,ValidationError):pass
        if readable:
            receipt=payroll.PayrollReportReceipt.objects.filter(publication=p,actor=actor).first()
            row.update(state='Receipt acknowledged' if receipt else 'Aggregate available',next_action='Your receipt is recorded. You can inspect the aggregate report.' if receipt else 'Inspect the aggregate and acknowledge receipt as yourself',needs_me=not bool(receipt))
            row['payroll']={'publication':p.pk,'recipient_only':True,'receipt':receipt};return row
        row.update(state='Restricted payroll work',next_action='A current nominated source reader or report recipient is required')
        row['payroll']={'restricted':True};return row
    try:state=payroll.report(work,actor)
    except (PermissionDenied,ValidationError):state={'stage':'source','finding':'Source changed or expired. Select an exact source-owned replacement.','runs':{}}
    changed=work.status=='verified' and state['stage']!='complete'
    row.update(next_action=state.get('finding') or 'Verify exact aggregate and recipient receipts',blocker=state.get('finding',''),readiness_changed=changed,can_advance=permitted(actor,work,'factory.execute') and work.status not in ['cancelled','verified','followup_needed'])
    row['payroll']={**state,'request':q,'inputs':data['inputs'],'can_correct':permitted(actor,work,'factory.manage'),'can_review':permitted(actor,work,'payroll.review'),'can_publish':permitted(actor,work,'payroll.publish')}
    row['needs_me']=row['can_advance'] or row['payroll']['can_review'];return row

@require_http_methods(['GET','HEAD','POST'])
def detail(request,work):
    panel=presentation(request.user,work)['payroll'];recipient=panel.get('recipient_only',False)
    if panel.get('restricted'):raise PermissionDenied('Current nominated source reader or aggregate recipient required')
    form=None if recipient else InputsForm(work.case,request.POST if request.method=='POST' and request.POST.get('action') in ['correct','restart'] else None,initial={**panel['inputs'],'request_id':panel['request'].pk})
    if request.method=='POST':
        try:
            p=request.POST;action=p.get('action');revision=int(p.get('revision','0'));case_revision=int(p.get('case_revision','0'));notice='Native payroll action recorded'
            if action=='advance':factory.advance(request.user,work.pk,revision)
            elif action=='correct':
                if not form or not form.is_valid():raise ValidationError('Choose exact current payroll sources')
                payroll.correct(request.user,work.pk,revision,case_revision,form.cleaned_data['request_id'].pk,form.inputs(),p.get('reason',''))
            elif action in ['review','publish','receive']:
                values={}
                if action=='review':values={'kind':p.get('kind'),'subject_id':int(p.get('subject_id','0')),'verdict':p.get('verdict'),'operation_key':p.get('operation_key',''),'evidence_id':int(p.get('evidence_id','0'))}
                elif action=='receive':values={'publication_id':int(p.get('publication_id','0'))}
                result=payroll.human_action(request.user,work.pk,revision,case_revision,action,values)
                if action=='receive':notice=f'Your receipt #{result.pk} for aggregate report #{result.publication_id} is recorded.'
            elif action=='restart':
                if not form or not form.is_valid():raise ValidationError('Select exact current payroll sources')
                payroll.restart(request.user,work.pk,revision,case_revision,form.cleaned_data['request_id'].pk,form.inputs(),int(p.get('configuration_id','0')),p.get('instruction_key',''),p.get('reason',''))
            elif action=='cancel':payroll.cancel(request.user,work.pk,revision)
            elif action=='resume':factory.manage(request.user,work.pk,revision,action)
            else:raise ValidationError('Choose a current payroll action')
            messages.success(request,notice);return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc));work.refresh_from_db();work.case.refresh_from_db()
    row=presentation(request.user,work)
    from apps.policy.models import Configuration
    profiles=Configuration.objects.filter(case=work.case,component='OPS.factory_payroll_execution').order_by('-pk') if row['payroll'].get('can_correct') else []
    response=render(request,'factory/payroll_detail.html',{'row':row,'case':work.case,'inputs_form':form,'review_key':'review-'+uuid4().hex,'restart_key':'restart-'+uuid4().hex,'restart_profiles':profiles,'review_evidence':Evidence.objects.filter(case=work.case,kind='payroll_review') if not recipient else []})
    response['Cache-Control']='no-store';return response
