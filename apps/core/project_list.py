"""Bounded project summaries over the current viewer's recorded sources."""
from collections import defaultdict
from datetime import date
from time import monotonic

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import F, Window
from django.db.models.functions import RowNumber

from apps.core.evidence_access import public_evidence
from apps.core.models import Evidence
from apps.core.project_journey import WORK_STATUS, engagement_facts
from apps.core.read_budget import ReadLimit, limit_queries
from apps.core.read_observation import observation_scope
from apps.identity.services import active_case_grants
from apps.pmo.models import DeliveryRecord, Milestone


STATIONS = {
    'engagement/v1': 'Engagement',
    'commercial/v1': 'Pre-sale',
    'rfp-response/v1': 'Pre-sale',
    'planning/v1': 'Planning',
    'delivery-release/v1': 'Release',
    'delivery-go-live/v1': 'Go-live',
    'delivery-hypercare/v1': 'Release follow-up',
    'delivery-archive/v1': 'Archive',
    'delivery-handover/v1': 'Handover',
    'delivery-closure/v1': 'Closure',
}
READ_ACTIONS = ('engagement.read', 'finance.read', 'factory.read')
WORK_LIMIT = 8
PAGE_QUERIES = 540
PAGE_SECONDS = 8


def next_milestone(case):
    from apps.finance.models import BillingCoverage
    from apps.finance.project_money import STAGES, expected_milestone, terms

    stages, _, coverage_id, _ = terms(case)
    coverage = BillingCoverage.objects.filter(case=case, pk=coverage_id).first() if coverage_id else None
    if not coverage:
        return None
    completions = Milestone.objects.filter(case=case)
    visible_proof = public_evidence(case.evidence.all())
    for stage in STAGES:
        if stage == 'signed_sow':
            continue
        if stage not in stages:
            return None
        name = expected_milestone(case, coverage, stage)
        if not name:
            return None
        completion = completions.filter(name=name)
        if completion.filter(evidence__in=visible_proof).exists():
            continue
        if completion.exists():
            return None
        due = stages[stage].get('due_date')
        return {'name': name, 'due': date.fromisoformat(due) if due else None}
    return None


def _closed_dates(projects):
    closed = [row.pk for row in projects if row.project_status_visible and
              row.has_closed_dossier and not row.has_open_dossier]
    if not closed:
        return {}
    evidence = public_evidence(Evidence.objects.filter(case_id__in=closed))
    closures = DeliveryRecord.objects.filter(
        dossier__case_id__in=closed, kind='closure', evidence__in=evidence,
    ).order_by('dossier__case_id', '-created_at', '-pk').distinct('dossier__case_id')
    return dict(closures.values_list('dossier__case_id', 'created_at'))


def _scope(actor, projects):
    from apps.workflows.factory_views import work_grant_scope

    # Payroll, BU and fixed-contract preparations use their separate protected discovery paths.
    return work_grant_scope(actor).filter(case_id__in=projects).exclude(
        definition__in=('finance-payroll/v1', 'finance-bu/v1'),
    ).exclude(preparation__kind='fixed_contract')


def _work_rows(scope):
    selected = scope.annotate(_rank=Window(
        expression=RowNumber(), partition_by=[F('case_id')],
        order_by=[F('updated_at').desc(), F('pk').desc()],
    )).filter(_rank__lte=WORK_LIMIT + 1)
    by_project = defaultdict(list)
    for work in selected.select_related('case', 'actor', 'invoice', 'source_head').defer('source_head__body'):
        by_project[work.case_id].append(work)
    return by_project


def _counts(actor, rows):
    from apps.workflows.factory_views import decision_inbox_row, exception_inbox_row, presentation

    if len(rows) > WORK_LIMIT:
        return None, None
    reviews, exceptions = 0, 0
    for work in rows:
        with observation_scope():
            row = presentation(actor, work)
        if work.status not in ('verified', 'cancelled') and decision_inbox_row(row):
            reviews += 1
        if exception_inbox_row(row, work.status):
            exceptions += 1
    return reviews, exceptions


def _inspect(fn, args, query_limit):
    try:
        with limit_queries(query_limit):
            return fn(*args)
    except (ReadLimit, PermissionDenied, ValidationError):
        return None


def summaries(actor, cases):
    if not cases:
        return []
    grants = active_case_grants(actor, [case.pk for case in cases], actions=READ_ACTIONS)
    visible_work = [case.pk for case in cases if (case.pk, 'factory.read') in grants]
    closed_dates = _closed_dates(cases)
    station = {}
    work = {}
    if visible_work:
        scope = _scope(actor, visible_work)
        latest = scope.filter(definition__in=STATIONS).exclude(status='cancelled').order_by(
            'case_id', '-updated_at', '-pk',
        ).distinct('case_id')
        station = {case_id: (definition, status) for case_id, definition, status in
                   latest.values_list('case_id', 'definition', 'status')}
        work = _work_rows(scope)
    rows = []
    with limit_queries(PAGE_QUERIES, deadline=monotonic() + PAGE_SECONDS):
        for case in cases:
            closed = case.project_status_visible and case.has_closed_dossier and not case.has_open_dossier
            opened = case.project_status_visible and case.has_open_dossier
            phase, state = None, None
            if not closed and case.pk in station:
                definition, status = station[case.pk]
                phase = STATIONS[definition]
                state = 'Outcome recorded' if status == 'verified' else WORK_STATUS.get(status)
            manager = _inspect(engagement_facts, (actor, case), 64) if (case.pk, 'engagement.read') in grants else None
            milestone = _inspect(next_milestone, (case,), 64) if not closed and (case.pk, 'finance.read') in grants else None
            counts = _inspect(_counts, (actor, work.get(case.pk, ())), 190) if case.pk in visible_work else None
            reviews, exceptions = counts or (None, None)
            rows.append({
                'case': case, 'manager': manager.get('manager') if manager else None,
                'lifecycle': 'Closed' if closed else 'Active' if opened else None,
                'closed_at': closed_dates.get(case.pk), 'phase': phase, 'state': state,
                'milestone': milestone, 'reviews': reviews, 'exceptions': exceptions,
            })
    return rows
