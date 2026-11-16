from io import BytesIO

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from adapters.reminders import ATTACHMENT_LIMIT, invoice_pdf, verify_message
from apps.agents.models import CaseUpload
from apps.core.models import Evidence
from apps.core.views import accessible_case
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.reminder_validators import COMPONENT

from . import reminders


class DraftForm(forms.Form):
    subject = forms.CharField(max_length=180)
    body = forms.CharField(max_length=10000, label='Message', widget=forms.Textarea(attrs={'rows': 8}))
    attachment = forms.ModelChoiceField(queryset=CaseUpload.objects.none(), required=False, label='Issued invoice PDF')
    attachment_checked = forms.BooleanField(required=False, label='I checked that this PDF is for this issued invoice')

    def __init__(self, actor, case, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = CaseUpload.objects.filter(case=case, actor=actor, name__iendswith='.pdf', size__lte=ATTACHMENT_LIMIT)
        self.fields['attachment'].queryset = choices.filter(pk__in=choices.order_by('-pk').values('pk')[:50]).order_by('-pk')
        self.fields['attachment'].label_from_instance = lambda upload: upload.name

    def clean(self):
        fields = super().clean()
        if fields.get('attachment') is not None and not fields.get('attachment_checked'):
            self.add_error('attachment_checked', 'Check the exact invoice before attaching its PDF.')
        return fields


class ScheduleForm(forms.Form):
    scheduled_for = forms.DateTimeField(label='Send at (local time)',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))


class OutcomeForm(forms.Form):
    reference = forms.CharField(max_length=160, label='Delivery reference')
    delivered = forms.TypedChoiceField(choices=[('yes', 'Delivered'), ('no', 'Confirmed undelivered')], coerce=lambda x: x == 'yes')
    evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Channel evidence')


class RuleForm(forms.Form):
    content = forms.JSONField(label='Reminder delivery rules', widget=forms.Textarea(attrs={'rows': 5}),
        help_text='Set contact_revision_ids, sender_ids, receipt_recorder_ids, mode, days_after_due and minimum_days_between. '
                  'The optional attachment_required and schedule_days_ahead fields control attachments and the scheduling window.')
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
    current = issue.reminder_drafts.select_related('contact', 'attachment').order_by('-number').first()
    destination = reminders.contact(issue)
    balance = reminders.facts(issue)
    activity = list(issue.reminder_drafts.select_related('contact', 'attachment', 'dispatch__receipt', 'set_aside').order_by('-number')[:20])
    actions = set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True))
    title, body = reminders.suggested(issue, balance)
    if current:
        title, body = current.subject, current.body
    command = request.POST.get('action') if request.method == 'POST' else None
    editable = DraftForm(actor, case, request.POST if command == 'draft' else None,
                         initial={'subject': title, 'body': body, 'attachment': current.attachment_id if current else None})
    schedule = ScheduleForm(request.POST if command == 'schedule' else None)
    rule = RuleForm(request.POST if command == 'policy' else None)
    rule.fields['evidence'].queryset = case.evidence.filter(kind='policy_decision').defer('body')
    outcome = OutcomeForm(request.POST if command == 'confirm' else None)
    outcome.fields['evidence'].queryset = case.evidence.filter(kind='payment_reminder_receipt').defer('body')
    if command:
        try:
            version = int(request.POST.get('revision', ''))
            if command == 'draft' and editable.is_valid():
                fields = editable.cleaned_data
                reminders.draft(actor, case.pk, issue.pk, fields['subject'], fields['body'], version,
                                attachment_id=fields['attachment'].pk if fields['attachment'] else None)
            elif command == 'send':
                reminders.dispatch(actor, case.pk, issue.pk, int(request.POST['draft']), version)
            elif command == 'schedule' and schedule.is_valid():
                reminders.dispatch(actor, case.pk, issue.pk, int(request.POST['draft']), version,
                                   scheduled_for=schedule.cleaned_data['scheduled_for'])
            elif command == 'cancel_schedule':
                reminders.cancel_schedule(actor, case.pk, issue.pk, int(request.POST['dispatch']), version)
            elif command == 'check_mailbox':
                checked = reminders.check_mailbox(actor, case.pk, issue.pk, int(request.POST['dispatch']))
                if checked is None:
                    messages.info(request, 'The test mailbox has no message for this release yet.')
                    return redirect('design_payment_reminder', case.pk, issue.pk)
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
        except OSError:
            messages.error(request, 'The private file could not be checked. Try again.')
        else:
            messages.success(request, 'Reminder history updated.')
            return redirect(reverse('design_payment_reminder', args=[case.pk, issue.pk]))
    send_mode = None
    can_schedule = False
    hold = None
    if current and not hasattr(current, 'dispatch') and not hasattr(current, 'set_aside'):
        try:
            _, values = reminders._bound_content(actor, case, issue, current)
            can_schedule = bool(values.get('schedule_days_ahead'))
            _, settings = reminders.send_ready(actor, case, issue, current)
            send_mode = settings['mode']
        except PermissionDenied:
            hold = 'A configured Finance sender can release the saved draft.'
        except ValidationError as exc:
            hold = exc.messages[0]
    return render(request, 'finance/payment_reminder.html', {
        'case': case, 'issue': issue, 'current': current, 'destination': destination, 'balance': balance,
        'activity': activity, 'editable': editable, 'rule': rule, 'outcome': outcome, 'hold': hold, 'send_mode': send_mode,
        'schedule': schedule, 'can_schedule': can_schedule, 'can_send': 'finance.reminder.send' in actions,
        'can_prepare': 'finance.reminder.prepare' in actions, 'can_confirm': 'finance.reminder.confirm' in actions,
        'can_configure': 'policy.configure' in actions,
    })


@login_required
@require_safe
@never_cache
def download(request, case_id, issue_id, draft_id, file_kind):
    case = accessible_case(request.user, case_id)
    try:
        issue = reminders.exact(request.user, case, issue_id)
    except ValidationError as exc:
        raise Http404 from exc
    draft = get_object_or_404(issue.reminder_drafts.select_related('attachment'), pk=draft_id)
    try:
        if file_kind == 'pdf' and draft.attachment_id:
            data = invoice_pdf(draft.attachment)
            filename, content_type = f'invoice-{issue.pk}.pdf', 'application/pdf'
        elif file_kind == 'email' and case.synthetic:
            row = get_object_or_404(reminders.PaymentReminderMailboxMessage.objects.select_related(
                'dispatch__draft__contact', 'dispatch__draft__attachment'), dispatch__draft=draft,
                dispatch__mode='synthetic_mailbox', dispatch__receipt__delivered=True)
            data = bytes(row.message)
            verify_message(row.dispatch, data, row.sha256)
            filename, content_type = f'reminder-{draft.pk}.eml', 'application/octet-stream'
        else:
            raise Http404
    except (OSError, ValidationError) as exc:
        raise Http404('The checked file is currently unavailable.') from exc
    return FileResponse(BytesIO(data), as_attachment=True, filename=filename, content_type=content_type)
