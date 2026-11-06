import json
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.core.views import accessible_case, policy_workbench
from apps.identity.services import visible_cases
from apps.policy.services import resolve
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.cold_recovery_validators import COMPONENT, VALUE
from apps.agents import cold_recovery as agent
from . import cold_recovery as d


def commands(case, data=None):
    plans = d.Plan.objects.filter(case=case).order_by('-pk')
    definitions = {
        'capture': ('Capture exact sealed recovery request', {'reference': forms.CharField(max_length=100), **{k: forms.CharField(max_length=100) for k in ['archive_ref', 'target_ref', 'key_ref']}}),
        'evidence': ('Record fresh configuration decision evidence', {'body': forms.CharField(max_length=4000, widget=forms.Textarea), 'source': forms.CharField(max_length=500)}),
        'policy': ('Draft independent cold recovery criteria', {'content': forms.JSONField(widget=forms.Textarea), 'evidence_id': forms.ModelChoiceField(case.evidence.filter(kind='policy_decision'))}),
        'review': ('Record independent human decision', {'plan': forms.ModelChoiceField(plans), 'phase': forms.ChoiceField(choices=[(x,x) for x in ['authorize','recovered']]), 'decision': forms.ChoiceField(choices=[(x,x) for x in ['approve','hold']]), 'rationale': forms.CharField(max_length=1000, widget=forms.Textarea), 'operation_key': forms.CharField(max_length=100)}),
        'reserve': ('Queue exact isolated recovery', {'plan': forms.ModelChoiceField(plans)}),
        'retry': ('Reconcile original held intent', {'job': forms.ModelChoiceField(d.Job.objects.filter(plan__case=case))}),
        'investigate': ('Investigate current evidence', {'plan': forms.ModelChoiceField(plans)}),
    }
    return [(action,label,type('ColdCommand',(forms.Form,),{'action':forms.CharField(initial=action,widget=forms.HiddenInput),**fields})(data if data and data.get('action') == action else None)) for action,(label,fields) in definitions.items()]


@login_required
@transaction.atomic
def home(request):
    d.control()
    d.provisioned(request.user, 'read')
    response = render(request, 'workflows/cold_home.html', {'cases': visible_cases(request.user)})
    response['Cache-Control'] = 'no-store'
    return response


@login_required
@transaction.atomic
def workbench(request, case_id):
    c = accessible_case(request.user, case_id)
    d.access(request.user, c, locked=request.method == 'GET')
    forms_list = commands(c, request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        try:
            f = next((f for action,_,f in forms_list if action == request.POST.get('action')), None)
            if f is None or not f.is_valid():
                raise ValidationError('Valid typed cold recovery command required')
            v = f.cleaned_data.copy()
            action = v.pop('action')
            if action == 'capture':
                ref = v.pop('reference')
                d.capture(request.user, c.pk, ref, v)
            elif action == 'policy':
                d.access(request.user, c, 'configure')
                draft_operator_policy(request.user, c.pk, COMPONENT, v['content'], v['evidence_id'].pk, timezone.now())
            elif action == 'evidence':
                d.access(request.user, c, 'configure')
                add_evidence(request.user, c.pk, 'policy_decision', v['body'], v['source'])
            elif action == 'review':
                v['plan_id'] = v.pop('plan').pk
                d.review(request.user, c.pk, **v)
            elif action == 'reserve':
                d.reserve(request.user, c.pk, v['plan'].pk)
            elif action == 'retry':
                d.retry(request.user, c.pk, v['job'].pk)
            else:
                return JsonResponse(agent.investigate(request.user, c.pk, v['plan'].pk), headers={'Cache-Control':'no-store'})
            messages.success(request, 'Fresh recovery history recorded')
            return redirect('cold_recovery', case_id=c.pk)
        except (ValidationError, ValueError, KeyError):
            messages.error(request, 'Command held: check typed criteria, exact deployment references and current evidence')
    d.access(request.user, c)
    response = render(request, 'workflows/cold_recovery.html', {'case':c, 'commands':forms_list,
        'policy_status':resolve(COMPONENT,c).status, 'value_schema':json.dumps(VALUE,indent=2),
        'plans':d.Plan.objects.filter(case=c).order_by('-pk')[:20], 'jobs':d.Job.objects.filter(plan__case=c).order_by('-pk')[:30]})
    response['Cache-Control'] = 'no-store'
    return response


@login_required
@transaction.atomic
def report(request, case_id, plan_id):
    c = accessible_case(request.user, case_id)
    get_object_or_404(d.Plan, case=c, pk=plan_id)
    return JsonResponse(d.report(request.user, c.pk, plan_id), headers={'Cache-Control':'no-store'})


@login_required
@transaction.atomic
def policy(request, case_id):
    c = accessible_case(request.user, case_id)
    d.access(request.user, c, 'configure' if request.method == 'POST' else 'read')
    response = policy_workbench(request, case_id)
    response['Cache-Control'] = 'no-store'
    return response
