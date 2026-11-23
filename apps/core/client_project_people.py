"""Named project contacts, separate from the primary contact used by workflow decisions."""
from uuid import uuid4

from django import forms
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Exists, OuterRef

from .evidence_access import public_evidence
from .models import ClientProjectPersonRevision, Evidence
from .services import bump, event, lock_case


PURPOSE = 'project_person'
FIELDS = ('name', 'role', 'email')
PROOF_KINDS = ('engagement_source', 'policy_decision')
PAGE_SIZE = 25


def current(case):
    scope = ClientProjectPersonRevision.objects.filter(case=case)
    successor = scope.filter(previous_id=OuterRef('pk'))
    return scope.filter(~Exists(successor))


class PersonForm(forms.Form):
    entry = forms.ModelChoiceField(queryset=ClientProjectPersonRevision.objects.none(), widget=forms.HiddenInput,
                                   required=False)
    name = forms.CharField(label='Contact name', max_length=160)
    role = forms.CharField(label='Role at the client', max_length=100)
    email = forms.EmailField(label='Email', required=False)
    evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Evidence for this contact')
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, case, rows, data, selected):
        initial = {'revision': case.revision}
        if selected:
            initial.update({name: getattr(selected, name) for name in FIELDS})
            initial.update(entry=selected.pk, evidence=selected.evidence_id)
        super().__init__(data, initial=initial, auto_id='id_person_%s')
        ids = [row.pk for row in rows]
        self.fields['entry'].queryset = current(case).filter(pk__in=ids)
        proofs = public_evidence(case.evidence.filter(kind__in=PROOF_KINDS))
        recent = list(proofs.order_by('-pk').values_list('pk', flat=True)[:30])
        if selected:
            recent.append(selected.evidence_id)
        elif self.is_bound:
            # Existing prepared source may fall outside recent options; it is still scoped on read and write.
            submitted = self.data.get('evidence', '')
            if submitted.isascii() and submitted.isdecimal() and len(submitted) <= 18:
                recent.append(int(submitted))
        self.fields['evidence'].queryset = proofs.filter(pk__in=recent).only('kind', 'version', 'source').order_by('-pk')
        self.fields['evidence'].label_from_instance = lambda proof: f'#{proof.pk} · {proof.source}'


@transaction.atomic
def save(actor, case, fields):
    from .client_contacts import authorize

    case = lock_case(actor, case.pk, 'engagement.capture', fields['revision'])
    authorize(actor, case, 'project')
    proof = fields['evidence']
    if not public_evidence(case.evidence.filter(pk=proof.pk, kind__in=PROOF_KINDS)).exists():
        raise ValidationError('Choose source evidence from this project.')
    previous = current(case).filter(pk=fields['entry'].pk).first() if fields['entry'] else None
    if fields['entry'] and previous is None:
        raise ValidationError('This contact changed. Open its current record before saving.')
    values = {name: fields[name] for name in FIELDS}
    if previous and previous.evidence_id == proof.pk and all(getattr(previous, name) == value for name, value in values.items()):
        return previous
    record = ClientProjectPersonRevision.objects.create(case=case, previous=previous, evidence=proof, actor=actor,
        person_key=previous.person_key if previous else uuid4(), number=previous.number + 1 if previous else 1, **values)
    event(actor, case, 'client.project_person_recorded', person=record.pk)
    bump(case)
    return record


def panel(case, *, can_edit, data=None, selection='', number=None):
    page = Paginator(current(case).select_related('actor').order_by('name', 'pk'), PAGE_SIZE).get_page(number)
    entries = list(page.object_list)
    selected = next((row for row in entries if str(row.pk) == selection), None)
    return {'entries': entries, 'selected': selected, 'page': page,
            'form': PersonForm(case, entries, data, selected) if can_edit else None}
