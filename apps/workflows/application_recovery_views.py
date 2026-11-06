from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.policy.application_recovery_validators import COMPONENT, VALUE
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import resolve
from apps.agents import application_recovery as agent
from . import application_recovery as d
from .application_recovery_models import ApplicationRecoveryPlan as Plan, ApplicationRecoveryJob as Job


def commands(case, data=None, files=None):
    plans = Plan.objects.filter(case=case).order_by('-pk')
    definitions = {
        'capture': ('Capture native recovery plan', {'reference': forms.CharField(max_length=100), 'source_ref': forms.CharField(max_length=100), 'target_ref': forms.CharField(max_length=100), 'key_ref': forms.CharField(max_length=100)}),
        'attachment': ('Register managed attachment', {'source_ref': forms.CharField(max_length=100), 'label': forms.CharField(max_length=120), 'file': forms.FileField()}),
        'policy': ('Draft independent recovery criteria', {'content': forms.JSONField(widget=forms.Textarea), 'evidence_id': forms.ModelChoiceField(case.evidence.filter(kind='policy_decision'))}),
        'review': ('Record independent human decision', {'plan': forms.ModelChoiceField(plans), 'phase': forms.ChoiceField(choices=[(s, s) for s in ['authorize', 'recovered']]), 'decision': forms.ChoiceField(choices=[(s, s) for s in ['approve', 'hold']]), 'rationale': forms.CharField(max_length=1000, widget=forms.Textarea), 'operation_key': forms.CharField(max_length=100)}),
        'reserve': ('Queue exact native intent', {'plan': forms.ModelChoiceField(plans), 'kind': forms.ChoiceField(choices=[('archive', 'Encrypted PostgreSQL + attachments'), ('restore', 'Empty isolated application target')])}),
        'retry': ('Reconcile original held intent', {'job': forms.ModelChoiceField(Job.objects.filter(plan__case=case))}),
        'investigate': ('Investigate current recovery evidence', {'plan': forms.ModelChoiceField(plans)}),
    }
    result = []
    for action, (label, fields) in definitions.items():
        cls = type('NativeRecoveryCommand', (forms.Form,), {'action': forms.CharField(initial=action, widget=forms.HiddenInput), **fields})
        result.append((action, label, cls(data if data and data.get('action') == action else None, files)))
    return result


@login_required
@transaction.atomic
def workbench(request, case_id):
    case = accessible_case(request.user, case_id)
    # Mutations acquire their own service lock order (jobs before case scope for
    # retry/worker reconciliation). Do not prelock cases before a POST retry.
    authorized_cases = d.access(request.user, case, locked=request.method == 'GET')
    forms_list = commands(case, request.POST if request.method == 'POST' else None, request.FILES)
    if request.method == 'POST':
        try:
            selected = next((f for action, _, f in forms_list if action == request.POST.get('action')), None)
            if selected is None or not selected.is_valid():
                raise ValidationError('Choose a valid typed recovery command')
            values = selected.cleaned_data.copy()
            action = values.pop('action')
            if action == 'capture':
                reference = values.pop('reference')
                d.capture(request.user, case.pk, reference, values)
            elif action == 'attachment':
                file = values.pop('file')
                if file.size > 1048576:
                    raise ValidationError('Managed attachment exceeds bounded upload size')
                d.attach(request.user, case.pk, data=file.read(), **values)
            elif action == 'policy':
                draft_operator_policy(request.user, case.pk, COMPONENT, values['content'], values['evidence_id'].pk, timezone.now())
            elif action == 'review':
                values['plan_id'] = values.pop('plan').pk
                d.review(request.user, case.pk, **values)
            elif action == 'reserve':
                d.reserve(request.user, case.pk, values['plan'].pk, values['kind'])
            elif action == 'retry':
                d.retry(request.user, case.pk, values['job'].pk)
            else:
                return JsonResponse(agent.investigate(request.user, case.pk, values['plan'].pk), headers={'Cache-Control': 'no-store'})
            messages.success(request, 'Native recovery history updated; dependent execution remains subject to current controls')
            return redirect('application_recovery', case_id=case.pk)
        except (ValidationError, ValueError, KeyError) as exc:
            messages.error(request, str(exc))
    import json
    authorized_cases = d.access(request.user, case, locked=True)
    response = render(request, 'workflows/application_recovery.html', {'case': case, 'commands': forms_list,
        'policy_status': resolve(COMPONENT, case).status, 'value_schema': json.dumps(VALUE, indent=2),
        'plans': Plan.objects.filter(case=case).order_by('-pk')[:20],
        'attachments': d.Attachment.objects.filter(case_id__in=authorized_cases).select_related('case').order_by('pk')[:1000],
        'jobs': Job.objects.filter(plan__case=case).order_by('-pk')[:30]})
    response['Cache-Control'] = 'no-store'
    return response


@login_required
def report(request, case_id, plan_id):
    case = accessible_case(request.user, case_id)
    get_object_or_404(Plan, case=case, pk=plan_id)
    return JsonResponse(d.report(request.user, case.pk, plan_id), headers={'Cache-Control': 'no-store'})
