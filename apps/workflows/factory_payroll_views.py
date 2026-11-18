"""Work-centric payroll console: references only, native private data boundaries."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from apps.core.models import Case,Evidence
from apps.core.workbench import granted
from apps.identity.services import require
from apps.finance.payroll_models import PayrollRequest,PayrollInput,PayrollRun
from apps.finance.hrfinance_models import HRReadSnapshot,HRHandoffRecord
from . import factory,factory_payroll as payroll
from .factory_progress_views import StartWithBackground, start_work
from .aggregate_presentation import publication_audience,publication_receipts
from .screen_focus import require_action

STAGES = {
    'input_review': 'Payroll inputs need review',
    'combine': 'Preparing the combined payroll',
    'combine_review': 'Combined payroll needs review',
    'match': 'Preparing the staff match',
    'match_review': 'Staff match needs review',
    'aggregate': 'Calculating payroll totals',
    'aggregate_review': 'Payroll totals need review',
    'publish': 'Ready for publication',
    'receipt': 'Waiting for payroll receipts',
}

REVIEW_HEADINGS = {'input':'Review payroll input','combine':'Review combined payroll',
                   'match':'Review staff match','aggregate':'Review payroll totals'}

class InputsForm(forms.Form):
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['request_id']=forms.ModelChoiceField(queryset=PayrollRequest.objects.filter(case=case),label='Exact payroll request')
        self.fields['input_ids']=forms.ModelMultipleChoiceField(queryset=PayrollInput.objects.defer('payload').filter(request__case=case,metadata__accepted=True),label='Exactly two accepted provider versions')
        self.fields['hr_snapshot_id']=forms.ModelChoiceField(queryset=HRReadSnapshot.objects.defer('payload').filter(contract__need__case=case),required=False,label='Exact minimal HR snapshot')
    def inputs(self):return {'input_ids':sorted(i.pk for i in self.cleaned_data['input_ids']),'hr_snapshot_id':self.cleaned_data['hr_snapshot_id'].pk if self.cleaned_data['hr_snapshot_id'] else None}

class StartForm(StartWithBackground):
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
            return start_work(request, lambda: payroll.start(request.user, d['case'].pk, d['key'],
                              inputs.cleaned_data['request_id'].pk, inputs.inputs(), d['reference'], d['revision']), d['background'])
        except ValidationError as exc:form.add_error(None,payroll.finding(exc))
    response=render(request,'factory/payroll_start.html',{'form':form,'inputs_form':inputs,'case':form.selected});response['Cache-Control']='no-store';return response

def presentation(actor,work):
    from .factory_views import permitted
    factory.access(actor,work.case,'factory.read',payroll.DEFINITION)
    row={'work':work,'title':work.request['reference'],'owner':work.actor.get_full_name() or work.actor.username,'state':work.status,'next_action':'Review restricted payroll work','blocker':'','needs_me':False,'can_advance':False,'jobs':[],'tasks':[],'readiness_changed':False,'payroll':{}}
    try:q,data=payroll.source(work,actor,False)
    except (PermissionDenied,ValidationError):
        p=payroll.publication(work)
        value=None
        if p:
            try:value=payroll.native.read_publication(actor,p.pk)
            except (PermissionDenied,ValidationError):pass
        if value is not None:
            receipt=payroll.PayrollReportReceipt.objects.filter(publication=p,actor=actor).first()
            row.update(state='Receipt acknowledged' if receipt else 'Aggregate available',next_action='Your receipt is recorded. You can inspect the aggregate report.' if receipt else 'Inspect the aggregate and acknowledge receipt as yourself',needs_me=not bool(receipt))
            row['payroll']={'publication':p.pk,'recipient_only':True,'receipt':receipt,
                            'totals':value['by_bu'],'currency':value['currency'],'period':value['period'],
                            'verified_at':work.updated_at if receipt and work.status=='verified' else None};return row
        notice=payroll.withdrawal(work)
        if notice and permitted(actor,work,'payroll.report.read'):
            original=payroll.publication_history(work).defer('payload').filter(pk=notice.data['publication']).first()
            if original and actor.pk in (publication_audience(original,payroll.REPORT) or []):
                receipt=payroll.PayrollReportReceipt.objects.filter(publication=original,actor=actor).first()
                row.update(state='Published payroll withdrawn',next_action='Wait for a newly reviewed report from Finance')
                row['payroll']={'publication':original.pk,'recipient_only':True,'withdrawn':True,
                                'receipt':receipt,'notice':notice}
                return row
        row.update(state='Restricted payroll work',next_action='A current nominated source reader or report recipient is required')
        row['payroll']={'restricted':True};return row
    try:state=payroll.report(work,actor)
    except (PermissionDenied,ValidationError):state={'stage':'source','finding':'Source changed or expired. Select an exact source-owned replacement.','runs':{}}
    changed=work.status=='verified' and state['stage']!='complete'
    row.update(next_action=state.get('finding') or 'Verify exact aggregate and recipient receipts',blocker=state.get('finding',''),readiness_changed=changed,can_advance=permitted(actor,work,'factory.execute') and work.status not in ['cancelled','verified','followup_needed'])
    stage=state['stage'];match=state['runs'].get('match',{})
    hr_held=(stage=='match' and not data['inputs']['hr_snapshot_id']) or 'hr_receipt_missing' in match.get('codes',[])
    if work.status=='followup_needed':
        row.update(state='Published payroll needs follow-up',next_action='Review the original publication and outstanding receipts')
    elif work.status!='cancelled' and (work.status!='verified' or changed):
        if hr_held:
            row.update(state='Staff matching held',next_action='Confirm receipt of the exact HR snapshot before recalculating')
        else:
            row['state']=STAGES.get(stage,'Ready for verification' if stage=='complete' else work.status)
    row['payroll']={**state,'request':q,'inputs':data['inputs'],'can_correct':permitted(actor,work,'factory.manage'),
                    'can_review':permitted(actor,work,'payroll.review') and not work.cancel_requested,
                    'can_publish':stage=='publish' and not work.cancel_requested and permitted(actor,work,'payroll.publish'),
                    'hr_held':hr_held}
    if row['payroll']['can_publish']:
        try:payroll.native.authority(actor,q,'publish')
        except (ValidationError,PermissionDenied):row['payroll']['can_publish']=False
    row['needs_me']=row['can_advance'] or row['payroll']['can_review'];return row

def working_next_stage(actor,work,q,data,selected,panel):
    from .factory_execution import require_control
    if (work.cancel_requested or work.status in ['verified','cancelled','followup_needed'] or
            work.lease_until and work.lease_until>timezone.now() or payroll.publication(work)):return None
    require_control(actor,work)
    stage=None
    if selected and selected.metadata['status']=='held' and panel['ready']:
        stage={'combine':'match','match':'aggregate'}.get(selected.kind)
    elif not selected:
        inputs=payroll.input_rows(actor,work.case,q,data['inputs'])
        if any(row.metadata['status']=='held' for row in inputs):stage='combine'
    if stage:
        require(actor,work.case,'payroll.'+stage)
        payroll.active_component(payroll.native.STAGE_POLICY[stage],work.case)
        if stage in ['match','aggregate']:
            snapshot=data['inputs']['hr_snapshot_id']
            if not snapshot or not HRHandoffRecord.objects.filter(snapshot_id=snapshot,actor=actor,kind='receipt').exists():return None
    return stage


def working_panel(actor,work,request):
    """Load at most one current, authorised working payload; never an agent context."""
    from apps.finance.payroll_working import rows
    try:
        q,data=payroll.source(work,actor)
        selected=None
        for stage in ['aggregate','match','combine']:
            candidate=payroll.checked_run(work,stage,q,data)
            if candidate:
                payroll.native.run_access(actor,candidate);selected=candidate;break
        panel={'record_id':selected.pk if selected else None,'kind':selected.kind if selected else None,
               'draft_only':True,'next_stage':None,'currency':q.metadata['currency'],'period':q.metadata['period']}
        if selected:panel.update(rows(selected.result,selected.kind,page=request.GET.get('working_page'),
                                      status=request.GET.get('working_status','all')))
        try:panel['next_stage']=working_next_stage(actor,work,q,data,selected,panel)
        except (PermissionDenied,ValidationError):panel['continuation_held']=True
        return panel
    except (PermissionDenied,ValidationError):return None


@require_http_methods(['GET','HEAD','POST'])
def detail(request,work,focus=None):
    from .factory_views import permitted
    row=presentation(request.user,work);panel=row['payroll'];recipient=panel.get('recipient_only',False)
    if panel.get('restricted'):raise PermissionDenied('Current nominated source reader or aggregate recipient required')
    if recipient and focus in ('decision','response'):raise PermissionDenied('Open your aggregate receipt to continue')
    form=InputsForm(work.case,request.POST if request.method=='POST' and request.POST.get('action') in ['correct','restart','successor'] else None,initial={**panel['inputs'],'request_id':panel['request'].pk}) if not recipient and panel['can_correct'] and focus in (None,'recovery') else None
    if request.method=='POST':
        try:
            p=request.POST;action=p.get('action');revision=int(p.get('revision','0'));case_revision=int(p.get('case_revision','0'));notice='Native payroll action recorded'
            require_action(work,focus,action)
            if recipient and action!='receive':raise PermissionDenied('Aggregate recipients can only acknowledge their own report')
            if action=='advance':
                from .factory_progress import set_progress
                set_progress(request.user,work.pk,revision,True)
                notice='Payroll work queued'
            elif action=='correct':
                if not form or not form.is_valid():raise ValidationError('Choose exact current payroll sources')
                payroll.correct(request.user,work.pk,revision,case_revision,form.cleaned_data['request_id'].pk,form.inputs(),p.get('reason',''))
            elif action in ['review','publish','receive','receive_hr','working']:
                values={}
                if action=='review':values={'kind':p.get('kind'),'subject_id':int(p.get('subject_id','0')),'verdict':p.get('verdict'),'operation_key':p.get('operation_key',''),'evidence_id':int(p.get('evidence_id','0'))}
                elif action=='receive':values={'publication_id':int(p.get('publication_id','0'))}
                elif action=='receive_hr':values={'snapshot_id':int(p.get('snapshot_id','0')),'evidence_id':int(p.get('evidence_id','0'))}
                elif action=='working':
                    if set(p)-{'action','revision','case_revision','working_stage','csrfmiddlewaretoken'}:
                        raise ValidationError('Use the displayed draft preparation step.')
                    values={'stage':p.get('working_stage')}
                result=payroll.human_action(request.user,work.pk,revision,case_revision,action,values)
                if action=='receive':notice=f'Your receipt #{result.pk} for aggregate report #{result.publication_id} is recorded.'
                elif action=='receive_hr':notice='HR snapshot receipt recorded. Recalculate the selected payroll sources.'
                elif action=='working':notice='Working draft prepared. Held rows and final review requirements are unchanged.'
            elif action=='restart':
                if not form or not form.is_valid():raise ValidationError('Select exact current payroll sources')
                payroll.restart(request.user,work.pk,revision,case_revision,form.cleaned_data['request_id'].pk,form.inputs(),int(p.get('configuration_id','0')),p.get('instruction_key',''),p.get('reason',''))
            elif action=='withdraw':
                payroll.withdraw_publication(request.user,work.pk,revision,case_revision,int(p.get('publication_id','0')),
                                             int(p.get('evidence_id','0')),p.get('reason',''))
                notice='Original publication withdrawn. Its receipt history is retained.'
            elif action=='successor':
                if not form or not form.is_valid():raise ValidationError('Choose corrected payroll sources')
                payroll.prepare_successor(request.user,work.pk,revision,case_revision,int(p.get('publication_id','0')),
                                          form.cleaned_data['request_id'].pk,form.inputs(),p.get('reason',''))
                notice='Corrected payroll preparation opened for fresh review'
            elif action=='cancel':payroll.cancel(request.user,work.pk,revision)
            elif action=='resume':factory.manage(request.user,work.pk,revision,action)
            else:raise ValidationError('Choose a current payroll action')
            messages.success(request,notice);return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:
            messages.error(request,str(exc));work.refresh_from_db();work.case.refresh_from_db()
            row=presentation(request.user,work);panel=row['payroll']
    review_targets=[];publication=None;receipt_rows=None;totals={};hr_snapshot=None;hr_received=False;hr_evidence=[]
    withdrawal=None;withdrawal_evidence=[];can_start_successor=False
    if not recipient and panel['can_review'] and focus in (None,'decision'):
        q=panel['request']
        inputs=PayrollInput.objects.defer('payload').filter(request=q,pk__in=panel['inputs']['input_ids']).order_by('provider')
        runs=PayrollRun.objects.defer('result').filter(request=q,pk__in=[run['id'] for run in panel['runs'].values()]).order_by('pk')
        for kind, items in (('input',inputs), ('run',runs)):
            for item in items:
                purpose='input' if kind=='input' else item.kind
                try:payroll.native.authority(request.user,q,purpose,item.actor_id)
                except (ValidationError,PermissionDenied):continue
                review_targets.append({'kind':kind,'item':item,'title':REVIEW_HEADINGS[purpose],
                                       'current':item.reviews.order_by('-pk').first()})
    if not recipient and focus in (None,'recovery'):
        publication=payroll.publication(work)
        withdrawal=payroll.withdrawal(work,publication.pk if publication else None)
        if not publication and withdrawal:
            publication=payroll.publication_history(work).defer('payload').filter(pk=withdrawal.data['publication']).first()
        if publication:
            receipt_rows=publication_receipts(publication,payroll.REPORT,payroll.PayrollReportReceipt.objects.filter(publication=publication))
        if publication and work.status=='followup_needed':
            can_start_successor=withdrawal is not None and form is not None
            if not withdrawal and permitted(request.user,work,'payroll.review'):
                aggregate=publication.run
                try:payroll.native.authority(request.user,aggregate.request,'aggregate',aggregate.actor_id)
                except (ValidationError,PermissionDenied):pass
                else:withdrawal_evidence=Evidence.objects.filter(case=work.case,kind='payroll_review')
        snapshot_id=panel['inputs']['hr_snapshot_id']
        if panel['hr_held'] and snapshot_id and not work.cancel_requested:
            hr_snapshot=snapshot_id
            hr_received=HRHandoffRecord.objects.filter(contract__need__case=work.case,snapshot_id=snapshot_id,
                                                       kind='receipt',actor=work.execution_actor).exists()
            if not hr_received and request.user.pk==work.execution_actor.pk and permitted(request.user,work,'hrfinance.receive'):
                hr_evidence=Evidence.objects.filter(case=work.case,kind='hr_disclosure_decision')
    if not recipient and panel['runs'].get('aggregate',{}).get('status')=='complete' and focus != 'recovery':
        totals=payroll.run(work,'aggregate').result['by_bu']
    from apps.policy.models import Configuration
    profiles=Configuration.objects.filter(case=work.case,component='OPS.factory_payroll_execution').order_by('-pk') if form and work.status=='cancelled' else []
    response=render(request,'factory/payroll_detail.html',{'row':row,'case':work.case,'focus':focus,
        'queue':request.GET.get('queue','needs_me'),'q':request.GET.get('q','')[:120],
        'inputs_form':form,'review_key':'review-'+uuid4().hex,'restart_key':'restart-'+uuid4().hex,
        'restart_profiles':profiles,'review_targets':review_targets,
        'review_evidence':Evidence.objects.filter(case=work.case,kind='payroll_review') if review_targets else [],
        'publication':publication,'receipt_rows':receipt_rows,'totals':totals,
        'withdrawal':withdrawal,'withdrawal_evidence':withdrawal_evidence,'can_start_successor':can_start_successor,
        'hr_snapshot':hr_snapshot,'hr_received':hr_received,'hr_evidence':hr_evidence,
        'working':working_panel(request.user,work,request) if not recipient and focus in (None,'recovery') else None})
    response['Cache-Control']='no-store';return response
