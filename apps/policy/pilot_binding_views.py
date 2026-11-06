from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import render,redirect
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Evidence
from apps.core.evidence_access import public_evidence
from apps.identity.services import require
from . import pilot,pilot_bindings as d
from .pilot_binding_validators import WORKERS
from adapters import pilot_guards,pilot_preflight


class IdentityChoice(forms.ModelChoiceField):
    def label_from_instance(self,obj):return '#'+str(obj.pk)


class BindingForm(forms.Form):
    operation=forms.ChoiceField(choices=[(k,k) for k in pilot_guards.REGISTRY])
    participant=forms.ChoiceField(choices=[])
    expected_revision=forms.IntegerField(min_value=1)
    role=forms.CharField(required=False,max_length=50,label='Existing configured role for this action')
    decision_action=forms.ChoiceField(required=False,choices=[('', 'Authority action only')]+[(v,v) for v in ['approve','return','reject','withdraw','reopen']])
    delegated=forms.BooleanField(required=False,label='Evaluate explicit scoped delegation')
    plan_id=forms.ModelChoiceField(required=False,queryset=Evidence.objects.none(),label='Plan evidence')
    cost_id=forms.ModelChoiceField(required=False,queryset=Evidence.objects.none(),label='Costing evidence')
    sow_id=forms.ModelChoiceField(required=False,queryset=Evidence.objects.none(),label='SOW evidence')
    signature_id=forms.ModelChoiceField(required=False,queryset=Evidence.objects.none(),label='Signature evidence')
    evidence_id=forms.ModelChoiceField(required=False,queryset=Evidence.objects.none(),label='Completion evidence')
    name=forms.CharField(required=False,max_length=200,label='Milestone identity')
    invoice_id=IdentityChoice(required=False,queryset=Evidence.objects.none(),label='Exact Finance invoice')
    correction_id=IdentityChoice(required=False,queryset=Evidence.objects.none(),label='Exact Finance correction')
    packet_id=IdentityChoice(required=False,queryset=Evidence.objects.none(),label='Exact private response packet')
    version_id=IdentityChoice(required=False,queryset=Evidence.objects.none(),label='Exact controlled document version')
    action_state_id=IdentityChoice(required=False,queryset=Evidence.objects.none(),label='Exact recorded action clock state')
    dossier_id=IdentityChoice(required=False,queryset=Evidence.objects.none(),label='Exact delivery dossier')
    coverage_id=IdentityChoice(required=False,queryset=Evidence.objects.none(),label='Exact billing coverage')
    cash_receipt_id=IdentityChoice(required=False,queryset=Evidence.objects.none(),label='Exact Finance cash report')
    cash_lot_id=IdentityChoice(required=False,queryset=Evidence.objects.none(),label='Exact verified cash lot')
    issued_invoice_id=IdentityChoice(required=False,queryset=Evidence.objects.none(),label='Exact proven invoice issue')
    cash_verification_evidence_id=IdentityChoice(required=False,queryset=Evidence.objects.none(),label='Exact cash verification evidence')
    cash_allocation_evidence_id=IdentityChoice(required=False,queryset=Evidence.objects.none(),label='Exact cash allocation evidence')
    cash_amount=forms.CharField(required=False,max_length=70,label='Exact cash allocation amount; no rounding')
    operation_key=forms.CharField(required=False,max_length=100,label='Exact cash allocation operation identity')
    verdict=forms.ChoiceField(required=False,choices=[('release','Release'),('withdraw','Withdraw')])
    deployment_ref=forms.RegexField(regex=r'^[a-zA-Z][a-zA-Z0-9_.:-]{0,99}$')
    revision=forms.RegexField(regex=r'^[a-zA-Z][a-zA-Z0-9_.:-]{0,99}$')
    web_key_ref=forms.RegexField(regex=r'^[a-zA-Z][a-zA-Z0-9_.:-]{0,99}$')
    worker_key_ref=forms.RegexField(regex=r'^[a-zA-Z][a-zA-Z0-9_.:-]{0,99}$')
    families=forms.MultipleChoiceField(choices=[(k,k) for k in WORKERS])
    freshness_seconds=forms.IntegerField(min_value=30,max_value=900,initial=300)
    source_identity=forms.RegexField(regex='^[a-f0-9]{64}$')
    schema_identity=forms.RegexField(regex='^[a-f0-9]{64}$')
    database_identity=forms.RegexField(regex='^[a-f0-9]{64}$')

    def __init__(self,actor,contract,*args,**kwargs):
        super().__init__(*args,**kwargs);self.contract=contract
        self.fields['operation'].choices=[(k,k) for k in pilot_guards.REGISTRY if k in contract.payload['operations']]
        self.fields['participant'].choices=[(str(p['user_id']),'Participant #'+str(p['user_id'])) for p in contract.payload['participants']]
        for key,kind in [('plan_id','plan'),('cost_id','costing'),('sow_id','sow'),('signature_id','signature'),('evidence_id','completion')]:
            self.fields[key].queryset=public_evidence(Evidence.objects.filter(case=contract.case,kind=kind))
        from apps.finance.models import Invoice,InvoiceCorrection
        from apps.baas.support_release import Packet,access
        try:
            require(actor,contract.case,'finance.read')
            self.fields['invoice_id'].queryset=Invoice.objects.filter(case=contract.case)
            self.fields['correction_id'].queryset=InvoiceCorrection.objects.filter(case=contract.case)
            from apps.finance.models import CashReceipt,CashVerification,InvoiceIssue
            self.fields['cash_receipt_id'].queryset=CashReceipt.objects.filter(case=contract.case)
            self.fields['cash_lot_id'].queryset=CashVerification.objects.filter(receipt__case=contract.case)
            self.fields['issued_invoice_id'].queryset=InvoiceIssue.objects.filter(invoice__case=contract.case)
            for key,kind in [('cash_verification_evidence_id','cash_verification'),('cash_allocation_evidence_id','cash_allocation')]:
                self.fields[key].queryset=public_evidence(Evidence.objects.filter(case=contract.case,kind=kind))
        except PermissionDenied:pass
        try:
            from apps.pmo.models import DeliveryDossier
            require(actor,contract.case,'delivery.read')
            self.fields['dossier_id'].queryset=DeliveryDossier.objects.filter(case=contract.case)
        except PermissionDenied:pass
        try:
            from apps.finance.models import BillingCoverage
            for action in ['finance.read','payment.read','delivery.read']:require(actor,contract.case,action)
            self.fields['coverage_id'].queryset=BillingCoverage.objects.filter(case=contract.case)
        except PermissionDenied:pass
        try:
            from apps.pmo.models import ActionState
            require(actor,contract.case,'meeting.read')
            self.fields['action_state_id'].queryset=ActionState.objects.filter(item__case=contract.case)
        except PermissionDenied:pass
        try:
            from adapters.document_guard import choices
            self.fields['version_id'].queryset=choices(actor,contract.case)
        except PermissionDenied:pass
        try:
            access(actor,contract.case)
            self.fields['packet_id'].queryset=Packet.objects.filter(case=contract.case)
        except PermissionDenied:pass

    def clean(self):
        v=super().clean()
        if self.errors:return v
        args={'expected_revision':v['expected_revision']}
        for field in pilot_guards.REGISTRY[v['operation']][2]:
            item=v.get(field)
            if item is None or item=='':raise forms.ValidationError('Complete the fields required by the selected native operation')
            args[field]=item.pk if hasattr(item,'pk') else item
        v['payload']={'format':'psl.pilot-bindings/v1','guards':[{'operation':v['operation'],'user_id':int(v['participant']),'arguments':args}],
            'deployment':{'ref':v['deployment_ref'],'revision':v['revision'],'web_key_ref':v['web_key_ref'],'worker_key_ref':v['worker_key_ref'],
                'families':v['families'],'freshness_seconds':v['freshness_seconds'],
                'expected':{k:v[k] for k in ['source_identity','schema_identity','database_identity']}}}
        from .pilot_binding_validators import validate
        validate(self.contract,v['payload']);return v


class ReviewForm(forms.Form):
    verdict=forms.ChoiceField(choices=[('accept','Accept engineering contract'),('reject','Reject'),('defer','Defer')])
    reason=forms.CharField(max_length=2000,widget=forms.Textarea)


@login_required
def workbench(request,case_id,contract_id):
    case,contract=pilot.contract(request.user,case_id,contract_id)
    technical=pilot_preflight.technical()
    form=BindingForm(request.user,contract,request.POST if request.method=='POST' else None,initial={'expected_revision':case.revision,**{k:technical[k] for k in ['source_identity','schema_identity','database_identity']}})
    error=None
    if request.method=='POST' and form.is_valid():
        try:
            b=d.configure(request.user,case_id,contract_id,form.cleaned_data['payload'])
            return redirect('pilot_binding',case_id=case_id,pk=b.pk)
        except ValidationError as exc:error=str(exc)
    response=render(request,'pilot_binding_form.html',{'case':case,'contract':contract,'form':form,'error':error})
    response['Cache-Control']='no-store';return response


@login_required
def detail(request,case_id,pk):
    case,b=d.get(request.user,case_id,pk);error=None;form=ReviewForm(request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            if request.POST.get('command')=='observe_web':d.emit(request.user,case_id,pk,'web')
            elif form.is_valid():d.review(request.user,case_id,pk,form.cleaned_data['verdict'],form.cleaned_data['reason'])
            else:raise ValidationError('Complete the typed engineering verdict')
            return redirect('pilot_binding',case_id=case_id,pk=pk)
        except ValidationError as exc:error=str(exc)
    report=d.report(request.user,case,b.contract)
    response=render(request,'pilot_binding.html',{'case':case,'binding':b,'report':report,'form':form,'error':error})
    response['Cache-Control']='no-store';return response
