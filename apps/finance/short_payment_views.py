from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.core.services import lock_case
from apps.core.views import accessible_case
from apps.documents.contracts import digest
from apps.identity.services import active_case_grants, require
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.short_payment_validators import COMPONENT, TREATMENTS

from . import cash, corrections, short_payments
from .rules import number


class DecisionForm(forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    position = forms.CharField(max_length=64, widget=forms.HiddenInput)
    allocation = forms.ChoiceField(label='Recorded payment')
    treatment = forms.ChoiceField(label='Decision', widget=forms.RadioSelect)
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))


class ReviewRuleForm(forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    reviewer = forms.ModelChoiceField(get_user_model().objects.none(), label='Finance reviewer', required=False)
    treatments = forms.MultipleChoiceField(choices=list(TREATMENTS.items()), widget=forms.CheckboxSelectMultiple,
                                           label='Permitted decisions', required=False)
    evidence = forms.ModelChoiceField(queryset=None, label='Rule approval evidence')


@login_required
@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def detail(request, case_id, issue_id):
    actor = request.user
    case = accessible_case(actor, case_id)
    issue = short_payments.exact_issue(actor, case, issue_id)
    position = short_payments.position(issue)
    fingerprint = digest(position)
    rule, choices, _ = short_payments.treatments(actor, case)
    receipts = []
    for allocation in cash.allocations(issue=issue).select_related('lot__receipt', 'lot__successor').order_by('pk'):
        payload = cash.lot_payload(allocation.lot)
        receipts.append({'id': allocation.pk, 'reference': payload['transaction_ref'],
                         'received_at': parse_datetime(payload['received_at']),
                         'amount': number(allocation.amount)})
    correction_pending = corrections.unresolved(issue)
    access = active_case_grants(actor, [case.pk], actions=['policy.read', 'policy.configure'])
    is_rule_command = request.method == 'POST' and request.POST.get('action') == 'draft_rule'
    if is_rule_command:
        require(actor, case, 'policy.configure')
    rule_form = None
    if (case.pk, 'policy.configure') in access:
        rule_form = ReviewRuleForm(request.POST if is_rule_command else None, initial={'revision': case.revision})
        rule_form.fields['reviewer'].queryset = get_user_model().objects.filter(
            grant__case=case, grant__action='finance.short_payment.decide', grant__active=True, is_active=True)
        rule_form.fields['evidence'].queryset = case.evidence.filter(kind='policy_decision').order_by('-version')
        if is_rule_command and rule_form.is_valid():
            data = rule_form.cleaned_data
            try:
                with transaction.atomic():
                    lock_case(actor, case_id, 'policy.configure', data['revision'])
                    reviewer = data['reviewer']
                    draft_operator_policy(actor, case_id, COMPONENT,
                                          {'reviewer_id': reviewer.pk if reviewer else None,
                                           'treatments': data['treatments']}, data['evidence'].pk, timezone.now())
            except ValidationError as exc:
                rule_form.add_error(None, exc)
            else:
                messages.success(request, 'Draft rule saved for review in Business rules.')
                return redirect('invoice_short_payment', case_id=case_id, issue_id=issue_id)
    is_decision_command = request.method == 'POST' and not is_rule_command
    form = None
    if is_decision_command or (choices and position['short_payment'] and not correction_pending):
        form = DecisionForm(request.POST if is_decision_command else None,
                            initial={'revision': case.revision, 'position': fingerprint})
        form.fields['allocation'].choices = [('', 'Choose the payment')] + [
            (row['id'], f'{row["reference"]} · {position["currency"]} {row["amount"]}')
            for row in receipts]
        form.fields['treatment'].choices = choices.items()
        if is_decision_command and form.is_valid():
            data = form.cleaned_data
            try:
                short_payments.decide(actor, case_id, issue_id, data['revision'], data['position'],
                                      data['allocation'], data['treatment'], data['reason'])
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, 'Finance decision recorded. The invoice balance stays owed.')
                return redirect('invoice_short_payment', case_id=case_id, issue_id=issue_id)
        if is_decision_command and not choices:
            raise PermissionDenied('This Finance decision requires current configured authority.')
    history = list(issue.short_payment_decisions.select_related('actor').order_by('-pk')[:30])
    for item in history:
        item.current_position = item.position_sha256 == fingerprint
        item.label = TREATMENTS.get(item.treatment, 'Recorded Finance decision')
    try:
        require(actor, case, 'finance.reminder.read')
        from apps.core.client_contacts import authorize
        authorize(actor, case, 'billing')
        can_follow_up = True
    except PermissionDenied:
        can_follow_up = False
    return render(request, 'finance/short_payment.html', {
        'case': case, 'issue': issue, 'position': position, 'rule': rule, 'form': form,
        'receipts': receipts, 'history': history, 'correction_pending': correction_pending,
        'can_follow_up': can_follow_up,
        'can_read_rules': (case.pk, 'policy.read') in access, 'rule_form': rule_form,
    })
