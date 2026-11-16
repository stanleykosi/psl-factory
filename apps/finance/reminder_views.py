from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.core.models import Evidence
from apps.core.views import accessible_case
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.reminder_validators import COMPONENT

from . import reminders


class DraftForm(forms.Form):
    subject = forms.CharField(max_length=180)
    body = forms.CharField(max_length=10000, label='Message', widget=forms.Textarea(attrs={'rows': 8}))


class OutcomeForm(forms.Form):
    reference = forms.CharField(max_length=160, label='Delivery reference')
    delivered = forms.TypedChoiceField(choices=[('yes', 'Delivered'), ('no', 'Confirmed undelivered')], coerce=lambda x: x == 'yes')
    evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Channel evidence')


class RuleForm(forms.Form):
    content = forms.JSONField(label='Reminder delivery rules', widget=forms.Textarea(attrs={'rows': 5}),
        help_text='Set contact_revision_ids, sender_ids, receipt_recorder_ids, mode, days_after_due and minimum_days_between.')
    evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Owner decision')


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def work(request, case_id, issue_id):
    actor, case = request.user, accessible_case(request.user, case_id)
    try:
        issue = reminders.exact(actor, case, issue_id)
    except ValidationError as exc:
        raise Http404 from exc
    current = issue.reminder_drafts.select_related('contact').order_by('-number').first()
    destination = reminders.contact(issue)
    balance = reminders.facts(issue)
    activity = list(issue.reminder_drafts.select_related('contact', 'dispatch__receipt', 'set_aside').order_by('-number')[:20])
    actions = set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True))
    title, body = reminders.suggested(issue, balance)
    if current:
        title, body = current.subject, current.body
    command = request.POST.get('action') if request.method == 'POST' else None
    editable = DraftForm(request.POST if command == 'draft' else None, initial={'subject': title, 'body': body})
    rule = RuleForm(request.POST if command == 'policy' else None)
    rule.fields['evidence'].queryset = case.evidence.filter(kind='policy_decision').defer('body')
    outcome = OutcomeForm(request.POST if command == 'confirm' else None)
    outcome.fields['evidence'].queryset = case.evidence.filter(kind='payment_reminder_receipt').defer('body')
    if command:
        try:
            version = int(request.POST.get('revision', ''))
            if command == 'draft' and editable.is_valid():
                reminders.draft(actor, case.pk, issue.pk, editable.cleaned_data['subject'], editable.cleaned_data['body'], version)
            elif command == 'send':
                reminders.dispatch(actor, case.pk, issue.pk, int(request.POST['draft']), version)
            elif command == 'set_aside':
                reminders.set_aside(actor, case.pk, issue.pk, int(request.POST['draft']), request.POST.get('reason', ''), version)
            elif command == 'confirm' and outcome.is_valid():
                data = outcome.cleaned_data
                reminders.confirm(actor, case.pk, issue.pk, int(request.POST['dispatch']), data['reference'],
                                  data['delivered'], data['evidence'].pk, version)
            elif command == 'policy' and rule.is_valid():
                draft_operator_policy(actor, case.pk, COMPONENT, rule.cleaned_data['content'], rule.cleaned_data['evidence'].pk, timezone.now())
            else:
                raise ValidationError('Check the reminder form.')
        except (KeyError, ValueError, ValidationError) as exc:
            messages.error(request, exc.messages[0] if isinstance(exc, ValidationError) else 'Check the selected reminder.')
        else:
            messages.success(request, 'Reminder history updated.')
            return redirect(reverse('design_payment_reminder', args=[case.pk, issue.pk]))
    send_mode = None
    hold = None
    if current and not hasattr(current, 'dispatch') and not hasattr(current, 'set_aside'):
        try:
            _, settings = reminders.send_ready(actor, case, issue, current)
            send_mode = settings['mode']
        except PermissionDenied:
            hold = 'A configured Finance sender can release the saved draft.'
        except ValidationError as exc:
            hold = exc.messages[0]
    return render(request, 'finance/payment_reminder.html', {
        'case': case, 'issue': issue, 'current': current, 'destination': destination, 'balance': balance,
        'activity': activity, 'editable': editable, 'rule': rule, 'outcome': outcome, 'hold': hold, 'send_mode': send_mode,
        'can_prepare': 'finance.reminder.prepare' in actions, 'can_confirm': 'finance.reminder.confirm' in actions,
        'can_configure': 'policy.configure' in actions,
    })
