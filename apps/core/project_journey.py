"""Project views over existing records. Native screens own edits and decisions."""
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Exists, F, OuterRef, Q, Subquery
from django.http import Http404
from django.urls import reverse
from django.utils import timezone

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import ReadLimit, limit_queries
from apps.pmo.change_impacts import timeline_rows
from apps.pmo.issue_access import public_current_issues, public_states
from apps.pmo.models import (ActionItem, ChangeExecutionEvent, ChangeRequest, EmergencyProfile, EscalationDecision,
                             EscalationRequest, IssueTeamAssignment, Milestone, RFPCase)


MILESTONE_RECORD_ACTIONS = {'commercial.read', 'delivery.read', 'milestone.complete'}

TABS = (
    ('journey', 'Journey', set()),
    ('milestones', 'Milestones', MILESTONE_RECORD_ACTIONS | {'finance.read'}),
    ('documents', 'Documents', {'document.read'}),
    ('templates', 'Templates', {'document.read'}),
    ('money', 'Money', {'finance.read'}),
    ('month-end', 'Month-end', {'finance.read'}),
    ('registers', 'Registers', {'issue.read', 'change.read', 'rfp.read', 'emergency.read'}),
    ('actions', 'Actions', {'meeting.read', 'team.actions.read'}),
    ('hr', 'HR', {'hrfinance.read'}),
)


def tabs(case, grants):
    return [{'key': key, 'title': title, 'url': reverse('design_project' if key == 'journey' else 'design_project_tab',
                                                       args=[case.pk] if key == 'journey' else [case.pk, key])}
            for key, title, permissions in TABS if not permissions or permissions.intersection(grants)]


WORK_STATUS = {
    'ready': 'Ready to continue', 'waiting': 'Waiting', 'waiting_effect': 'Awaiting confirmation',
    'verified': 'Verified', 'blocked': 'Needs attention', 'configuration_needed': 'Setup needed',
    'owner_needed': 'Owner needed', 'cancelled': 'Stopped', 'followup_needed': 'Follow-up needed',
}


def work_timeline(works, page_number):
    from apps.workflows.factory_definitions import DEFINITIONS

    counts = dict(works.order_by().values('status').annotate(total=Count('pk')).values_list('status', 'total'))
    rows = works.order_by('created_at', 'pk').values('pk', 'definition', 'request__reference', 'status', 'created_at', 'updated_at')
    page = Paginator(rows, 20).get_page(page_number)
    items = [{'id': row['pk'], 'line': DEFINITIONS[row['definition']]['title'], 'reference': row['request__reference'],
              'state': WORK_STATUS.get(row['status'], 'Check work item'), 'started': row['created_at'],
              'updated': row['updated_at']} for row in page]
    return {'items': items, 'page': page, 'as_of': timezone.now(), 'total': sum(counts.values()),
            'waiting': counts.get('waiting', 0) + counts.get('waiting_effect', 0),
            'stopped': counts.get('cancelled', 0) + counts.get('followup_needed', 0)}


def finance_facts(actor, case):
    from apps.core.read_budget import ReadBudget
    from apps.finance.models import BillingCoverage
    from apps.finance.project_money import STAGES, expected_milestone, invoice_rows, terms
    from apps.identity.services import require

    require(actor, case, 'finance.read')
    try:
        with limit_queries(260):
            stages, _, coverage_id, _ = terms(case)
            coverage = BillingCoverage.objects.filter(case=case, pk=coverage_id).first() if coverage_id else None
            delivered = sum(hasattr(item, 'invoicedelivery') for item in invoice_rows(actor, case, ReadBudget()))
            next_milestone = None
            if coverage:
                completions = Milestone.objects.filter(case=case, evidence__in=public_evidence(case.evidence.all()))
                for stage in STAGES:
                    if stage == 'signed_sow':
                        continue
                    if stage not in stages:
                        break
                    name = expected_milestone(case, coverage, stage)
                    if not name or not completions.filter(name=name).exists():
                        next_milestone = name
                        break
            return {'stages': len(stages) if coverage and stages else None, 'delivered': delivered, 'next': next_milestone}
    except ReadLimit:
        return {'limited': True}


def engagement_facts(actor, case):
    from apps.identity.services import require
    from apps.pmo import engagement

    require(actor, case, 'engagement.read')
    try:
        source = engagement.current_capture(case)
        for action in ('case.read', 'engagement.read', 'engagement.capture'):
            require(source.actor, case, action)
        if not public_evidence(case.evidence.filter(pk=source.evidence_id)).exists():
            return {}
    except (ValidationError, PermissionDenied):
        return {}
    facts = {'route': source.data['route'], 'reference': source.data['reference']}
    try:
        assignment = engagement.current_assignment(case)
        if public_evidence(case.evidence.filter(pk=assignment.evidence_id)).exists():
            pm = get_user_model().objects.get(pk=assignment.data['pm_id'], is_active=True)
            facts['manager'] = pm.get_full_name() or pm.get_username()
    except (ValidationError, PermissionDenied, get_user_model().DoesNotExist):
        facts['manager'] = None
    return facts


def change_timeline(case, query, page):
    events = ChangeExecutionEvent.objects.filter(authorization__version__change__case=case, kind='plan_updated',
        impact_details__has_key='approved_timeline').exclude(impact_details__approved_timeline='')
    current_ids = events.order_by('authorization_id', '-pk').distinct('authorization_id').values('pk')
    records = ChangeExecutionEvent.objects.filter(pk__in=current_ids,
        evidence__in=public_evidence(case.evidence.all()), authorization__version__change__reference__icontains=query
    ).select_related('authorization__version__change').order_by('-pk')
    window = Paginator(records, 8).get_page(page)
    try:
        with limit_queries(300):
            rows = timeline_rows(case, window)
    except ReadLimit:
        return {'limited': True}
    return {'rows': rows, 'page': window}


def filters(case,tab,grants,data):
    fields={}
    records=None
    if tab=='actions' and {'meeting.read', 'team.actions.read'}.intersection(grants):
        records=ActionItem.objects.filter(case=case,current__isnull=False)
    if tab=='registers' and 'issue.read' in grants:
        records=public_current_issues(case)
        severities=records.exclude(current__severity__isnull=True).order_by('current__severity').values_list('current__severity',flat=True).distinct()[:30]
        fields['severity']=forms.ChoiceField(required=False,label='Issue severity',choices=[('','All severities')]+[(value,value) for value in severities])
    if records is not None:
        states=records.order_by('current__status').values_list('current__status',flat=True).distinct()[:30]
        fields['state']=forms.ChoiceField(required=False,label='Action status' if tab=='actions' else 'Issue status',choices=[('','All statuses')]+[(value,value.replace('_',' ').capitalize()) for value in states])
        owners=get_user_model().objects.filter(pk__in=records.values('current__owner_id')).order_by('username','pk')[:100]
        fields['owner']=forms.ChoiceField(required=False,label='Owner or coordinator' if tab=='registers' else 'Owner',
            choices=[('','All owners'),('unassigned','Unassigned')]+[(str(person.pk),person.get_full_name() or person.get_username()) for person in owners])
    form=type('ProjectReadFilters',(forms.Form,),fields)(data)
    return form


def issue_register_metadata(issues, case):
    opening = public_states(case).filter(issue_id=OuterRef('pk'), number=1).values('created_at')
    latest_assignment = IssueTeamAssignment.objects.filter(issue_id=OuterRef('pk')).order_by('-number').values('pk')[:1]
    team = IssueTeamAssignment.objects.filter(pk=OuterRef('_assignment'), mode='team',
        recorder_id=OuterRef('current__owner_id'), evidence_id__in=public_evidence(case.evidence.all()).values('pk'))
    return issues.alias(_assignment=Subquery(latest_assignment)).annotate(
        opened_at=Subquery(opening), team_label=Subquery(team.values('team_label')),
    ).select_related('current__owner').only('reference', 'current__title', 'current__status', 'current__severity',
        'current__owner__first_name', 'current__owner__last_name', 'current__owner__username')


def issue_register_row(issue, as_of, register_url):
    owner = issue.current.owner
    name = owner.get_full_name() or owner.get_username()
    closed = issue.current.status == 'Closed'
    return {
        'title': issue.reference, 'reference': issue.reference, 'detail': issue.current.title,
        'state': issue.current.status.replace('_', ' ').capitalize(),
        'state_code': issue.current.status,
        'severity': issue.current.severity,
        'owner': name if issue.team_label is None else issue.team_label or 'Owner needed',
        'coordinator': name if issue.team_label is not None else None,
        'closed': closed,
        'age_days': (as_of - issue.opened_at).days if not closed and issue.opened_at and issue.opened_at <= as_of else None,
        'url': f'{register_url}#issue-{issue.pk}',
    }


def sections(actor, case, tab, grants, query='', pages=None, selected=None):
    if not any(item['key'] == tab for item in tabs(case, grants)):
        raise Http404
    from apps.identity.factory_access import department_cases
    project_reader = department_cases(actor, 'pmo-lead').filter(pk=case.pk).exists()

    def section(title, action, route, records, present):
        page_key = route + '-page'
        window = Paginator(records, 25).get_page(pages.get(page_key) if pages else None)
        result={'title': title, 'action': action, 'url': reverse(route, args=[case.pk]), 'page': window, 'page_key': page_key,
                'items': [{**present(record), 'record_id': record.pk} for record in window]}
        group = {'case': 'milestone', 'issues': 'issue', 'escalations': 'escalation', 'changes': 'change',
                 'emergencies': 'emergency', 'rfp': 'bid'}.get(route)
        if project_reader and group:
            result['url'] = reverse('department_records', args=['tola', case.pk]) + '?group=' + group
            for item, record in zip(result['items'], window):
                item['url'] = result['url'] + f'&id={record.pk}'
        if pages is not None:
            for direction in ['previous','next']:
                if getattr(window,'has_'+direction)():
                    params=pages.copy()
                    params[page_key]=getattr(window,direction+'_page_number')()
                    result[direction+'_url']='?'+params.urlencode()+'#'+page_key
        return result

    def apply(records):
        values=selected or {}
        if values.get('state'):
            records=records.filter(current__status=values['state'])
        if values.get('owner'):
            records=records.filter(current__owner_id=None if values['owner']=='unassigned' else values['owner'])
        if values.get('severity'):
            records=records.filter(current__severity=values['severity'])
        return records

    if tab == 'milestones':
        if not MILESTONE_RECORD_ACTIONS.intersection(grants):
            return []
        milestones = Milestone.objects.filter(case=case, name__icontains=query,
            evidence__in=public_evidence(case.evidence.all())).select_related('completed_by').order_by('-completed_at', '-pk')
        return [section('Recorded completions', 'Open milestone records', 'case',
                        milestones, lambda m: {'title': m.name, 'state': 'Completion recorded', 'at': m.completed_at,
                            'state_code': 'recorded', 'detail': m.completed_by.get_full_name() or m.completed_by.get_username()})]
    if tab == 'documents':
        evidence = public_evidence(case.evidence.all()).order_by('-created_at', '-pk').only('kind', 'version', 'created_at')
        return [section('Project evidence', 'Review controlled documents', 'documents',
                        evidence, lambda e: {'title': e.kind.replace('_', ' ').capitalize(),
                            'state': f'Version {e.version}', 'state_code': 'recorded', 'at': e.created_at})]
    if tab == 'actions':
        from apps.identity.services import active_case_grants
        from apps.identity.teams import visible_assignments

        scoped = not active_case_grants(actor, [case.pk], actions=['meeting.read'])
        assignments = visible_assignments(actor).filter(case=case, action__isnull=False)
        actions = apply(ActionItem.objects.filter(case=case, current__isnull=False)).filter(
            Q(reference__icontains=query) | Q(current__description__icontains=query)
        ).select_related('current__owner', 'meeting__current').annotate(
            origin_visible=Exists(public_evidence(case.evidence.filter(pk=OuterRef('meeting__current__evidence_id')))),
        ).order_by('current__due_at', 'pk')
        if project_reader:
            actions = actions.filter(Q(staffassignment__isnull=True) | Q(staffassignment__membership__role='pmo-lead'),
                                     current__evidence__in=public_evidence(case.evidence.all()))
        elif scoped:
            actions = actions.filter(pk__in=assignments.values('action_id')).annotate(
                role_assignment=Subquery(assignments.filter(action_id=OuterRef('pk')).values('pk')[:1]),
            )
        result = section('Project actions', 'Manage actions and minutes', 'meetings', actions,
            lambda a: {'title': a.current.description, 'state': a.current.status.replace('_', ' ').capitalize(),
             'state_code': a.current.status,
             'reference': a.reference,
             'origin_meeting': {'id': a.meeting_id, 'reference': a.meeting.reference, 'at': a.meeting.current.occurred_at}
                 if a.meeting_id and a.meeting.current and a.origin_visible and not scoped else None,
             'detail': (a.current.owner.get_full_name() or a.current.owner.username) if a.current.owner else 'Owner needed',
             'due': a.current.due_at, 'show_due': True, 'assignment_id': a.role_assignment if scoped and not project_reader else None,
             'url': (reverse('department_records', args=['tola', case.pk]) + f'?group=action&id={a.pk}') if project_reader else
             reverse('role_work_detail', args=[a.role_assignment]) if scoped else
             reverse('design_project_action', args=[case.pk, a.pk])})
        active = ~Q(current__status__in=['completed', 'cancelled'])
        paused = Q(current__status='paused', current__clock_meta__pause_behavior='extend_elapsed')
        result['counts'] = actions.aggregate(
            overdue=Count('pk', distinct=True, filter=active & ~paused & Q(current__due_at__lt=timezone.now())),
            unassigned=Count('pk', distinct=True, filter=active & Q(current__owner__isnull=True)),
            total=Count('pk', distinct=True))
        if project_reader:
            result.update(action='Project action records', url=reverse('department_records', args=['tola', case.pk]) + '?group=action')
        elif scoped:
            result.update(action='Open team assignments', url=reverse('home') + '#assignments')
        return [result]
    if tab == 'registers':
        result = []
        if 'issue.read' in grants:
            issues = apply(public_current_issues(case)).filter(
                Q(reference__icontains=query) | Q(current__title__icontains=query)).order_by('-pk')
            as_of, register_url = timezone.now(), reverse('issues', args=[case.pk])
            result.append(section('Issues', 'Open issues', 'issues', issue_register_metadata(issues, case),
                lambda issue: issue_register_row(issue, as_of, register_url)))
            decision = EscalationDecision.objects.filter(request=OuterRef('pk')).order_by('-pk').values('verdict')[:1]
            escalations = EscalationRequest.objects.filter(
                profile__state__issue__case=case, profile__state__issue__reference__icontains=query,
                evidence__in=public_evidence(case.evidence.all()),
            ).select_related('profile__state__issue').annotate(last_verdict=Subquery(decision)).order_by('-pk')
            result.append(section('Escalations', 'Open escalations', 'escalations', escalations, lambda item: {
                'title': item.profile.state.issue.reference,
                'state': f'Decision recorded · {item.last_verdict.replace("_", " ")}' if item.last_verdict else 'Awaiting decision',
                'state_code': item.last_verdict or 'awaiting_decision',
                'at': item.created_at,
            }))
        if 'change.read' in grants:
            changes = ChangeRequest.objects.filter(case=case, current__isnull=False).filter(
                Q(reference__icontains=query) | Q(current__module__icontains=query)).select_related('current').order_by('-pk')
            result.append(section('Changes', 'Open change requests', 'changes', changes, lambda change: {
                'title': change.reference, 'state': f'Version {change.current.number}', 'detail': change.current.module,
                'state_code': 'recorded', 'version_id': change.current_id}))
        if 'emergency.read' in grants:
            emergencies = EmergencyProfile.objects.filter(version__change__case=case, version__change__reference__icontains=query,
                version__change__current_id=F('version_id')).select_related('version__change').order_by('-pk')
            result.append(section('Emergency changes', 'Open emergency records', 'emergencies', emergencies, lambda emergency: {
                'title': emergency.version.change.reference, 'state': 'Emergency evidence recorded', 'at': emergency.created_at,
                'state_code': 'recorded', 'version_id': emergency.version_id}))
        if 'rfp.read' in grants:
            bids = RFPCase.objects.filter(case=case, current_intake__isnull=False, reference__icontains=query).order_by('-pk')
            result.append(section('Bid requests', 'Open bid requests', 'rfp', bids, lambda bid: {
                'title': bid.reference, 'state': 'Intake recorded', 'state_code': 'recorded',
                'receipt_id': bid.current_intake_id}))
        return result
    raise Http404
