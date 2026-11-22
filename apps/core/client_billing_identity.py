"""Versioned legal billing details for an exact native customer on a case."""

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from apps.finance.client_billing import current_coverages

from .evidence_access import public_evidence
from .models import ClientBillingIdentityRevision, Evidence
from .services import bump, event, lock_case


PURPOSE = 'billing_identity'
FIELDS = ('legal_name', 'billing_address', 'tax_reference')
SCOPE_LIMIT = 100
HISTORY_LIMIT = 30


class BillingIdentityForm(forms.Form):
    coverage = forms.ModelChoiceField(queryset=None, label='Customer and billing coverage')
    legal_name = forms.CharField(label='Legal business name', required=False, max_length=160)
    billing_address = forms.CharField(required=False, max_length=600, widget=forms.Textarea(attrs={'rows': 3}))
    tax_reference = forms.CharField(required=False, max_length=100)
    evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Evidence for these billing details')
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, case, data=None, initial=None):
        super().__init__(data, initial={'revision': case.revision, **(initial or {})}, auto_id='id_identity_%s')
        coverage = current_coverages(case).order_by('customer', 'reference', 'pk')
        self.fields['coverage'].queryset = coverage.filter(pk__in=coverage.values('pk')[:SCOPE_LIMIT])
        self.fields['coverage'].label_from_instance = lambda row: f'{row.customer} · {row.reference}'
        proofs = public_evidence(case.evidence.filter(kind='policy_decision') | case.evidence.filter(
            pk__in=self.fields['coverage'].queryset.values('evidence_id'), kind='billing_coverage'
        )).defer('body').order_by('-pk')
        # Current coverage proofs remain selectable even on cases with long decision histories.
        self.fields['evidence'].queryset = proofs.filter(Q(kind='billing_coverage') | Q(pk__in=proofs.filter(
            kind='policy_decision',
        ).values('pk')[:30]))
        self.fields['evidence'].label_from_instance = lambda proof: f'#{proof.pk} · {proof.source}'


@transaction.atomic
def save(actor, case, fields):
    from .client_contacts import authorize

    case = lock_case(actor, case.pk, 'finance.billing.register', fields['revision'])
    authorize(actor, case, 'billing')
    coverage = current_coverages(case).filter(pk=fields['coverage'].pk).first()
    if coverage is None:
        raise ValidationError('Choose current billing coverage from this workspace.')
    proof = fields['evidence']
    if not public_evidence(case.evidence.filter(pk=proof.pk)).filter(
            Q(kind='policy_decision') | Q(kind='billing_coverage', pk=coverage.evidence_id)).exists():
        raise ValidationError('Choose a decision from this workspace or the evidence for the selected coverage.')
    values = {name: fields[name] or None for name in FIELDS}
    if values['billing_address']:
        values['billing_address'] = values['billing_address'].replace('\r\n', '\n').replace('\r', '\n')
    records = ClientBillingIdentityRevision.objects.filter(case=case, customer_ref=coverage.customer)
    previous = records.order_by('-number').first()
    if (previous and previous.coverage_id == coverage.pk and previous.evidence_id == proof.pk
            and all(getattr(previous, name) == value for name, value in values.items())):
        return previous
    record = ClientBillingIdentityRevision.objects.create(
        case=case, coverage=coverage, customer_ref=coverage.customer, number=previous.number + 1 if previous else 1,
        previous=previous, evidence=proof, actor=actor, **values,
    )
    event(actor, case, 'client.billing_identity_recorded', identity=record.pk)
    bump(case)
    return record


def panel(case, *, can_edit, data=None):
    scopes = list(current_coverages(case).order_by('customer').values_list('customer', flat=True).distinct()[:SCOPE_LIMIT])
    query = ClientBillingIdentityRevision.objects.filter(case=case)
    latest = {row.customer_ref: row for row in query.filter(customer_ref__in=scopes)
              .select_related('actor').order_by('customer_ref', '-number').distinct('customer_ref')}
    earlier = query.exclude(pk__in=[row.pk for row in latest.values()]).select_related('actor').order_by('-pk')[:HISTORY_LIMIT]
    initial = {}
    if len(scopes) == 1:
        selected = current_coverages(case).filter(customer=scopes[0]).order_by('reference', 'pk').first()
        initial['coverage'] = selected.pk
        if scopes[0] in latest:
            initial.update({name: getattr(latest[scopes[0]], name) for name in FIELDS})
    return {'rows': [{'customer': customer, 'identity': latest.get(customer)} for customer in scopes],
            'earlier': earlier, 'form': BillingIdentityForm(case, data, initial) if can_edit and scopes else None}
