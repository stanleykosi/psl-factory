"""Bounded source choices for Start work, under the native line's grants."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Exists, F, Max, OuterRef, Q
from django.shortcuts import get_object_or_404

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import ReadBudget, ReadLimit, limit_queries
from apps.documents.models import Template
from apps.documents.template_access import visible_templates
from apps.finance.fixed_charge import preparation_access
from apps.finance.forecast_workbook import source_ids as workbook_source_ids
from apps.finance.models import BillingCoverage, BillingPreparation, FinanceAdjustment, FinanceRun, FinanceSource
from apps.finance.models import ForecastScenario, Handoff, Invoice, LedgerLineage, ScheduleWork
from apps.identity.services import require
from apps.pmo.issue_access import public_current_issues
from apps.pmo.models import ChangeAuthorization, ChangeVersion, CommercialRevision, DeliveryDossier, DeliveryRecord
from apps.pmo.models import EmergencyAuthorization, EmergencyOutcome, EmergencyProfile, MeetingVersion
from apps.workflows import factory, factory_archive, factory_forecast_sources, factory_go_live, factory_handover

from .http import ID, REVISION, TEXT, Problem, array, choice, endpoint, nullable, obj
from .intake import STARTS, start_projects


PAGE_SIZE = 25
FIELD = {**TEXT, 'maxLength': 100}
DELIVERY_LINES = (
    'delivery-release/v1', 'delivery-hypercare/v1', 'delivery-go-live/v1',
    'delivery-handover/v1', 'delivery-closure/v1', 'delivery-archive/v1',
)
TEMPLATE_TYPES = {
    'pmo-minutes/v1': ('minutes',),
    'delivery-go-live/v1': ('project_artifact',),
    'delivery-handover/v1': ('project_artifact',),
    'delivery-closure/v1': ('project_artifact',),
    'pmo-change/v1': ('project_artifact', 'status_report'),
    'pmo-emergency/v1': ('project_artifact', 'status_report'),
    'pmo-escalation/v1': ('project_artifact', 'status_report'),
    'finance-forecast/v1': ('finance_report', 'finance_group_report'),
}
EVIDENCE_FIELDS = {
    'pmo-minutes/v1': {'data.evidence_id': ('meeting_notes',)},
    'delivery-go-live/v1': {f'inputs.{field}': (kind,) for field, kind in factory_go_live.KINDS.items()},
    'delivery-handover/v1': {f'inputs.{kind}': (kind,) for kind in factory_handover.FIELDS[1:]},
    'delivery-closure/v1': {'inputs.report_evidence_id': ('closure_report',)},
    'finance-schedules/v1': {'evidence_id': ('income_detail', 'schedule_inventory')},
    'rfp-response/v1': {
        'payload.response_evidence': ('rfp_response',), 'payload.public_terms': ('rfp_commercial_terms',),
        'payload.lessons': ('rfp_lessons',), 'payload.matrix.evidence_id': ('requirements', 'rfp_intake'),
        **{f'payload.sources.{kind}': (kind,) for kind in ('requirements', 'plan', 'costing')},
    },
}
TEMPLATE_FIELDS = {key: 'inputs.template_id' for key in TEMPLATE_TYPES} | {
    'pmo-minutes/v1': 'data.template_id', 'pmo-escalation/v1': 'template_id', 'finance-forecast/v1': 'value.template_id',
}


def source_choices(actor, case, line, parent_id):
    evidence = case.evidence.all()
    public = public_evidence(evidence)
    choices = {
        field: (public.filter(kind__in=kinds), ('kind', 'version'))
        for field, kinds in EVIDENCE_FIELDS.get(line, {}).items()
    }
    if line in DELIVERY_LINES:
        dossiers = DeliveryDossier.objects.filter(case=case)
        if line in ('delivery-handover/v1', 'delivery-archive/v1', 'delivery-release/v1'):
            dossiers = dossiers.exclude(Exists(DeliveryRecord.objects.filter(dossier_id=OuterRef('pk'), kind='closure')))
        choices['dossier_id'] = (dossiers, ('candidate__reference',))
    if line in TEMPLATE_FIELDS:
        # A line grant does not admit a restricted template or a bound report.
        try:
            require(actor, case, 'document.read')
        except PermissionDenied:
            pass
        else:
            templates = Template.objects.filter(case=case, definition__document_type__in=TEMPLATE_TYPES[line])
            choices[TEMPLATE_FIELDS[line]] = (templates, ('name', 'version'))
    if line == 'delivery-archive/v1':
        choices.update({f'inventory.{kind}': (public.filter(kind=kind), ('kind', 'version'))
                        for kind in factory_archive.required_kinds(case)})
    if line == 'planning/v1':
        latest = evidence.filter(kind='planning_packet').order_by('-version').values('pk')[:1]
        choices['packet_id'] = (evidence.filter(pk__in=latest), ('kind', 'version'))
    if line == 'commercial/v1':
        heads = CommercialRevision.objects.filter(dossier__case=case, dossier__current_id=F('pk'))
        choices['head_id'] = (heads, ('number',))
    if line == 'pmo-issues/v1':
        issues = public_current_issues(case).filter(current__status__in=('Open', 'In Progress'))
        choices['issue_id'] = (issues, ('reference', 'current__title'))
    if line == 'pmo-change/v1':
        versions = ChangeVersion.objects.filter(change__case=case, change__current_id=F('pk'),
            category__in=['Normal', 'Standard'], evidence__in=public)
        choices['version_id'] = (versions, ('change__reference', 'category', 'number'))
        choices['inputs.authorization_id'] = (ChangeAuthorization.objects.filter(version__in=versions, version_id=parent_id),
                                              ('version__change__reference',))
    if line == 'pmo-emergency/v1':
        current = EmergencyProfile.objects.filter(version__change__case=case, version__change__current_id=F('version_id'),
            version__incident__in=public, evidence__in=public)
        current = current.exclude(Exists(current.filter(version_id=OuterRef('version_id'), pk__gt=OuterRef('pk'))))
        choices['profile_id'] = (current, ('version__change__reference', 'version__number'))
        selected = current.filter(pk=parent_id)
        choices['inputs.authorization_id'] = (EmergencyAuthorization.objects.filter(profile__in=selected), ('created_at',))
        choices['inputs.outcome_id'] = (EmergencyOutcome.objects.filter(profile__in=selected), ('implemented_at',))
    if line == 'pmo-finance/v1':
        coverage = BillingCoverage.objects.filter(case=case)
        current = coverage.exclude(Exists(coverage.filter(reference=OuterRef('reference'), version__gt=OuterRef('version'))))
        choices['coverage_id'] = (current, ('reference', 'version'))
        choices['handoff_id'] = (Handoff.objects.filter(case=case), ('milestone__name',))
        preparation = BillingPreparation.objects.filter(case=case).filter(
            Q(kind='fixed_contract') | Q(kind='usage', usage__collective_acceptance__isnull=False))
        choices['preparation_id'] = (preparation, ('kind', 'coverage__reference'))
        choices['invoice_id'] = (Invoice.objects.filter(case=case, preparation__in=preparation, preparation_id=parent_id),
                                 ('reference', 'version'))
    if line == 'finance-forecast/v1':
        scenarios = ForecastScenario.objects.filter(case=case)
        current = scenarios.exclude(Exists(scenarios.filter(reference=OuterRef('reference'), number__gt=OuterRef('number'))))
        choices['value.scenario_id'] = (current, ('reference', 'number'))
    if line in ('pmo-minutes/v1', 'delivery-closure/v1'):
        # Retrospective metadata inherits the meeting source boundary.
        meetings = MeetingVersion.objects.filter(meeting__case=case, meeting__current_id=F('pk'),
                                                 evidence_id__in=public.values('pk'))
        if line == 'delivery-closure/v1':
            try:
                require(actor, case, 'meeting.read')
            except PermissionDenied:
                pass
            else:
                choices['inputs.retrospective_id'] = (meetings.filter(kind='retrospective'), ('meeting__reference', 'number'))
        else:
            choices['data.meeting_version_id'] = (meetings, ('meeting__reference', 'number'))
    if line == 'finance-ledger/v1':
        # factory.access has already enforced the ledger-private reader here.
        choices['evidence_id'] = (evidence.filter(kind='ledger_source'), ('kind', 'version'))
        choices['predecessor_id'] = (LedgerLineage.objects.filter(case=case), ('evidence_id',))
    if line in ('finance-schedules/v1', 'finance-ppe/v1'):
        mapping = FinanceRun.objects.filter(case=case, kind='mapping')
        if line == 'finance-ppe/v1':
            schedules = ScheduleWork.objects.filter(case=case)
            choices.update({'register_id': (schedules.filter(kind='ppe_register'), ('reference',)),
                            'prior_id': (schedules.filter(kind='ppe_schedule'), ('reference',)),
                            'ledger_id': (mapping, ('source_id',))})
        else:
            choices['parent_id'] = (mapping, ('source_id',))
    if line == 'finance-accounts/v1':
        sources = FinanceSource.objects.filter(case=case)
        heads = sources.values('batch_id').annotate(head=Max('pk')).values('head')
        sources = sources.filter(pk__in=heads)
        choices['source_id'] = (sources, ('entity', 'extracted_at'))
        adjustments = FinanceAdjustment.objects.filter(source_id__in=sources.values('pk'), source_id=parent_id)
        choices['adjustment_ids'] = (adjustments, ('reference', 'number'))
    return choices


def scoped_finance_choices(actor, queryset, ids):
    if queryset.model is ForecastScenario:
        return set(queryset.filter(pk__in=ids, actor__is_active=True, actor__grant__case_id=F('case_id'),
                                   actor__grant__active=True, actor__grant__action='finance.forecast.capture')
                   .values_list('pk', flat=True))
    if queryset.model is Invoice:
        sources = ((row.pk, row.preparation) for row in queryset.filter(pk__in=ids).select_related('preparation'))
    else:
        sources = ((row.pk, row) for row in queryset.filter(pk__in=ids))
    visible = set()
    for key, preparation in sources:
        try:
            preparation_access(actor, preparation)
        except (PermissionDenied, ValidationError):
            continue
        visible.add(key)
    return visible


def positive_id(request, name):
    value = request.GET.get(name)
    if value is None:
        return None
    if len(value) > 19 or not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= ID['maximum']:
        raise Problem(422, 'invalid_filter', 'Choose a valid source reference or continuation.')
    return int(value)


@endpoint(response=obj({'case_revision': REVISION, 'fields': array(FIELD, limit=30), 'field': nullable(FIELD),
                       'items': array(obj({'id': ID, 'label': TEXT}), limit=PAGE_SIZE), 'next_before': nullable(ID)}),
          query={'line': choice(*STARTS), 'field': FIELD, 'before': ID, 'parent_id': ID}, required_query=('line',),
          summary='List authorised intake sources, using the selected parent for dependent fields')
def options(request, case_id):
    line, field = request.GET.get('line'), request.GET.get('field')
    if line not in STARTS or (field is not None and not 1 <= len(field) <= FIELD['maxLength']):
        raise Problem(422, 'invalid_filter', 'Choose a Start work type and a supported source field.')
    before, parent = positive_id(request, 'before'), positive_id(request, 'parent_id')
    actor = request.user
    case = get_object_or_404(start_projects(actor, line), pk=case_id)
    factory.access(actor, case, 'factory.start', line)
    with limit_queries(120):
        choices = source_choices(actor, case, line, parent)
        answer = {'case_revision': case.revision, 'fields': sorted(choices), 'field': field,
                  'items': [], 'next_before': None}
        if field is None:
            return answer
        if field not in choices:
            raise Problem(422, 'invalid_filter', 'Choose a supported source field for this intake.')
        queryset, columns = choices[field]
        if before is not None:
            queryset = queryset.filter(pk__lt=before)
        rows = list(queryset.order_by('-pk').values_list('pk', *columns)[:PAGE_SIZE + 1])
        more = len(rows) > PAGE_SIZE
        rows = rows[:PAGE_SIZE]
        if queryset.model is Template:
            allowed = set(visible_templates(actor, case, candidate_ids=[row[0] for row in rows], budget=ReadBudget())
                          .values_list('pk', flat=True))
            rows = [row for row in rows if row[0] in allowed]
            if more and not rows:
                raise ReadLimit
        elif queryset.model in (BillingPreparation, Invoice, ForecastScenario):
            allowed = scoped_finance_choices(actor, queryset, [row[0] for row in rows])
            cursor = rows[-1][0] if rows else None
            rows = [row for row in rows if row[0] in allowed]
            if more:
                answer['next_before'] = cursor
            more = False
        if more:
            answer['next_before'] = rows[-1][0]
        answer['items'] = [{'id': pk, 'label': ' · '.join(str(value) for value in values) + f' · #{pk}'}
                           for pk, *values in rows]
    return answer


@endpoint(response=obj({'case_revision': REVISION, 'scenario_id': ID, 'reference': TEXT, 'number': REVISION,
    'as_of': {'type': 'string', 'format': 'date'}, 'months': array(TEXT, limit=120), 'source_ids': array(ID, limit=4000),
    'protocol': {'const': factory_forecast_sources.PROTOCOL}}),
    summary='Read the exact current forecast horizon and source inventory without exposing amounts')
def forecast_selection(request, case_id, scenario_id):
    actor = request.user
    line = 'finance-forecast/v1'
    case = get_object_or_404(start_projects(actor, line), pk=case_id)
    factory.access(actor, case, 'factory.start', line)
    scenario = get_object_or_404(ForecastScenario.objects.select_related('actor'), case=case, pk=scenario_id)
    require(scenario.actor, case, 'finance.forecast.capture')
    payload = scenario.payload
    source_ids = sorted({scenario.evidence_id, *workbook_source_ids(scenario),
                         *(item['evidence_id'] for item in payload['openings'] + payload['items'])})
    if len(source_ids) > 4000 or len(payload['months']) > 120:
        raise ReadLimit
    value = {'protocol': factory_forecast_sources.PROTOCOL, 'scenario_id': scenario.pk,
             'as_of': payload['as_of'], 'months': payload['months'], 'source_ids': source_ids}
    # Keep the same provenance check as submission. The exact record may be superseded.
    with limit_queries(300):
        factory_forecast_sources.selection(actor, case, {**value, 'template_id': None, 'audience': 'internal'})
    return {**value, 'case_revision': case.revision, 'reference': scenario.reference, 'number': scenario.number}
