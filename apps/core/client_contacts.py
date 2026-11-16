"""Contact records scoped to projects and exact native billing customers."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from apps.finance.fixed_charge import case_access
from apps.finance.models import BillingCoverage
from apps.identity.services import active_case_grants, require, visible_cases

from .evidence_access import public_evidence
from .models import ClientContactRevision, Evidence
from .services import bump, event, lock_case
from .workbench import granted


READ = {'project': 'engagement.read', 'billing': 'finance.read'}
WRITE = {'project': 'engagement.capture', 'billing': 'finance.billing.register'}
PROOFS = {'project': ('engagement_source', 'policy_decision'), 'billing': ('billing_coverage', 'policy_decision')}


def customers(case):
    return BillingCoverage.objects.filter(case=case).order_by().values_list('customer', flat=True).distinct()


def authorize(actor, case, purpose):
    require(actor, case, 'case.read')
    require(actor, case, READ[purpose])
    if purpose == 'billing':
        case_access(actor, case)


class ContactForm(forms.Form):
    customer = forms.ChoiceField(label='Billing customer', required=False)
    client_name = forms.CharField(label='Client name', max_length=160)
    name = forms.CharField(label='Contact name', max_length=160)
    email = forms.EmailField(required=False)
    role = forms.CharField(label='Role at the client', max_length=100, required=False)
    evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Evidence for this contact')
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, case, purpose, data=None, initial=None):
        super().__init__(data, initial={'revision': case.revision, **(initial or {})}, auto_id=f'id_{purpose}_%s')
        self.fields['customer'].choices = [(name, name) for name in customers(case).order_by('customer')[:100]] if purpose == 'billing' else []
        if purpose == 'billing':
            self.fields['customer'].required = True
            self.fields['email'].required = True
        else:
            self.fields['customer'].widget = forms.HiddenInput()
        choices = public_evidence(case.evidence.filter(kind__in=PROOFS[purpose])).defer('body')
        self.fields['evidence'].queryset = choices.filter(pk__in=choices.order_by('-pk').values('pk')[:25]).order_by('-pk')


@transaction.atomic
def save(actor, case, purpose, fields):
    authorize(actor, case, purpose)
    case = lock_case(actor, case.pk, WRITE[purpose], fields['revision'])
    authorize(actor, case, purpose)
    proof = fields['evidence']
    if not public_evidence(case.evidence.filter(pk=proof.pk, kind__in=PROOFS[purpose])).exists():
        raise ValidationError('Select evidence from this workspace.')
    customer = fields['customer']
    if purpose == 'project' and customer:
        raise ValidationError('Project contacts belong to this project.')
    if purpose == 'billing' and not customers(case).filter(customer=customer).exists():
        raise ValidationError('Choose a billing customer on this project.')
    records = ClientContactRevision.objects.filter(case=case, purpose=purpose, customer=customer)
    previous = records.order_by('-number').first()
    values = {key: fields[key] for key in ('client_name', 'name', 'email', 'role')}
    if previous and all(getattr(previous, k) == v for k, v in values.items()) and previous.evidence_id == proof.pk:
        return previous
    record = records.create(case=case, purpose=purpose, customer=customer, evidence=proof, actor=actor,
                            number=previous.number + 1 if previous else 1, **values)
    event(actor, case, 'client.contact_recorded', contact=record.pk, purpose=purpose)
    bump(case)
    return record


@login_required
@require_safe
@never_cache
def index(request):
    project_grants = granted(request.user, ['engagement.read'])
    recorded = ClientContactRevision.objects.filter(case_id=OuterRef('pk'), purpose='project', case__in=project_grants).order_by('-number')
    query = (project_grants | granted(request.user, ['finance.read'])).annotate(client_name=Subquery(recorded.values('client_name')[:1]))
    term = request.GET.get('q', '').strip()[:100]
    if term:
        query = query.filter(Q(title__icontains=term) | Q(client_name__icontains=term))
    return render(request, 'design/clients.html', {'projects': query.filter(kind='project').order_by('title', 'pk')[:50], 'query': term})


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def project(request, case_id):
    case = get_object_or_404(visible_cases(request.user), kind='project', pk=case_id)
    actions = {action for _, action in active_case_grants(request.user, [case.pk])}
    selected = request.POST.get('purpose') if request.method == 'POST' else None
    if request.method == 'POST' and (selected not in WRITE or WRITE[selected] not in actions):
        raise PermissionDenied
    sections = []
    for purpose in READ:
        try:
            authorize(request.user, case, purpose)
        except (PermissionDenied, ValidationError):
            if selected == purpose:
                raise PermissionDenied
            continue
        records = ClientContactRevision.objects.filter(case=case, purpose=purpose).order_by('customer', '-number').distinct('customer')[:100]
        entries = list(records)
        form = None
        if WRITE[purpose] in actions:
            current = entries[0] if len(entries) == 1 else None
            initial = {field: getattr(current, field) for field in ('customer', 'client_name', 'name', 'email', 'role')} if current else {}
            form = ContactForm(case, purpose, request.POST if selected == purpose else None, initial)
            if selected == purpose and form.is_valid():
                try:
                    save(request.user, case, purpose, form.cleaned_data)
                except ValidationError as exc:
                    form.add_error(None, exc)
                else:
                    messages.success(request, 'Client contact recorded.')
                    return redirect('design_client_project', case.pk)
        sections.append({'purpose': purpose, 'label': 'Billing contacts' if purpose == 'billing' else 'Project contact',
                         'entries': entries, 'form': form})
    if not sections:
        raise PermissionDenied
    return render(request, 'design/client_project.html', {'case': case, 'sections': sections})
