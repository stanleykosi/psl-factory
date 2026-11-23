"""Progress recorded by the worker, independent reviewers, and native delivery services."""
import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.agents.models import AgentRun
from apps.core.evidence_access import public_agent_runs
from apps.core.services import add_evidence, lock_case
from apps.core.templatetags.studio_ui import readable
from apps.documents.models import PublicationReceipt
from apps.finance.models import InvoiceDelivery, InvoiceReview
from apps.workflows.factory import uncertain_job
from apps.workflows.models import FactoryAttempt, FactoryWork, TaskEvent

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, Problem, array, choice, endpoint, nullable, obj
from .work import FINANCE_INVOICE, observed_work
from .work_proofs import KIND


FACTS = ('drafted', 'reviewed', 'approved', 'sent', 'receipt', 'verified')
OUTCOME = choice('delivered', 'not_delivered', 'unknown')
OBSERVATION_KIND = 'agent_private_delivery_observation_v1'
EFFECT = obj({'job_id': ID, 'job_type': TEXT})
OBSERVATION = obj({'id': ID, 'effect': EFFECT, 'outcome': OUTCOME, 'proof_id': ID, 'reason': TEXT, 'recorded_at': DATETIME})
STEPS = {
    'intake': 'Intake', 'execution': 'Agent and team work', 'decision': 'Human decision',
    'delivery': 'Delivery and receipt', 'verified': 'Verified result',
}


@endpoint(response=obj({
    'work_id': ID, 'as_of': DATETIME, 'next_step': TEXT, 'blocker': {'type': 'string'},
    'owner': nullable(TEXT),
    'station': obj({'key': choice(*STEPS), 'name': TEXT}),
    'stations': array(obj({'key': choice(*STEPS), 'name': TEXT})),
    'facts': obj(dict.fromkeys(FACTS, nullable(BOOLEAN))),
    'worker_history_url': TEXT, 'decision_history_url': TEXT, 'evidence_history_url': TEXT,
    'can_record_delivery_observation': BOOLEAN, 'delivery_observation_url': nullable(TEXT),
    'uncertain_effects': array(EFFECT),
    'last_activity': nullable(obj({
        'kind': TEXT, 'status': TEXT, 'at': DATETIME, 'agent_process': nullable(TEXT),
        'evidence_id': nullable(ID),
    })),
}), summary='Read observed work progress and independently recorded results')
def tracking(request, work_id):
    work, row, protected = observed_work(request.user, work_id)
    if protected.get('recipient_only') or protected.get('handoff'):
        raise Http404
    attempt = FactoryAttempt.objects.filter(activity__work=work).select_related('activity').order_by('-pk').first()
    activity = None
    if attempt:
        source = public_agent_runs(AgentRun.objects.filter(case_id=work.case_id, pk=attempt.agent_run_id)).values(
            'process_id', 'evidence_id').first() if attempt.agent_run_id else None
        activity = {'kind': readable(attempt.activity.kind), 'status': attempt.phase, 'at': attempt.created_at,
                    'agent_process': source['process_id'] if source else None,
                    'evidence_id': source['evidence_id'] if source else None}

    reviews = TaskEvent.objects.filter(task__case_id=work.case_id, task__context__work=work.pk,
                                       task__factory_key__startswith=f'factory:{work.pk}:',
                                       data__verdict__in=('approve', 'return', 'reject'))
    latest = reviews.order_by('-pk').values_list('data__verdict', flat=True).first()
    facts = dict.fromkeys(FACTS)
    facts['reviewed'] = True if latest else None
    facts['approved'] = True if latest == 'approve' else False if latest else None
    facts['verified'] = work.status == 'verified' and not row.get('readiness_changed', False)
    if work.definition == FINANCE_INVOICE:
        facts['drafted'] = work.invoice_id is not None
        if work.invoice_id:
            latest = InvoiceReview.objects.filter(invoice_id=work.invoice_id).order_by('-pk').values_list(
                'verdict', flat=True).first()
            facts['reviewed'] = latest is not None
            facts['approved'] = latest == 'approve'
            delivered = InvoiceDelivery.objects.filter(invoice_id=work.invoice_id).exists()
            facts['sent'] = facts['receipt'] = True if delivered else None
    else:
        publication = work.document_publications.filter(factory_source_id=work.source_head_id,
            version__document__case_id=work.case_id).select_related('review').order_by('-pk').first()
        if publication:
            facts['drafted'] = True
            if publication.review_id and publication.review.version_id == publication.version_id:
                facts['reviewed'] = True
                facts['approved'] = publication.review.verdict == 'approve'
            recipients = set(publication.recipient_ids)
            received = set(PublicationReceipt.objects.filter(publication=publication).values_list('recipient_id', flat=True))
            facts['receipt'] = bool(recipients & received)
            facts['sent'] = bool(recipients) and recipients == received

    station = 'intake'
    if activity or work.status not in ('ready', 'configuration_needed'):
        station = 'execution'
    if any(task.status == 'open' for task in row.get('tasks', ())) or row.get('department_wait'):
        station = 'decision'
    if work.status == 'waiting_effect' or facts['receipt']:
        station = 'delivery'
    if facts['verified']:
        station = 'verified'
    history = f'/api/v1/work/{work.pk}/history?kind='
    effects = original_effects(row)
    return {'work_id': work.pk, 'as_of': timezone.now(), 'next_step': row.get('next_action') or 'Review the current work.',
            'blocker': row.get('blocker') or '', 'owner': row.get('owner') or None,
            'station': {'key': station, 'name': STEPS[station]}, 'facts': facts, 'last_activity': activity,
            'stations': [{'key': key, 'name': name} for key, name in STEPS.items()],
            'can_record_delivery_observation': bool(effects), 'uncertain_effects': effects,
            'delivery_observation_url': f'/api/v1/work/{work.pk}/delivery-observations',
            'worker_history_url': history + 'worker', 'decision_history_url': history + 'decision',
            'evidence_history_url': history + 'evidence'}


def delivery_work(actor, work_id):
    work, row, protected = observed_work(actor, work_id)
    if protected.get('recipient_only') or protected.get('handoff'):
        raise Http404
    return work, row


def original_effects(row):
    if not row.get('can_reconcile'):
        return []
    return [{'job_id': job.pk, 'job_type': job._meta.model_name}
            for job in row.get('jobs', ()) if uncertain_job(job)]


def observation(row):
    return {'id': row.pk, 'recorded_at': row.created_at, **json.loads(row.body)}


@endpoint(response=obj({'items': array(OBSERVATION, limit=25)}),
          summary='Read human observations about the original delivery')
def delivery_observations(request, work_id):
    work, _ = delivery_work(request.user, work_id)
    recorded = work.case.evidence.filter(kind=OBSERVATION_KIND, source=f'work-delivery/v1:{work.pk}')
    return {'items': [observation(row) for row in recorded.order_by('-pk')[:25]]}


@endpoint(method='POST', request=obj({'expected_revision': REVISION, 'case_revision': REVISION, 'outcome': OUTCOME,
    'effect': EFFECT, 'proof_id': ID, 'reason': {**TEXT, 'maxLength': 4000}}), response=OBSERVATION, status=201,
          summary='Record an authorised human observation while native delivery reconciliation is pending')
def record_delivery_observation(request, work_id, *, body):
    actor = request.user
    work, _ = delivery_work(actor, work_id)
    reason = body['reason'].strip()
    if not reason:
        raise ValidationError('Enter what you checked about the original delivery.')
    with transaction.atomic():
        work = FactoryWork.objects.select_for_update().get(pk=work_id)
        case = lock_case(actor, work.case_id, 'evidence.add')
        current, row = delivery_work(actor, work_id)
        if not row.get('can_reconcile'):
            raise PermissionDenied('Current recovery responsibility is required.')
        if current.revision != body['expected_revision'] or body['effect'] not in original_effects(row):
            raise Problem(409, 'conflict', 'Review the current delivery before recording an observation.')
        proof = get_object_or_404(case.evidence, pk=body['proof_id'], kind=KIND, source=f'work-proof/v1:{work.pk}')
        source = f'work-delivery/v1:{work.pk}'
        recorded = json.dumps({'outcome': body['outcome'], 'effect': body['effect'], 'proof_id': proof.pk,
                               'reason': reason}, sort_keys=True)
        existing = case.evidence.filter(kind=OBSERVATION_KIND, source=source, created_by=actor,
                                        sha256=hashlib.sha256(recorded.encode()).hexdigest()).first()
        row = existing or add_evidence(actor, case.pk, OBSERVATION_KIND, recorded, source, body['case_revision'])
        return observation(row)
