"""Record, verify and apply a bank payment from the exact issued invoice."""
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from adapters import case_uploads
from adapters.billing_usage import KEY
from apps.core.views import accessible_case
from apps.identity.services import active_case_grants, require
from . import bank_receipt_capture as domain, cash, cash_reported_amount, corrections, short_payments
from .models import CashReceipt, CashReversal, CashVerification


class RevisionForm(forms.Form):
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)


class ReportForm(RevisionForm):
    customer=forms.RegexField(KEY,max_length=100,label='Received from')
    amount=forms.DecimalField(required=False,min_value=Decimal('0.00000001'),max_digits=32,
                              decimal_places=8,label='Amount received',help_text='Leave blank if the amount is unknown.')
    currency=forms.RegexField(r'^[A-Z]{3}$',label='Currency')
    amount_basis=forms.ChoiceField(choices=[('', 'Choose basis'),('gross_including_tax','Gross including tax'),
        ('net_excluding_tax','Net excluding tax'),('unknown','Unknown')],label='Amount basis')
    received_at=forms.DateTimeField(label='Date and time in the bank',
        widget=forms.DateTimeInput(attrs={'type':'datetime-local'},format='%Y-%m-%dT%H:%M'))
    source=forms.RegexField(KEY,max_length=100,label='Bank source reference')
    transaction_ref=forms.RegexField(KEY,max_length=100,label='Bank transaction reference')
    locator=forms.RegexField(KEY,max_length=100,label='Statement reference')
    file=forms.FileField(label='Private bank statement (PDF)',widget=forms.ClearableFileInput(attrs={'accept':'.pdf,application/pdf'}))

    def facts(self):
        values=self.cleaned_data
        return {'customer':values['customer'],'source':values['source'],'transaction_ref':values['transaction_ref'],
                'amount':format(values['amount'],'f') if values['amount'] is not None else None,
                'currency':values['currency'],'amount_basis':values['amount_basis'],'received_at':values['received_at'].isoformat()}


class VerifyForm(RevisionForm):
    reported_amount_id=forms.IntegerField(required=False,min_value=1,widget=forms.HiddenInput)
    role=forms.ChoiceField(label='Your verification role')
    confirmed=forms.BooleanField(label='I checked the exact reported facts against the bank statement')
    locator=forms.RegexField(KEY,max_length=100,required=False,label='Verification statement reference')
    file=forms.FileField(label='Independent bank statement (PDF)',required=False,
                         widget=forms.ClearableFileInput(attrs={'accept':'.pdf,application/pdf'}))


class SupplyAmountForm(RevisionForm):
    amount=forms.DecimalField(label='Amount confirmed by the bank',min_value=Decimal('0.00000001'),
                              max_digits=32,decimal_places=8)
    locator=forms.RegexField(KEY,max_length=100,label='New statement reference')
    reason=forms.CharField(max_length=2000,label='How did the amount become known?',widget=forms.Textarea(attrs={'rows':2}))
    file=forms.FileField(label='New private bank statement (PDF)',
                         widget=forms.ClearableFileInput(attrs={'accept':'.pdf,application/pdf'}))


class AllocationForm(RevisionForm):
    role=forms.ChoiceField(label='Your allocation role')
    amount=forms.DecimalField(label='Amount to apply',min_value=Decimal('0.00000001'),max_digits=32,decimal_places=8)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    reason=forms.CharField(max_length=2000,label='Reason',widget=forms.Textarea(attrs={'rows':2}))


def case_actions(actor,case):
    return {action for _,action in active_case_grants(actor,[case.pk],actions={
        'evidence.add','finance.cash.record','finance.cash.verify','finance.cash.assign','finance.cash.allocate',
        'finance.short_payment.read','policy.read',
    })}


def permitted_roles(actor,case,policy,action):
    try:return domain.roles_for(actor,case,policy,action)
    except (ValidationError,PermissionDenied):return []


def proof_access(actor,case,receipt,lot=None,*,supplement=None):
    if supplement:
        cash_reported_amount.authorize(supplement.actor,receipt)
    else:
        for action in ('evidence.add','finance.cash.record'):
            require(receipt.actor,case,action)
    if lot:
        for action in ('evidence.add','finance.cash.verify'):
            require(lot.actor,case,action)
    if actor.pk!=receipt.actor_id and (not lot or actor.pk!=lot.actor_id):
        if not permitted_roles(actor,case,domain.VERIFIER_POLICY,'finance.cash.verify'):
            raise PermissionDenied('Current bank proof authority is required.')


@login_required
@never_cache
@require_http_methods(['GET','HEAD','POST'])
def payment(request,case_id,issue_id,receipt_id=None):
    actor=request.user
    case=accessible_case(actor,case_id)
    issue=domain.issue_for(actor,case,issue_id)
    receipt=domain.read_receipt(case,issue,receipt_id) if receipt_id is not None else None
    actions=case_actions(actor,case)
    init={'revision':case.revision}
    action=request.POST.get('action') if request.method=='POST' else None
    form=None
    verification=None
    supplement=None
    supplied_form=None
    supplied_proof=None
    verification_hold=''
    allocation_hold=''
    report_proof=None
    verification_proof=None
    can_read_proof=False
    can_read_verification=False
    lot=None
    reversed_lot=False
    remaining=None
    position=short_payments.position(issue)
    pending_correction=corrections.unresolved(issue)
    recent=()
    if receipt is None and actions.intersection({'finance.cash.record','finance.cash.verify','finance.cash.allocate'}):
        recent=CashReceipt.objects.filter(case=case,payload__customer=issue.invoice.preparation.coverage.customer).order_by('-pk')[:12]
    if receipt is None and {'evidence.add','finance.cash.record'}<=actions:
        rule={}
        try:rule=domain.proof_policy(case)
        except ValidationError:pass
        form=ReportForm(request.POST if action=='report' else None,request.FILES if action=='report' else None,
           initial={**init,'customer':issue.invoice.preparation.coverage.customer,'currency':issue.invoice.currency,
                    'source':rule.get('source'),'amount_basis':issue.invoice.amount_basis})
    elif receipt:
        lot=CashVerification.objects.filter(receipt=receipt).select_related('actor','evidence','successor').order_by('-pk').first()
        try:
            proof_access(actor,case,receipt)
            report_proof=domain.exact_proof(receipt)
            can_read_proof=bool(report_proof)
        except PermissionDenied:pass
        supplement=cash_reported_amount.latest(receipt)
        if supplement:
            try:
                proof_access(actor,case,receipt,supplement=supplement)
                supplied_proof=domain.exact_proof(receipt,supplement=supplement)
            except PermissionDenied:pass
        elif not lot and receipt.payload['amount'] is None and receipt.actor_id==actor.pk:
            if {'evidence.add','finance.cash.record'}<=actions:
                supplied_form=SupplyAmountForm(request.POST if action=='supply_amount' else None,
                       request.FILES if action=='supply_amount' else None,initial=init)
        if lot:
            verification_proof=domain.exact_proof(receipt,lot)
            try:
                if verification_proof:
                    proof_access(actor,case,receipt,lot)
                    can_read_verification=True
            except PermissionDenied:pass
        else:
            report=supplement or receipt
            current_proof=supplied_proof if supplement else report_proof
            if report.payload['amount'] is None:
                verification_hold='The reported amount is unknown. Verified cash needs a known amount.'
            elif report.payload['amount_basis']=='unknown':
                verification_hold='The reported amount basis is unknown. Verified cash needs its exact basis.'
            elif not current_proof:
                verification_hold='An authorised Finance verifier with access to the current bank proof is needed.'
            else:
                try:
                    rule=domain.proof_policy(case)
                    roles=domain.roles_for(actor,case,domain.VERIFIER_POLICY,'finance.cash.verify')
                    recorder=domain.reference_values(domain.active_component(domain.VERIFIER_POLICY,case))[0]
                    if actor.pk==receipt.actor_id and not recorder['allow_reporter_verify']:
                        roles=[]
                    if not roles:raise PermissionDenied
                    verification=VerifyForm(request.POST if action=='verify' else None,
                         request.FILES if action=='verify' else None,
                         initial={**init,'reported_amount_id':supplement.pk if supplement else None})
                    verification.fields['role'].choices=[(role,role) for role in roles]
                    verification.fields['file'].required=verification.fields['locator'].required=rule['require_independent_evidence']
                except ValidationError:
                    verification_hold='Bank verification rules are needed before this receipt can be verified.'
                except PermissionDenied:
                    verification_hold='A currently authorised Finance verifier is needed.'
        if lot:
            reversed_lot=CashReversal.objects.filter(lot=lot).exists()
            remaining=cash.cash_remaining(lot)
            assignment=cash.assigned(receipt)
            roles=permitted_roles(actor,case,domain.ALLOCATION_POLICY,'finance.cash.allocate')
            if assignment is None or assignment.coverage_id is None:
                assign_roles=permitted_roles(actor,case,domain.ALLOCATION_POLICY,'finance.cash.assign')
                roles=[role for role in roles if role in assign_roles]
            if pending_correction or position['source']['voided']:
                allocation_hold='Check the original invoice correction before applying a payment.'
            elif remaining<=0 or Decimal(position['owed'])<=0:
                allocation_hold='There is no remaining verified cash or open invoice balance to apply.'
            elif not roles:
                allocation_hold='A current allocation rule and an authorised Finance allocator are needed.'
            else:
                rule=domain.reference_values(domain.active_component(domain.ALLOCATION_POLICY,case))[0]
                if lot.actor_id==actor.pk and not rule['allow_verifier_allocation']:
                    allocation_hold='The configured allocator must be different from the verifier.'
                else:
                    form=AllocationForm(request.POST if action=='allocate' else None,
                                        initial={**init,'key':'bank-allocation-'+uuid4().hex})
                    form.fields['role'].choices=[(role,role) for role in roles]
    if action is not None:
        chosen={'report':form if receipt is None else None,
                'supply_amount':supplied_form,'verify':verification,'allocate':form if lot else None}.get(action)
        if chosen is None:
            raise PermissionDenied('This payment step is not available to the current account.')
        if chosen.is_valid():
            values=chosen.cleaned_data
            try:
                if action=='report':
                    receipt=domain.report(actor,case_id,issue_id,values['revision'],chosen.facts(),values['locator'],values['file'])
                    messages.success(request,'Reported bank receipt recorded. Verification is separate.')
                elif action=='supply_amount':
                    domain.supply_amount(actor,case_id,issue_id,receipt.pk,values['revision'],
                         format(values['amount'],'f'),values['locator'],values['reason'],values['file'])
                    messages.success(request,'Amount recorded on the same receipt. Verification is separate.')
                elif action=='verify':
                    domain.verify(actor,case_id,issue_id,receipt.pk,values['revision'],values['role'],values['locator'],
                                  values['file'],reported_amount_id=values['reported_amount_id'])
                    messages.success(request,'The exact receipt has been verified. Any allocation is separate.')
                else:
                    domain.allocate(actor,case_id,issue_id,receipt.pk,values['revision'],values['role'],
                                    format(values['amount'],'f'),values['key'],values['reason'])
                    messages.success(request,'Allocation recorded. The remaining balance stays owed.')
            except ValidationError as exc:
                chosen.add_error(None,exc)
            else:
                return redirect('finance_bank_receipt',case_id=case_id,issue_id=issue_id,receipt_id=receipt.pk)
    return render(request,'finance/bank_receipt.html',{'case':case,'issue':issue,'position':position,'receipt':receipt,
        'received_at':parse_datetime(receipt.payload['received_at']) if receipt else None,
        'timezone_name':timezone.get_current_timezone_name(),'report':form if receipt is None else None,
        'verification':verification,'verification_hold':verification_hold,'lot':lot,'remaining':remaining,
        'reversed_lot':reversed_lot,
        'supplement':supplement,'supplied_form':supplied_form,'supplied_proof':supplied_proof,
        'allocation':form if lot else None,'allocation_hold':allocation_hold,
        'report_proof':report_proof if can_read_proof else None,
        'verification_proof':verification_proof if can_read_verification else None,
        'recent_receipts':recent,
        'can_review_shortfall':'finance.short_payment.read' in actions,
        'can_read_rules':'policy.read' in actions,
    })


@login_required
@require_safe
@never_cache
def download(request,case_id,issue_id,receipt_id,kind):
    actor=request.user
    case=accessible_case(actor,case_id)
    issue=domain.issue_for(actor,case,issue_id)
    receipt=domain.read_receipt(case,issue,receipt_id)
    lot=CashVerification.objects.filter(receipt=receipt,successor__isnull=True).first() if kind=='verification' else None
    supplement=cash_reported_amount.latest(receipt) if kind=='reported-amount' else None
    if (kind not in ('report','verification','reported-amount') or kind=='verification' and not lot
            or kind=='reported-amount' and not supplement):
        raise Http404('Bank proof unavailable.')
    proof_access(actor,case,receipt,lot,supplement=supplement)
    proof=domain.exact_proof(receipt,lot,supplement=supplement)
    if not proof:raise Http404('Bank proof unavailable.')
    try:contents=case_uploads.read(proof)
    except (ValidationError,OSError) as exc:raise Http404('Bank proof unavailable.') from exc
    response=FileResponse(BytesIO(contents),as_attachment=True,filename=proof.name,content_type='application/octet-stream')
    response['Cache-Control']='no-store'
    return response
