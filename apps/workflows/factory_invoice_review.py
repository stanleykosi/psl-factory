"""Finance decision context and comments for an exact invoice review packet."""
from collections import defaultdict

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.urls import reverse

from apps.core.presentation import workspace_name
from apps.core.read_observation import read_observation
from apps.core.services import lock_case
from apps.core.workbench import granted
from apps.documents.contracts import digest
from apps.finance import invoices
from apps.finance.fixed_charge import preparation_access
from . import factory, factory_routing
from .models import FactoryWork, HumanTask, TaskEvent


COMMENT = 'factory.invoice_comment'
ASSIGNMENT_ALERT_LIMIT = 8
ASSIGNMENT_CANDIDATE_LIMIT = 24


@read_observation
def assigned_alerts(actor):
    """Point eligible reviewers to a current decision without including its contents."""
    if not actor.is_authenticated or not actor.is_active:
        return []
    cases = granted(actor, ['factory.read', 'finance.read', 'finance.invoice.review'])
    candidates = list(HumanTask.objects.filter(
        case_id__in=cases.values('pk'), kind='factory_review', status='open',
        context__routing_at_creation__eligible_principals__contains=[actor.pk],
    ).filter(Q(claimed_by=None) | Q(claimed_by=actor)).order_by('-pk')[:ASSIGNMENT_CANDIDATE_LIMIT])
    work_ids = {task.context.get('work') for task in candidates if type(task.context.get('work')) is int}
    works = FactoryWork.objects.filter(
        definition='pmo-finance/v1', invoice__isnull=False, cancel_requested=False, status__in=['ready', 'waiting'],
    ).select_related('case', 'invoice__preparation', 'invoice__actor').in_bulk(work_ids)
    rows = []
    for task in candidates:
        work_id = task.context.get('work')
        work = works.get(work_id) if type(work_id) is int else None
        if (work is None or work.case_id != task.case_id or not isinstance(task.context.get('packet'), dict)
                or not (task.factory_key or '').startswith(f'factory:{work.pk}:')):
            continue
        try:
            factory.access(actor, work.case)
            preparation_access(actor, work.invoice.preparation)
            factory.profile(work, recovery=True)
            invoices.current(work.invoice)
            factory.assert_review_task_current(work, task)
        except (PermissionDenied, ValidationError):
            continue
        rows.append({'key': digest(['invoice-review-task', task.pk]), 'label': 'Invoice needs your review',
                     'subject': workspace_name(work.case), 'detail': '',
                     'url': reverse('factory_invoice_decision', args=[work.pk]), 'group': 'action'})
        if len(rows) == ASSIGNMENT_ALERT_LIMIT:
            break
    return rows


def context(actor, row):
    work = row['work']
    invoice = work.invoice
    routing = row.get('routing', {})
    eligible = routing.get('eligible_principals', [])
    review_tasks = [task for task in row['tasks'] if task.kind == 'factory_review']
    recipient_ids = set()
    for task in review_tasks:
        packet = task.context.get('packet', {})
        recorded = task.context.get('routing_at_creation', {}).get('eligible_principals', [])
        task.can_read_invoice_destination = actor.pk in eligible and actor.pk in recorded
        task.display_packet = packet if task.can_read_invoice_destination else {
            key: value for key, value in packet.items() if key != 'recipient_id'
        }
        if task.can_read_invoice_destination and type(packet.get('recipient_id')) is int:
            recipient_ids.add(packet['recipient_id'])
    if invoice is None:
        return None
    preparation_access(actor, invoice.preparation)
    successor = invoices.successor_drafts(invoice).select_related('preparation').order_by('-pk').first()
    if successor:
        try:
            preparation_access(actor, successor.preparation)
        except (PermissionDenied, ValidationError):
            successor = None
    comparison = None
    if successor is None and row['review_needs_update'] and actor.pk in eligible:
        comparison = changed_recipient(invoice, review_tasks)
        if comparison is not None:
            recipient_ids.update(comparison.values())
    recipients = recipient_names(work.case, recipient_ids)
    for task in review_tasks:
        if task.can_read_invoice_destination:
            task.recipient_name = recipients.get(task.context['packet'].get('recipient_id'))
    if comparison is not None:
        comparison = {label: recipients.get(pk) for label, pk in comparison.items()}
    open_review = any(task.status == 'open' for task in review_tasks)
    waiting_for_other = (open_review and bool(eligible) and not row['review_needs_update']
                         and actor.pk not in eligible and work.status in {'ready', 'waiting'})
    reviewers = []
    if waiting_for_other:
        routed = (get_user_model().objects.filter(pk__in=eligible).order_by('pk')
                  .only('username', 'first_name', 'last_name')[:10])
        reviewers = [user.get_full_name() or user.username for user in routed]
    return {'successor': successor, 'recipient_change': comparison, 'prepared_here': invoice.actor_id == actor.pk,
            'waiting_for_other': waiting_for_other, 'reviewers': reviewers}


def changed_recipient(invoice, review_tasks):
    earlier = next((task.context['packet'] for task in reversed(review_tasks)
                    if task.can_read_invoice_destination and task.status in ('open', 'completed')
                    and task.context['packet'].get('invoice') == invoice.pk), None)
    if earlier is None:
        return None
    try:
        current = invoices.review_packet(invoice)
    except (ValidationError, PermissionDenied):
        return None
    old_id, new_id = earlier.get('recipient_id'), current.get('recipient_id')
    if (type(old_id) is int and type(new_id) is int and old_id != new_id
            and earlier.get('payload_hash') == current['payload_hash']):
        return {'earlier': old_id, 'current': new_id}
    return None


def recipient_names(case, recipient_ids):
    users = get_user_model().objects.filter(
        pk__in=recipient_ids, is_active=True, grant__case=case, grant__active=True,
        grant__action='finance.invoice.receive',
    ).only('username', 'first_name', 'last_name').distinct()
    return {user.pk: user.get_full_name() or user.username for user in users}


@transaction.atomic
def comment(actor, work_id, task_id, revision, body):
    work = FactoryWork.objects.select_for_update(of=('self',)).select_related('invoice__preparation').get(pk=work_id)
    if work.definition != 'pmo-finance/v1' or work.invoice_id is None:
        raise ValidationError('Choose an exact invoice review to comment on.')
    task = HumanTask.objects.select_for_update().filter(case_id=work.case_id, pk=task_id, kind='factory_review',
                                                       factory_key__startswith=f'factory:{work.pk}:').first()
    case = lock_case(actor, work.case_id, 'finance.read')
    factory.access(actor, case)
    preparation_access(actor, work.invoice.preparation)
    if (task is None or task.revision != revision or task.status != 'open' or work.cancel_requested
            or work.status not in {'ready', 'waiting'}):
        raise ValidationError('Review the current decision before adding a comment.')
    factory.assert_review_task_current(work, task)
    if actor.pk in factory_routing.require_ready(work)['eligible_principals']:
        raise ValidationError('Use the assigned Finance decision to record your rationale.')
    body = body.strip() if isinstance(body, str) else ''
    if not 1 <= len(body) <= 2000:
        raise ValidationError('Enter a comment of at most 2,000 characters.')
    return TaskEvent.objects.get_or_create(task=task, actor=actor, action=COMMENT,
                                           data={'body': body, 'invoice': work.invoice_id})[0]


def annotate_comments(row):
    work = row['work']
    tasks = {task.pk: task for task in row['tasks']
             if task.kind == 'factory_review' and task.context['packet'].get('invoice') == work.invoice_id}
    comments = defaultdict(list)
    recorded = TaskEvent.objects.filter(task_id__in=tasks, action=COMMENT, data__invoice=work.invoice_id)
    for item in recorded.select_related('actor').order_by('-pk')[:20]:
        comments[item.task_id].append(item)
    for task in tasks.values():
        task.comments = comments[task.pk]
        task.can_comment = (row['invoice_context']['waiting_for_other'] and task.status == 'open'
                            and not row['invoice_context']['successor'] and not work.cancel_requested
                            and work.status in {'ready', 'waiting'})
