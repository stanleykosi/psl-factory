"""Read-only records shared by the role workspace, citations and assistant worker."""
from dataclasses import dataclass
import re
from string import Formatter
from urllib.parse import urlencode

from django.db.models import Count, F, OuterRef, Q, Value
from django.db.models.functions import Lower, StrIndex, Substr
from django.urls import reverse

from apps.core.evidence_access import public_evidence
from apps.core.models import Evidence
from apps.identity.factory_access import PERSONA_ROLES, department_cases
from apps.workflows.factory_definitions import DEFINITIONS
from apps.workflows.models import FactoryWork


@dataclass
class Register:
    key: str
    title: str
    rows: object
    label: str
    fact: str
    case_path: str = 'case'

    def entries(self):
        fields = {name for pattern in (self.label, self.fact) for _, name, _, _ in Formatter().parse(pattern) if name}
        if self.key == 'finance_figure':
            fields.add('document_id')
        return self.rows.annotate(project_id=F(self.case_path + '_id'), project=F(self.case_path + '__title')).values(
            'project_id', 'project', 'pk', *sorted(fields - {'pk'})).order_by('-pk')

    def matching_entries(self, question):
        rows = self.entries()
        if not question:
            return rows
        # Look up an older named record even when newer records fill the recent window.
        from django.db.models import IntegerField
        from django.db.models.functions import Greatest

        fields = [name for _, name, _, _ in Formatter().parse(self.label) if name in (
            'name', 'reference', 'account', 'transaction_ref', 'scenario__reference')]
        numbers = {int(value) for value in re.findall(r'#([0-9]{1,17})\b', question)}
        if numbers:
            from django.db.models import Case, When
            rows = rows.annotate(exact_id=Case(When(pk__in=numbers, then=Value(1)), default=Value(0)))
        if fields:
            ranks = [StrIndex(Lower(Value(question)), Lower(F(name))) for name in fields]
            rows = rows.annotate(match_rank=Greatest(Value(0), *ranks, output_field=IntegerField()))
        order = (['-exact_id'] if numbers else []) + (['-match_rank'] if fields else [])
        return rows.order_by(*order, '-pk')

    def source(self, persona, row):
        values = {key: value if value is not None else 'unknown' for key, value in row.items()}
        if 'definition' in row:
            values['definition'] = DEFINITIONS[row['definition']]['title']
        label = self.label.format_map(values)
        fact = self.fact.format_map(values)
        if self.key == 'invoice':
            from apps.core.read_budget import ReadBudget, ReadLimit
            from apps.finance.models import Invoice
            from apps.finance.project_money import balance

            invoice = Invoice.objects.select_related('invoiceissue').get(pk=row['pk'])
            try:
                paid, owed, _, _ = balance(invoice, ReadBudget(), include_sources=False)
            except ReadLimit:
                paid = owed = None
            fact += f" Paid: {paid if paid is not None else 'unknown'}. Owed: {owed if owed is not None else 'unknown'}."
        url = reverse('department_records', args=[persona, row['project_id']]) + '?' + urlencode({'group': self.key, 'id': row['pk']})
        if self.key == 'finance_figure':
            url = reverse('finance_document_review', args=[row['project_id'], row['document_id']])
        return {'label': f"{row['project']} · {label}", 'fact': fact,
                'record': {'field': self.key, 'pk': row['pk']},
                'url': url}


def work_definitions(persona):
    finance = {key for key in DEFINITIONS if key.startswith(('finance-', 'pmo-finance/'))}
    return finance if persona == 'chidi' else set(DEFINITIONS) - finance if persona == 'tola' else set()


def registers(persona, cases):
    if persona == 'zainab':
        return []
    works = FactoryWork.objects.filter(case__in=cases, definition__in=work_definitions(persona))
    groups = [Register('work', 'Work in progress and completed work', works, '{definition} #{pk}',
                       'Recorded status: {status}. Last updated {updated_at}.')]
    if persona == 'tola':
        from apps.pmo.issue_access import PublicLinkedProofs
        from django.db.models import Func, JSONField, Subquery
        from apps.pmo.models import (ActionItem, ChangeRequest, EmergencyProfile, EngagementRecord, EscalationRequest,
                                     GateRecord, Issue, Meeting, Milestone, ReportSchedule, RFPCase)
        from apps.pmo.planning_input_models import PlanningDepartmentInput

        evidence = public_evidence(Evidence.objects.filter(case__in=cases)).values('pk')
        issue_proofs = evidence.filter(case_id=OuterRef('case_id'))
        json_ids = issue_proofs.annotate(proof_id=Func('pk', function='to_jsonb', output_field=JSONField())).values('proof_id')
        issues = Issue.objects.filter(case__in=cases, current__evidence__in=issue_proofs).filter(
            Q(current__fix__isnull=True) | Q(current__fix__in=issue_proofs),
            Q(current__root_cause__isnull=True) | Q(current__root_cause__in=issue_proofs),
            PublicLinkedProofs(F('current__external_links'), Subquery(json_ids)))
        actions = ActionItem.objects.filter(case__in=cases, current__evidence__in=evidence).filter(
            Q(staffassignment__isnull=True) | Q(staffassignment__membership__role='pmo-lead'))
        groups.extend([
            Register('intake', 'Incoming project records', EngagementRecord.objects.filter(case__in=cases),
                     'Project intake #{pk}', 'Recorded {kind} on {created_at}.'),
            Register('bid', 'Bid requests', RFPCase.objects.filter(case__in=cases), '{reference}',
                     'Current intake version: {current_intake__number}.'),
            Register('planning', 'Planning and requirements', public_evidence(Evidence.objects.filter(case__in=cases,
                     kind__in=['plan', 'requirements'])).annotate(excerpt=Substr('body', 1, 800)),
                     '{kind} v{version}', '{excerpt}'),
            Register('estimate', 'Department planning inputs', PlanningDepartmentInput.objects.filter(
                     case__in=cases, source__in=evidence).annotate(excerpt=Substr('summary', 1, 500)),
                     '{department} v{version}', '{excerpt}. Effort: {effort_state}. Person-days: {person_days}.'),
            Register('gate', 'Delivery checks', GateRecord.objects.filter(candidate__case__in=cases, evidence__in=evidence),
                     '{kind} · {external_ref}', 'Recorded for {candidate__reference} on {created_at}.', 'candidate__case'),
            Register('milestone', 'Completed milestones', Milestone.objects.filter(case__in=cases, evidence__in=evidence),
                     '{name}', 'Completion recorded on {completed_at}.'),
            Register('meeting', 'Meetings', Meeting.objects.filter(case__in=cases, current__evidence__in=evidence),
                     '{reference}', '{current__purpose}. Met on {current__occurred_at}.'),
            Register('action', 'Project actions', actions,
                     '{reference}', '{current__description}. Status: {current__status}. Due: {current__due_at}.'),
            Register('issue', 'Issues', issues, '{reference}', '{current__title}. Status: {current__status}. Next: {current__next_action}.'),
            Register('escalation', 'Escalations', EscalationRequest.objects.filter(
                     profile__state__issue__case__in=cases, evidence__in=evidence), 'Escalation #{pk}',
                     'Raised for {profile__state__issue__reference} on {created_at}.', 'profile__state__issue__case'),
            Register('change', 'Change requests', ChangeRequest.objects.filter(case__in=cases, current__evidence__in=evidence),
                     '{reference}', '{current__category} change to {current__module}, version {current__number}.'),
            Register('emergency', 'Emergency changes', EmergencyProfile.objects.filter(version__change__case__in=cases,
                     version__change__current_id=F('version_id'), evidence__in=evidence), 'Emergency change #{pk}',
                     'Recorded for {version__change__reference} on {created_at}.', 'version__change__case'),
            Register('report', 'Reporting schedules', ReportSchedule.objects.filter(case__in=cases),
                     '{kind} report #{pk}', 'Status: {status}. Next due: {next_due_at}.'),
        ])
    else:
        from apps.finance.document_models import ReviewedFinanceFigure
        from apps.finance.models import CashAllocation, CashReceipt, CashVerification, FinanceRun, ForecastRun, Handoff, Invoice, PaymentAssessment, ScheduleWork
        from apps.finance.ledger_models import LedgerLineage

        groups.extend([
            Register('invoice', 'Invoices', Invoice.objects.filter(case__in=cases), '{reference} v{version}',
                     'Invoice amount: {currency} {amount}. Due: {due_date}. Issue recorded: {invoiceissue__created_at}.'),
            Register('receipt', 'Cash receipts', CashReceipt.objects.filter(case__in=cases),
                     'Receipt {transaction_ref}', 'Cash receipt recorded on {created_at}. Separate from allocation to an invoice.'),
            Register('verified_cash', 'Verified cash', CashVerification.objects.filter(receipt__case__in=cases,
                     cashreversal__isnull=True), 'Verified cash #{pk}', '{receipt__payload__currency} {amount} verified '
                     'for receipt {receipt__transaction_ref} on {created_at}.', 'receipt__case'),
            Register('allocation', 'Cash allocations', CashAllocation.objects.filter(issue__invoice__case__in=cases,
                     lot__receipt__case__in=cases), 'Allocation #{pk}', '{issue__invoice__currency} {amount} allocated to '
                     '{issue__invoice__reference}. Reversal recorded: {cashreversal__created_at}.', 'issue__invoice__case'),
            Register('handoff', 'Milestones received by Finance', Handoff.objects.filter(case__in=cases),
                     'Milestone handoff #{pk}', 'Finance received the completion of {milestone__name}.'),
            Register('schedule', 'Finance schedules', ScheduleWork.objects.filter(case__in=cases), '{reference}',
                     '{kind} schedule version {version}.'),
            Register('forecast', 'Forecasts', ForecastRun.objects.filter(case__in=cases), 'Forecast #{pk}',
                     'Scenario {scenario__reference}, version {scenario__number}. Calculated on {created_at}.'),
            Register('finance_figure', 'Figures approved by Finance', ReviewedFinanceFigure.objects.filter(
                     document__case__in=cases, document__status='approved'), '{account}',
                     '{period}: {currency} {amount}. Source: {document__name}, {citation}.', 'document__case'),
            Register('accounts', 'Accounting and analysis runs', FinanceRun.objects.filter(case__in=cases),
                     '{kind} #{pk}', 'Recorded on {created_at}.'),
            Register('payment', 'Payment assessments', PaymentAssessment.objects.filter(case__in=cases),
                     'Payment assessment #{pk}', 'Recorded status: {result__status}. Assessed on {created_at}.'),
            Register('ledger', 'Ledger records', LedgerLineage.objects.filter(case__in=cases), 'Ledger record #{pk}',
                     'Source record registered on {created_at}.'),
        ])
    return groups


def records(conversation, question=''):
    persona, case = conversation.persona, conversation.case
    cases = department_cases(conversation.actor, PERSONA_ROLES[persona]).filter(
        tenant=case.tenant, synthetic=case.synthetic)
    if conversation.scope == 'project':
        cases = cases.filter(pk=case.pk)
    elif question:
        named = cases.annotate(mentioned=StrIndex(Lower(Value(question)), Lower('title'))).filter(mentioned__gt=0)
        if named.exists():
            cases = named
    count = cases.count()
    names = list(cases.order_by('title', 'pk').values_list('title', flat=True)[:30])
    url = reverse('department_records', args=[persona, case.pk])
    if conversation.scope == 'department':
        url = reverse('workspace_overview') + '?kind=project'
    result = [{'label': 'Projects in this view', 'fact': f'{count} project(s). Showing {len(names)} names: ' + ', '.join(names),
               'url': url}]
    department = {'tola': 'PMO', 'chidi': 'Finance', 'zainab': 'HR'}[persona]
    head = conversation.scope == 'department' or department_cases(conversation.actor, PERSONA_ROLES[persona],
        heads_only=True).filter(pk=case.pk).exists()
    role_fact = f'The signed-in person heads {department}.' if head else f'The signed-in person is assigned to {department} on this project.'
    scope_fact = 'All department projects in this organisation.' if conversation.scope == 'department' else 'Only this project.'
    if persona == 'zainab':
        return result + [{'label': 'Your role', 'fact': role_fact + ' ' + scope_fact, 'url': url},
                         {'label': 'HR connection', 'fact': 'The live HR system is not connected yet. '
                          'Only available handoff records can be checked here.', 'url': url}]
    groups = registers(persona, cases)
    counts = []
    for group in groups:
        total = group.rows.count()
        counts.append(f'{group.title}: {total}')
        if total:
            for row in group.matching_entries(question)[:4]:
                result.append(group.source(persona, row))
    result.append({'label': 'Department record counts', 'fact': '. '.join(counts) +
                   '. Counts cover all matching projects. Details show up to four recent records per category.', 'url': url})
    states = groups[0].rows.order_by().values('status').annotate(total=Count('pk')).order_by('status')
    if states:
        result.append({'label': 'Work by status', 'fact': ', '.join(f"{row['status']}: {row['total']}" for row in states),
                       'url': url})
    result.append({'label': 'Your role', 'fact': role_fact + ' ' + scope_fact, 'url': url})
    return result
