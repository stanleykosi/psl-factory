"""Typed work console. Private rules and aggregates retain native authority."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from apps.core.models import Case,Evidence
from apps.core.workbench import granted
from apps.finance.bu_models import BUWork, BUReceipt
from apps.finance.payroll_models import PayrollRun
from apps.finance.analysis_models import FinanceRun
from . import factory,factory_bu as bu
from .factory_progress import current_plan_step
from .factory_progress_views import StartWithBackground, start_work
from .aggregate_presentation import publication_receipts
from .screen_focus import require_action

STAGES = {
    'source_review': 'Source and exception review',
    'calculate': 'Checking the selected business-unit inputs',
    'result_review': 'Business-unit totals review',
    'historical_review': 'Historical treatment review',
    'disclosure_held': 'Publication held by disclosure rules',
    'publish': 'Ready for publication',
    'receipt': 'Waiting for recipient receipts',
}

class RefField(forms.ModelChoiceField):
    def label_from_instance(self,obj):
        labels = {'match': 'Payroll match', 'source': 'Accepted event source', 'allocation': 'Company allocation'}
        return f'{labels.get(obj.kind, "Source reference")} {obj.pk}'
class RefsField(forms.ModelMultipleChoiceField):
    def label_from_instance(self,obj):return f'Exception rule #{obj.pk} / version {obj.version}'

class InputsForm(forms.Form):
    mode=forms.ChoiceField(choices=[('staff','Payroll exceptions and staff aggregate'),('event','Supplied-event attribution reference')])
    def __init__(self,case,actor,*args,starting=False,**kwargs):
        super().__init__(*args,**kwargs)
        payroll=[];sources=[];rules=[]
        for p in PayrollRun.objects.defer('result').filter(request__case=case,kind='match').order_by('-pk')[:100]:
            try:bu.inputs_checked(actor,case,{'mode':'staff','payroll_id':p.pk,'source_id':None,'rule_ids':[],'comparison':None},starting);payroll.append(p.pk)
            except (PermissionDenied,ValidationError):pass
        for w in BUWork.objects.defer('payload').filter(case=case,kind__in=['rule','source']).order_by('-pk')[:200]:
            try:
                if w.kind=='rule':
                    if w.payroll_id in payroll:rules.append(w.pk)
                else:
                    bu.native.private_access(actor,w)
                    if starting:
                        bu.native.current(w)
                    sources.append(w.pk)
            except (PermissionDenied,ValidationError):pass
        self.fields['payroll_id']=RefField(PayrollRun.objects.defer('result').filter(pk__in=payroll),required=False,label='Exact payroll match')
        self.fields['rule_ids']=RefsField(BUWork.objects.defer('payload').filter(pk__in=rules),required=False,label='Exceptions to exclude from the standard pool',help_text='Explicitly select every exception. Selection declares each rule’s subject and component. It does not approve a ratio.')
        self.fields['source_id']=RefField(BUWork.objects.defer('payload').filter(pk__in=sources,metadata__accepted=True),required=False,label='Exact accepted supplied-event source')
        self.has_current_sources = bool(payroll or sources)
        from apps.identity.services import require
        try:require(actor,case,'finance.calculate');comparisons=FinanceRun.objects.defer('result','snapshot').filter(case=case,kind='allocation')
        except PermissionDenied:comparisons=FinanceRun.objects.none()
        self.fields['comparison_id']=RefField(comparisons,required=False,label='Existing Finance company comparison')
        self.fields['metric']=forms.ChoiceField(choices=[('','No comparison selected')]+[(v,v.replace('_',' ')) for v in ['revenue','direct_cost','staff_cost','opex','other']],required=False)
    def clean(self):
        d=super().clean()
        if bool(d.get('comparison_id'))!=bool(d.get('metric')):raise forms.ValidationError('Select both the existing allocation and its metric')
        return d
    def inputs(self):
        d=self.cleaned_data
        return {'mode':d['mode'],'payroll_id':d['payroll_id'].pk if d['payroll_id'] else None,'source_id':d['source_id'].pk if d['source_id'] else None,'rule_ids':sorted(x.pk for x in d['rule_ids']),'comparison':{'run_id':d['comparison_id'].pk,'metric':d['metric']} if d['comparison_id'] else None}

class StartForm(StartWithBackground):
    definition=forms.CharField(initial=bu.DEFINITION,widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none(),label='Workspace')
    reference=forms.CharField(max_length=160,label='Work description without private details')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,*args,case_id=None,**kwargs):
        super().__init__(*args,**kwargs);cases=granted(actor,['factory.start','bu.read','bu.private.read','evidence.add']);self.fields['case'].queryset=cases
        self.selected=cases.filter(pk=case_id).first() if case_id else None
        if self.selected:self.fields['case'].initial=self.selected;self.fields['revision'].initial=self.selected.revision
        if not self.is_bound:self.fields['key'].initial='BU-'+uuid4().hex

@never_cache
@require_http_methods(['GET','HEAD','POST'])
def create(request):
    data=request.POST if request.method=='POST' else None
    try:form=StartForm(request.user,data,case_id=(data or request.GET).get('case'))
    except (ValueError,ValidationError):form=StartForm(request.user,data={});form.is_valid();form.add_error(None,'Choose an available workspace')
    inputs=InputsForm(form.selected,request.user,data,starting=True) if form.selected else None
    if request.method=='POST' and form.is_valid() and inputs and inputs.is_valid():
        try:
            d=form.cleaned_data
            if d['definition']!=bu.DEFINITION or set(request.POST)-set(form.fields)-set(inputs.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Choose an exact typed BU command')
            return start_work(request, lambda: bu.start(request.user, d['case'].pk, d['key'],
                              inputs.inputs(), d['reference'], d['revision']), d['background'])
        except ValidationError as exc:form.add_error(None,bu.finding(exc))
    return render(request,'factory/bu_start.html',{'form':form,'inputs_form':inputs,'case':form.selected})

def presentation(actor,work):
    from .factory_views import permitted
    factory.access(actor,work.case,'factory.read',bu.DEFINITION)
    row={'work':work,'title':work.request['reference'],'owner':work.actor.get_full_name() or work.actor.username,'state':work.status,'next_action':'Review BU work','blocker':'','needs_me':False,'can_advance':False,'jobs':[],'tasks':[],'readiness_changed':False,'bu':{}}
    try:p,rules,inputs=bu.source(work,actor,False)
    except (PermissionDenied,ValidationError):
        row.update(title='Received aggregate report', owner='')
        report=bu.publication(work);value=None
        if report:
            try:value=bu.native.read_report(actor,report.pk)
            except (PermissionDenied,ValidationError):pass
        if value is not None:
            receipt=BUReceipt.objects.filter(report=report,actor=actor).first()
            row.update(state='Receipt acknowledged' if receipt else 'Aggregate available',next_action='Your receipt is recorded.' if receipt else 'Inspect the aggregate and acknowledge receipt as yourself',needs_me=not bool(receipt))
            row['bu']={'publication':report.pk,'recipient_only':True,'receipt':receipt,
                       'totals':value['by_bu'],'currency':value['currency'],'period':value['period'],
                       'verified_at':work.updated_at if receipt and work.status=='verified' else None}
            return row
        row.update(state='Restricted BU work',next_action='Current source-reader or aggregate-recipient permission required');row['bu']={'restricted':True};return row
    try:state=bu.report(work,actor)
    except (PermissionDenied,ValidationError):state={'stage':'source','finding':'Source or authority changed. Select an exact source-owned replacement.','subjects':[],'result':None}
    row.update(next_action=state.get('finding') or 'Verify exact aggregate and recipient receipts',blocker=state.get('finding',''),readiness_changed=work.status=='verified' and state['stage']!='complete',can_advance=permitted(actor,work,'factory.execute') and work.status not in ['cancelled','verified','followup_needed'])
    stage = state['stage']
    if work.status not in ('cancelled', 'followup_needed'):
        if state.get('result') and state['result']['status'] == 'held':
            row['state'] = 'Business-unit totals held'
        elif work.status != 'verified' or stage != 'complete':
            row['state'] = STAGES.get(stage, 'Ready for verification' if stage == 'complete' else work.status)
    row['bu']={**state,'inputs':inputs,'can_correct':permitted(actor,work,'factory.manage'),
               'can_review':permitted(actor,work,'bu.review') and not work.cancel_requested,
               'can_publish':stage=='publish' and not work.cancel_requested and permitted(actor,work,'bu.publish')}
    if row['bu']['can_publish']:
        try:bu.native.authority(actor,bu.result(work),'publish')
        except (ValidationError,PermissionDenied):row['bu']['can_publish']=False
    row['needs_me']=row['can_advance'] or row['bu']['can_review'];return row


def investigation_progress(actor, work):
    if work.cancel_requested or work.status in factory.TERMINAL or not work.lease_until or work.lease_until <= timezone.now():
        return None
    try:
        _, profile = factory.profile(work)
        observation = bu.snapshot(work, profile, reader=actor)
        choices, _ = bu.eligible(work, profile, *observation)
        if current_plan_step(work, observation[0]['hash'], choices) == 'ACT04':
            return {'label': 'Investigating the selected business-unit sources and exception rules.', 'watching': True}
    except (PermissionDenied, ValidationError):
        pass
    return None


@never_cache
@require_http_methods(['GET','HEAD','POST'])
def detail(request,work,focus=None):
    row=presentation(request.user,work);panel=row['bu'];recipient=panel.get('recipient_only',False)
    if panel.get('restricted'):raise PermissionDenied('Current source reader or aggregate recipient required')
    if recipient and focus in ('decision','response'):raise PermissionDenied('Open your aggregate receipt to continue')
    initial=panel.get('inputs',{}).copy();comparison=initial.pop('comparison',None)
    if comparison:initial.update(comparison_id=comparison['run_id'],metric=comparison['metric'])
    form=InputsForm(work.case,request.user,request.POST if request.method=='POST' and request.POST.get('action') in ['correct','restart'] else None,initial=initial) if not recipient and panel['can_correct'] and focus in (None,'recovery') else None
    rule_form=None
    from .factory_views import permitted
    if not recipient and focus in (None,'decision') and panel['inputs']['mode']=='staff' and permitted(request.user,work,'bu.rule'):
        try:rule_form=RuleForm(work,request.user,request.POST if request.method=='POST' and request.POST.get('action')=='prepare_rule' else None)
        except (PermissionDenied,ValidationError):pass
    if request.method=='POST':
        try:
            p=request.POST;a=p.get('action');revision=int(p.get('revision','0'));cv=int(p.get('case_revision','0'))
            require_action(work,focus,a)
            common={'csrfmiddlewaretoken','action','revision','case_revision'};fields=set(form.fields) if form else set()
            allowed={'prepare_rule':set(rule_form.fields) if rule_form else set(),'advance':set(),'cancel':set(),'resume':set(),'correct':fields|{'reason'},'restart':fields|{'reason','instruction_key','configuration_id'},'review':{'work_id','purpose','verdict','operation_key','evidence_id'},'publish':set(),'receive':{'publication_id'}}
            if a not in allowed or set(p)-allowed[a]-common:raise ValidationError('Choose an exact typed BU command')
            if recipient and a!='receive':raise PermissionDenied('Aggregate recipients can only acknowledge their own report')
            notice='Native BU action recorded'
            if a=='advance':
                from .factory_progress import set_progress
                set_progress(request.user,work.pk,revision,True)
                notice='Business-unit work queued'
            elif a=='cancel':bu.cancel(request.user,work.pk,revision)
            elif a=='resume':factory.manage(request.user,work.pk,revision,a)
            elif a in ['correct','restart']:
                if not form or not form.is_valid():raise ValidationError('Choose exact native BU sources')
                if a=='correct':bu.correct(request.user,work.pk,revision,cv,form.inputs(),p.get('reason',''))
                else:bu.restart(request.user,work.pk,revision,cv,form.inputs(),int(p.get('configuration_id','0')),p.get('instruction_key',''),p.get('reason',''))
            else:
                values={}
                if a=='prepare_rule':
                    if not rule_form or not rule_form.is_valid():raise ValidationError('Choose the exact payroll subject and explicit BU weights with a positive total')
                    values=rule_form.values()
                if a=='review':values={'work_id':int(p.get('work_id','0')),'purpose':p.get('purpose'),'verdict':p.get('verdict'),'operation_key':p.get('operation_key',''),'evidence_id':int(p.get('evidence_id','0'))}
                if a=='receive':values={'publication_id':int(p.get('publication_id','0'))}
                result=bu.human_action(request.user,work.pk,revision,cv,a,values)
                if a=='prepare_rule':notice='Private rule prepared. Select it as an exclusion and obtain its exact human review before calculation.'
                if a=='receive':notice=f'Your receipt #{result.pk} for aggregate report #{result.report_id} is recorded.'
            messages.success(request,notice);return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:
            messages.error(request,str(exc));work.refresh_from_db();work.case.refresh_from_db()
            row=presentation(request.user,work);panel=row['bu']
    reviews=[]
    if not recipient and focus in (None,'decision') and panel['can_review']:
        for subject in panel.get('subjects',[]):
            w=bu.native.exact(work.case,subject['id'])
            for purpose in [w.kind]+(['historical'] if w.metadata.get('historical') else []):
                try:bu.native.authority(request.user,w,purpose)
                except (ValidationError,PermissionDenied):continue
                latest=w.reviews.filter(purpose=purpose).order_by('-pk').first()
                reviews.append({'work_id':w.pk,'purpose':purpose,'version':w.version,'current':latest,
                                'can_approve':w.metadata['status']=='complete'})
    publication=None;receipt_rows=None;totals={};scope={};investigation=None;progress=None
    if not recipient:
        if focus in (None,'recovery') and (publication:=bu.publication(work)):
            receipt_rows=publication_receipts(publication,bu.DISCLOSE,BUReceipt.objects.filter(report=publication))
        if panel.get('result') and panel['result']['status']=='complete' and focus != 'recovery':
            result=bu.result(work)
            totals=result.payload['by_bu'];scope=result.metadata['scope']
        if not focus:
            if request.method in ('GET', 'HEAD'):
                progress = investigation_progress(request.user, work)
            if progress is None:
                investigation=work.activities.filter(kind='ACT04').order_by('-pk').first()
    from apps.policy.models import Configuration
    return render(request,'factory/bu_detail.html',{'row':row,'case':work.case,'focus':focus,
        'queue':request.GET.get('queue','needs_me'),'q':request.GET.get('q','')[:120],
        'inputs_form':form,'rule_form':rule_form,'reviews':reviews,'review_key':'review-'+uuid4().hex,
        'restart_key':'restart-'+uuid4().hex,'profiles':Configuration.objects.filter(case=work.case,component='OPS.factory_bu_execution') if form and work.status=='cancelled' else [],
        'review_evidence':Evidence.objects.filter(case=work.case,kind='bu_review') if reviews else [],
        'publication':publication,'receipt_rows':receipt_rows,'totals':totals,'currency':scope.get('currency'),
        'period':scope.get('period'),'investigation':investigation,'progress':progress})

class RuleForm(forms.Form):
    """Exact private subject choices and explicit weights; no raw decision JSON."""
    reference=forms.RegexField(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$',label='Stable exception rule reference')
    operation_key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    def __init__(self,work,actor,*args,**kwargs):
        super().__init__(*args,**kwargs);p,rules,inputs=bu.source(work,actor)
        if inputs['mode']!='staff':raise ValidationError('Payroll source required')
        self.payroll=p;self.scope={k:p.request.metadata[k] for k in ['entity','period','currency']}
        from apps.policy.bu_validators import STAFF
        _,self.policy=bu.native.config(STAFF,work.case,self.scope);_,self.bus=bu.native.catalog(work.case,self.scope)
        self.subjects=sorted({(row['employee_id'],row['component']) for row in p.result['rows'] if row['component'] in self.policy['components']})
        self.fields['subject']=forms.ChoiceField(choices=[(str(i),employee+' / '+component) for i,(employee,component) in enumerate(self.subjects)],label='Exact private employee and component')
        self.fields['rationale_evidence_id']=RefField(Evidence.objects.filter(case=work.case,kind='bu_review'),label='Rationale and review evidence')
        for i,b in enumerate(self.bus):self.fields['weight_'+str(i)]=forms.DecimalField(min_value=0,max_digits=24,decimal_places=8,required=False,label='Explicit weight for '+b,help_text='Leave blank only when this BU is not in the exception rule. No previous-period weight is assumed.')
        if not self.is_bound:self.fields['operation_key'].initial='rule-'+uuid4().hex
    def clean(self):
        d=super().clean()
        if not any(d.get('weight_'+str(i)) is not None and d['weight_'+str(i)]>0 for i in range(len(self.bus))):raise forms.ValidationError('Enter explicit positive weights; missing ratios are not zero')
        return d
    def values(self):
        d=self.cleaned_data;employee,component=self.subjects[int(d['subject'])]
        return {'reference':d['reference'],'operation_key':d['operation_key'],'payload':{'employee_id':employee,'component':component,'entity':self.scope['entity'],'period':self.scope['period'],'standard_pool_ref':self.policy['standard_pool_ref'],'weights':[{'bu':b,'weight':str(d['weight_'+str(i)])} for i,b in enumerate(self.bus) if d.get('weight_'+str(i)) is not None],'rationale_evidence_id':d['rationale_evidence_id'].pk}}
