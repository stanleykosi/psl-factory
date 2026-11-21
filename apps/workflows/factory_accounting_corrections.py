"""Preserve returned Finance review while starting its exact corrected import."""
from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit
from apps.core.services import event
from apps.documents.models import Publication
from apps.finance import analysis
from apps.finance.models import FinanceReview
from apps.identity.services import require

from . import factory, factory_accounting as accounting
from .models import FactoryWork, TaskEvent


LINKED = 'factory.accounting_correction_linked'


def successor(work):
    return Audit.objects.filter(case_id=work.case_id, action=LINKED, data__previous_work=work.pk).first()


def predecessor(work):
    return Audit.objects.filter(case_id=work.case_id, action=LINKED, data__work=work.pk).first()


def url(work):
    return reverse('factory_create') + '?' + urlencode({
        'definition': accounting.DEFINITION, 'case': work.case_id, 'correction': work.pk,
    })


def selection(actor, work):
    from .factory_accounting_intake import authority

    authority(actor, work.case)
    factory.access(actor, work.case, 'factory.execute', accounting.DEFINITION)
    if work.actor_id != actor.pk:
        raise PermissionDenied('The original accounting preparer must submit this corrected source.')
    if (work.status != 'followup_needed' or work.cancel_requested
            or work.lease_until and work.lease_until > timezone.now()
            or Publication.objects.filter(factory_work=work).exists() or successor(work)):
        raise ValidationError('The original work is unavailable for this source correction.')
    source = accounting.source_for(work)
    if source.actor_id != actor.pk:
        raise PermissionDenied('The exact source owner must submit this corrected extract.')
    decision = FinanceReview.objects.filter(case=work.case, purpose='source', source=source).select_related('actor').order_by('-pk').first()
    if (decision is None or decision.verdict != 'return' or decision.actor_id == actor.pk
            or not TaskEvent.objects.filter(
                task__case=work.case, task__kind='factory_accounting_review', task__status='returned',
                task__context__work=work.pk, task__context__purpose='source', task__context__packet__target=source.pk,
                task__context__packet__head=work.source_head_id, actor_id=decision.actor_id,
                action='factory.accounting_review', data__native_review=decision.pk, data__verdict='return',
            ).exists()):
        raise ValidationError('Choose the exact work whose current trial-balance source was returned.')
    require(decision.actor, work.case, 'finance.review')
    current = analysis.review_authority(decision.actor, work.case, 'source', decision.role, 'return', source.actor_id)
    if {key: value for key, value in current.items() if key != 'D05.decision_action_matrix'} != {
            key: value for key, value in decision.authority.items() if key != 'D05.decision_action_matrix'}:
        raise ValidationError('The authority for the original return changed. Review the source first.')
    batch = source.batch
    dimensions = {(row.get('period'), row.get('currency')) for row in batch.rows}
    if len(dimensions) != 1 or any(not item for item in next(iter(dimensions), ())):
        raise ValidationError('The returned file must identify one exact period and currency.')
    period, currency = dimensions.pop()
    return {
        'work': work.pk, 'head': work.source_head_id, 'source': source.pk, 'batch': batch.pk,
        'sha256': batch.source_sha256, 'decision': decision.pk, 'entity': source.entity,
        'period': period, 'currency': currency, 'accounting_basis': source.accounting_basis,
        'reason': decision.note,
    }


def locked_selection(actor, case, correction):
    if (not isinstance(correction, dict) or set(correction) != {'work', 'head', 'decision'}
            or any(type(pk) is not int or not 0 < pk <= 9223372036854775807 for pk in correction.values())):
        raise ValidationError('Exact returned work and decision references are required.')
    # Existing workers lease a work row before locking its case. The intake
    # already holds the case and must never wait for that worker to release it.
    old = FactoryWork.objects.select_for_update(of=('self',), skip_locked=True).select_related('case').filter(
        case=case, definition=accounting.DEFINITION, pk=correction['work']).first()
    if old is None:
        raise ValidationError('The original returned work is unavailable or busy. Refresh before continuing.')
    pin = selection(actor, old)
    if any(pin[key] != value for key, value in correction.items()):
        raise ValidationError('The original returned source changed. Open its current correction controls.')
    return pin


def check_file(pin, context, sha256):
    if not isinstance(context, dict) or any(pin[key] != context.get(key) for key in ('entity', 'period', 'currency', 'accounting_basis')):
        raise ValidationError('Use a corrected extract for the same entity, period, currency and accounting basis.')
    if pin['sha256'] == sha256:
        raise ValidationError('Select a changed trial-balance extract. The returned file remains in its history.')


def link(actor, case, pin, receipt, work, source):
    if work.pk == pin['work'] or source.batch_id == pin['batch'] or predecessor(work):
        raise ValidationError('Choose a new corrected source that has no earlier successor relationship.')
    return event(actor, case, LINKED, previous_work=pin['work'], previous_source=pin['source'],
                 previous_head=pin['head'], return_decision=pin['decision'], receipt=receipt.pk,
                 work=work.pk, source=source.pk, new_batch=source.batch_id)
