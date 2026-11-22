"""Bounded source choices for Start work, under the native line's grants."""
from django.core.exceptions import PermissionDenied
from django.db.models import Exists, F, Max, OuterRef
from django.shortcuts import get_object_or_404

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import ReadBudget, ReadLimit, limit_queries
from apps.documents.models import Template
from apps.documents.template_access import visible_templates
from apps.finance.models import FinanceAdjustment, FinanceRun, FinanceSource, LedgerLineage, ScheduleWork
from apps.identity.services import require
from apps.pmo.issue_access import public_current_issues
from apps.pmo.models import CommercialRevision, DeliveryDossier, DeliveryRecord, MeetingVersion
from apps.workflows import factory, factory_archive, factory_go_live, factory_handover

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
    'pmo-minutes/v1': 'data.template_id', 'pmo-escalation/v1': 'template_id',
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
          summary='List authorised exact source references for an intake field; use parent_id for trial-balance adjustments')
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
        if more:
            answer['next_before'] = rows[-1][0]
        answer['items'] = [{'id': pk, 'label': ' · '.join(str(value) for value in values) + f' · #{pk}'}
                           for pk, *values in rows]
    return answer
