"""Contact records scoped to projects and exact native billing customers."""
import re

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from apps.finance.fixed_charge import case_access
from apps.finance import client_billing
from apps.finance.models import BillingCoverage
from apps.identity.services import active_case_grants, require, visible_cases

from .evidence_access import public_evidence
from . import client_billing_identity
from . import client_directory
from . import client_project_people
from .models import ClientContactRevision, Evidence
from .read_budget import ReadLimit
from .services import bump, event, lock_case


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
    term = request.GET.get('q', '').strip()[:100]
    billing = request.GET.get('billing', '')
    if billing not in dict(client_directory.BILLING_FILTERS):
        billing = ''
    visible = client_directory.visible_links(request.user)
    group = request.GET.get('client', '')
    if group:
        if not re.fullmatch(r'[a-f0-9]{64}', group):
            raise Http404('Choose an available client.')
        label, members = client_directory.group_members(client_directory.active_links(visible), group, request.GET.get('page'))
        if not label:
            raise Http404('Choose an available client.')
        return render(request, 'design/client_directory_group.html',
                      {'label': label, 'group': group, 'members': members, 'query': term, 'billing': billing})
    links = client_directory.active_links(visible) if visible.exists() else None
    projects = client_directory.page(request.user, term, billing, request.GET.get('page'), links)
    groups = client_directory.grouped_page(links, term, billing, request.GET.get('clients_page')) if links is not None else None
    return render(request, 'design/clients.html',
                  {'projects': projects, 'groups': groups, 'query': term, 'billing': billing,
                   'billing_filters': client_directory.BILLING_FILTERS})


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def project(request, case_id):
    case = get_object_or_404(visible_cases(request.user), kind='project', pk=case_id)
    actions = {action for _, action in active_case_grants(request.user, [case.pk])}
    return_work=None
    try:
        selected_work=int(request.GET.get('work',''))
        if 0<selected_work<=9223372036854775807:
            from apps.workflows.models import FactoryWork
            from apps.workflows.factory import access
            access(request.user,case,'factory.read','engagement/v1')
            return_work=FactoryWork.objects.filter(pk=selected_work,case=case,definition='engagement/v1').values_list('pk',flat=True).first()
    except (ValueError,PermissionDenied,ValidationError):pass
    selected = request.POST.get('purpose') if request.method == 'POST' else None
    targets = {client_billing_identity.PURPOSE: 'billing', client_project_people.PURPOSE: 'project'}
    target = targets.get(selected, selected)
    if request.method == 'POST':
        if target not in WRITE or WRITE[target] not in actions:
            raise PermissionDenied
    sections = []
    for purpose in READ:
        try:
            authorize(request.user, case, purpose)
        except (PermissionDenied, ValidationError):
            if target == purpose:
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
                    return redirect(request.path+'?work='+str(return_work)) if return_work else redirect('design_client_project', case.pk)
        sections.append({'purpose': purpose, 'label': 'Billing contacts' if purpose == 'billing' else 'Project contact',
                         'entries': entries, 'form': form})
    if not sections:
        raise PermissionDenied
    people = None
    if any(section['purpose'] == 'project' for section in sections):
        selected_person = selected == client_project_people.PURPOSE
        people = client_project_people.panel(case, can_edit=WRITE['project'] in actions,
            data=request.POST if selected_person else None, selection=request.GET.get('project_contact', ''),
            number=request.GET.get('people_page'))
        person_form = people['form']
        if selected_person and person_form.is_valid():
            try:
                client_project_people.save(request.user, case, person_form.cleaned_data)
            except ValidationError as exc:
                person_form.add_error(None, exc)
            else:
                messages.success(request, 'Project contact recorded.')
                return redirect(request.path+'?work='+str(return_work)) if return_work else redirect('design_client_project', case.pk)
    billing = None
    billing_limited = False
    identity = None
    billing_contacts = next((section['entries'] for section in sections if section['purpose'] == 'billing'), None)
    if billing_contacts is not None:
        identity_post = selected == client_billing_identity.PURPOSE
        identity = client_billing_identity.panel(case, can_edit=WRITE['billing'] in actions,
                                                 data=request.POST if identity_post else None)
        if identity_post:
            form = identity['form']
            if form and form.is_valid():
                try:
                    client_billing_identity.save(request.user, case, form.cleaned_data)
                except ValidationError as exc:
                    form.add_error(None, exc)
                else:
                    messages.success(request, 'Billing details recorded.')
                    return redirect(request.path+'?work='+str(return_work)) if return_work else redirect('design_client_project', case.pk)
            elif form is None:
                messages.error(request, 'Record current billing coverage before adding these details.')
        try:
            billing = client_billing.overview(request.user, case)
        except ReadLimit:
            billing_limited = True
        except (PermissionDenied, ValidationError):
            billing = None
        if billing:
            contacts = {contact.customer for contact in billing_contacts if contact.email}
            for cover in billing['coverage']:
                cover.contact_recorded = cover.customer in contacts
    return render(request, 'design/client_project.html', {'case': case, 'sections': sections, 'billing': billing,
                                                         'billing_limited': billing_limited, 'return_work': return_work,
                                                         'billing_identity': identity, 'project_people': people})
