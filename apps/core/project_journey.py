"""Project views over existing records. Native screens own edits and decisions."""
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import Http404
from django.urls import reverse

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import ReadLimit, limit_queries
from apps.pmo.change_impacts import timeline_rows
from apps.pmo.models import ActionItem, ChangeExecutionEvent, ChangeRequest, EmergencyProfile, Issue, Milestone, RFPCase


TABS = (
    ('journey', 'Journey', set()),
    ('milestones', 'Milestones', {'commercial.read', 'delivery.read', 'milestone.complete'}),
    ('documents', 'Documents', {'document.read'}),
    ('templates', 'Templates', {'document.read'}),
    ('money', 'Money', {'finance.read'}),
    ('month-end', 'Month-end', {'finance.read'}),
    ('registers', 'Registers', {'issue.read', 'change.read', 'rfp.read', 'emergency.read'}),
    ('actions', 'Actions', {'meeting.read'}),
)


def tabs(case, grants):
    return [{'key': key, 'title': title, 'url': reverse('design_project' if key == 'journey' else 'design_project_tab',
                                                       args=[case.pk] if key == 'journey' else [case.pk, key])}
            for key, title, permissions in TABS if not permissions or permissions.intersection(grants)]


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


def sections(actor, case, tab, grants, query='', pages=None):
    if not any(item['key'] == tab for item in tabs(case, grants)):
        raise Http404

    def section(title, action, route, records, present):
        page_key = route + '-page'
        window = Paginator(records, 25).get_page(pages.get(page_key) if pages else None)
        return {'title': title, 'action': action, 'url': reverse(route, args=[case.pk]), 'page': window, 'page_key': page_key,
                'items': [present(record) for record in window]}

    if tab == 'milestones':
        milestones = Milestone.objects.filter(case=case, name__icontains=query,
            evidence__in=public_evidence(case.evidence.all())).select_related('completed_by').order_by('-completed_at', '-pk')
        return [section('Recorded completions', 'Open milestone records', 'case',
                        milestones, lambda m: {'title': m.name, 'state': 'Completion recorded', 'at': m.completed_at,
                            'detail': m.completed_by.get_full_name() or m.completed_by.get_username()})]
    if tab == 'documents':
        evidence = public_evidence(case.evidence.all()).order_by('-created_at', '-pk').only('kind', 'version', 'created_at')
        return [section('Project evidence', 'Review controlled documents', 'documents',
                        evidence, lambda e: {'title': e.kind.replace('_', ' ').capitalize(),
                            'state': f'Version {e.version}', 'at': e.created_at})]
    if tab == 'actions':
        actions = ActionItem.objects.filter(case=case, current__isnull=False).filter(
            Q(reference__icontains=query) | Q(current__description__icontains=query)
        ).select_related('current__owner').order_by('current__due_at', 'pk')
        return [section('Project actions', 'Manage actions and minutes', 'meetings', actions,
            lambda a: {'title': a.current.description, 'state': a.current.status.replace('_', ' ').capitalize(),
             'detail': (a.current.owner.get_full_name() or a.current.owner.username) if a.current.owner else 'Owner needed',
             'due': a.current.due_at, 'show_due': True, 'url': reverse('design_project_action', args=[case.pk, a.pk])})]
    if tab == 'registers':
        result = []
        if 'issue.read' in grants:
            issues = Issue.objects.filter(case=case, current__isnull=False).filter(
                Q(reference__icontains=query) | Q(current__title__icontains=query)).select_related('current').order_by('-pk')
            result.append(section('Issues', 'Open issues', 'issues', issues, lambda issue: {
                'title': issue.reference, 'state': issue.current.status.replace('_', ' ').capitalize(), 'detail': issue.current.title}))
        if 'change.read' in grants:
            changes = ChangeRequest.objects.filter(case=case, current__isnull=False).filter(
                Q(reference__icontains=query) | Q(current__module__icontains=query)).select_related('current').order_by('-pk')
            result.append(section('Changes', 'Open change requests', 'changes', changes, lambda change: {
                'title': change.reference, 'state': f'Version {change.current.number}', 'detail': change.current.module}))
        if 'emergency.read' in grants:
            emergencies = EmergencyProfile.objects.filter(version__change__case=case, version__change__reference__icontains=query,
                version__change__current_id=F('version_id')).select_related('version__change').order_by('-pk')
            result.append(section('Emergency changes', 'Open emergency records', 'emergencies', emergencies, lambda emergency: {
                'title': emergency.version.change.reference, 'state': 'Emergency evidence recorded', 'at': emergency.created_at}))
        if 'rfp.read' in grants:
            bids = RFPCase.objects.filter(case=case, current_intake__isnull=False, reference__icontains=query).order_by('-pk')
            result.append(section('Bid requests', 'Open bid requests', 'rfp', bids, lambda bid: {
                'title': bid.reference, 'state': 'Intake recorded'}))
        return result
    raise Http404
