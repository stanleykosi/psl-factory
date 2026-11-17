"""Workspace setup areas over the existing versioned policy registry."""
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.services import resolve

from .views import accessible_case


AREAS = {
    'roles': ('Roles and rules', (
        ('D05.role_principal_assignments', 'Assigned roles and eligibility'),
        ('D05.delegation_rules', 'Delegation'),
        ('D05.decision_action_matrix', 'Decision authority'),
    )),
    'finance': ('Finance rules', (
        ('D12.contract_version_ref', 'Signed agreement'),
        ('D12.stage_terms', 'Stage billing terms'),
        ('D13.payment_denominator_rule_ref', 'Payment assessment basis'),
        ('D13.qualifying_funds_rule_ref', 'Qualifying funds'),
    )),
    'delivery': ('Delivery rules', (
        ('D11.hypercare_criteria_ref', 'Hypercare acceptance'),
        ('D11.template_storage_retention_rules', 'Document retention'),
        ('D11.adapter_configuration_refs', 'Reviewed delivery routes'),
    )),
    'payroll': ('Payroll visibility', ()),
}


@login_required
@require_safe
@never_cache
def overview(request, case_id):
    case = accessible_case(request.user,case_id)
    require(request.user,case,'policy.read')
    area = request.GET.get('area','roles')
    if area not in AREAS:
        raise Http404('Choose a workspace settings area.')
    title, components = AREAS[area]
    items = []
    for key, label in components:
        resolved = resolve(key,case)
        saved = resolved.configuration if resolved.status=='ACTIVE' else None
        items.append({'label':label,'status':resolved.status,'revision':saved.revision if saved else None})
    can_configure = Grant.objects.filter(case=case,user=request.user,active=True,action='policy.configure').exists()
    return render(request,'design/setup_overview.html',{'case':case,'area':area,'title':title,'items':items,
                  'can_configure':can_configure,'navigation':[(key,value[0]) for key,value in AREAS.items()]})
