"""Workspace setup areas over the existing versioned policy registry."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from apps.identity.models import Grant
from apps.identity.services import require, visible_cases
from apps.identity.intake import options
from apps.policy.services import resolve
from apps.policy.hrfinance_validators import FIELDS

from .views import accessible_case
from .presentation import HR_FIELD_LABELS as FIELD_LABELS


class DisclosureFieldsForm(forms.Form):
    fields = forms.MultipleChoiceField(label='Fields allowed in the HR handoff',
        choices=[(key, FIELD_LABELS[key]) for key in FIELDS], widget=forms.CheckboxSelectMultiple)
    evidence = forms.ChoiceField(label='Decision evidence')
    reason = forms.CharField(label='Reason for the change', max_length=1000,
                             widget=forms.Textarea(attrs={'rows': 3}))
    effective_from = forms.DateTimeField(label='Effective from',
        widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M:%S', attrs={'type': 'datetime-local', 'step': 1}))
    base_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    latest_revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


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
    'payroll': ('Payroll visibility', (
        ('F35.disclosure_rules', 'HR fields and recipients'),
        ('F16.input_access_rules', 'Restricted payroll readers'),
        ('F18.reporting_rules', 'Staff-cost report audience'),
    )),
}


@login_required
@require_safe
@never_cache
def index(request):
    management = {(row.tenant, row.value['classification'] == 'synthetic'): row
                  for row in options(request.user, 'manage_access')}
    rules = Grant.objects.filter(user=request.user, case_id=OuterRef('pk'),
                                 action='policy.read', active=True)
    cases = visible_cases(request.user).annotate(can_read_rules=Exists(rules))
    allowed = Q(can_read_rules=True)
    for tenant, synthetic in management:
        allowed |= Q(tenant=tenant, synthetic=synthetic)
    cases = cases.filter(allowed)
    search = request.GET.get('q', '').strip()[:120]
    if search:
        cases = cases.filter(title__icontains=search)
    page = Paginator(cases.order_by('title', 'pk'), 25).get_page(request.GET.get('page'))
    for case in page:
        authority = management.get((case.tenant, case.synthetic))
        case.can_manage_accounts = authority is not None
        case.can_invite_staff = bool(authority and authority.value.get('staff_lifecycle'))
    return render(request, 'design/setup_index.html', {
        'workspaces': page, 'search': search, 'observed_at': timezone.now(),
    })


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def overview(request, case_id):
    case = accessible_case(request.user,case_id)
    require(request.user,case,'policy.read')
    area = request.GET.get('area','roles')
    if area not in AREAS:
        raise Http404('Choose a workspace settings area.')
    if request.method == 'POST' and area != 'payroll':
        return HttpResponseNotAllowed(['GET', 'HEAD'])
    title, components = AREAS[area]
    items = []
    for key, label in components:
        resolved = resolve(key,case)
        saved = resolved.configuration if resolved.status=='ACTIVE' else None
        items.append({'label':label,'status':resolved.status,'revision':saved.revision if saved else None})
    can_configure = Grant.objects.filter(case=case,user=request.user,active=True,action='policy.configure').exists()
    disclosure = None
    form = None
    visibility_draft = None
    disclosure_hold = None
    field_rows = []
    role_rows = []
    role_hold = None
    if area == 'roles':
        from apps.policy.role_assignments import report
        try:
            assignments = report(request.user, case.pk)['assignments']
        except (PermissionDenied, ValidationError):
            role_hold = 'The current assignments need authorised review.'
        else:
            people = get_user_model().objects.only('id', 'username', 'first_name', 'last_name').in_bulk(
                [row['user_id'] for row in assignments])
            role_rows = [{'person': people[row['user_id']], 'roles': row['roles'],
                          'eligible': row['eligible_role_bundle']} for row in assignments]
    if area == 'payroll':
        from apps.policy.hrfinance_validators import DISCLOSURE, DISCLOSURE_FORMAT_V2
        from apps.policy.models import Configuration
        from apps.policy.services import reference_values

        current = resolve(DISCLOSURE, case)
        if current.status == 'ACTIVE':
            from apps.policy.impact import configuration
            try:
                configuration(request.user, case.pk, current.configuration.pk)
            except PermissionDenied:
                disclosure_hold = 'Current disclosure requires access to its original rules.'
        if current.status == 'ACTIVE':
            disclosure = reference_values(current.configuration)[0] if not disclosure_hold else None
            if disclosure:
                supported = disclosure.get('source_fields', FIELDS)
                field_rows = [{'label': label, 'included': key in disclosure['allowed_fields'],
                               'supported': key in supported} for key, label in FIELD_LABELS.items()]
            latest = Configuration.objects.filter(case=case, component=DISCLOSURE).order_by('-revision').first()
            if latest.pk != current.configuration.pk:
                state = latest.states.order_by('-pk').first().state
                if state in {'draft', 'validated'}:
                    visibility_draft = {'id': latest.pk, 'revision': latest.revision, 'state': state}
            if can_configure and disclosure:
                form = DisclosureFieldsForm(request.POST if request.method == 'POST' else None, initial={
                    'fields': disclosure['allowed_fields'], 'base_id': current.configuration.pk,
                    'latest_revision': latest.revision, 'revision': case.revision,
                    'effective_from': timezone.localtime().replace(microsecond=0),
                })
                if disclosure.get('format') == DISCLOSURE_FORMAT_V2:
                    form.fields['fields'].choices = [(key, FIELD_LABELS[key]) for key in disclosure['source_fields']]
                proofs = case.evidence.filter(kind='policy_decision').defer('body').order_by('-pk')[:30]
                form.fields['evidence'].choices = [(row.pk, f'Version {row.version} · {row.source[:120]}') for row in proofs]
        if request.method == 'POST':
            require(request.user, case, 'policy.configure')
            if form and form.is_valid():
                if set(request.POST) - set(form.fields) - {'csrfmiddlewaretoken'}:
                    form.add_error(None, 'Use the displayed fields for this proposal.')
                else:
                    from apps.policy.hrfinance_drafts import draft_disclosure_fields
                    data = form.cleaned_data
                    try:
                        draft = draft_disclosure_fields(request.user, case.pk, data['base_id'],
                            data['latest_revision'], data['fields'], int(data['evidence']),
                            data['effective_from'], data['revision'], reason=data['reason'])
                    except ValidationError:
                        form.add_error(None, 'Check the required staff, business-unit and membership-date fields. Pay and currency must be selected together. Refresh if the source or rule has changed.')
                    else:
                        messages.success(request, f'Visibility draft {draft.revision} saved. Review and activate it in the rule versions.')
                        return redirect(request.path + '?area=payroll')
            elif form is None:
                messages.error(request, disclosure_hold or 'Configure the HR source and disclosure terms before proposing its fields.')
    return render(request,'design/setup_overview.html',{'case':case,'area':area,'title':title,'items':items,
                  'can_configure':can_configure,'navigation':[(key,value[0]) for key,value in AREAS.items()],
                  'disclosure':disclosure, 'visibility_form':form, 'visibility_draft':visibility_draft,
                  'disclosure_hold':disclosure_hold,
                  'field_rows':field_rows,
                  'role_rows':role_rows, 'role_hold':role_hold, 'observed_at':timezone.now()})


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def visibility_review(request, case_id, configuration_id):
    from apps.policy.hrfinance_drafts import disclosure_field_review, review_disclosure_fields

    case = accessible_case(request.user, case_id)
    require(request.user, case, 'policy.read')
    try:
        review = disclosure_field_review(request.user, case.pk, configuration_id)
    except ValidationError:
        messages.error(request, 'This proposal needs a current source and complete rule review.')
        return redirect('workspace_settings', case_id=case.pk)
    if request.method == 'POST':
        try:
            if set(request.POST) - {'csrfmiddlewaretoken'} != {'action', 'revision', 'state'}:
                raise ValidationError('Use the displayed review action.')
            review_disclosure_fields(request.user, case.pk, configuration_id, request.POST.get('state'),
                                     request.POST.get('action'), int(request.POST.get('revision', '0')))
        except (ValidationError, ValueError):
            messages.error(request, 'The review could not proceed. Check the current version and source before continuing.')
        else:
            messages.success(request, 'Visibility version activated.' if request.POST['action'] == 'activate'
                             else 'Visibility proposal checked and ready for activation.')
        return redirect('visibility_review', case_id=case.pk, configuration_id=configuration_id)
    permissions = set(Grant.objects.filter(case=case, user=request.user, active=True).values_list('action', flat=True))
    recipients = get_user_model().objects.filter(pk__in=review['proposed']['recipient_ids']).only(
        'id', 'username', 'first_name', 'last_name').order_by('username')
    rows = [{'label': label, 'current': key in review['original']['allowed_fields'],
             'proposed': key in review['proposed']['allowed_fields']} for key, label in FIELD_LABELS.items()]
    from apps.pmo.clocks import aware
    return render(request, 'design/visibility_review.html', {'case': case, 'review': review, 'rows': rows,
        'recipients': recipients, 'effective_at': aware(review['configuration'].envelope['effective_from']),
        'can_validate': review['current'] and review['state'] == 'draft' and 'policy.configure' in permissions,
        'can_activate': review['current'] and review['state'] == 'validated' and 'policy.activate' in permissions})
