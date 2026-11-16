"""Project views over existing records. Native screens own edits and decisions."""
from django.http import Http404
from django.urls import reverse

from apps.core.evidence_access import public_evidence
from apps.finance.fixed_charge import case_access
from apps.finance.models import Invoice
from apps.pmo.models import ActionItem, ChangeRequest, Issue, Milestone, RFPCase


TABS = (
    ('journey', 'Journey', set()),
    ('milestones', 'Milestones', {'commercial.read', 'delivery.read', 'milestone.complete'}),
    ('documents', 'Documents', {'document.read'}),
    ('templates', 'Templates', {'document.read'}),
    ('money', 'Money', {'finance.read'}),
    ('month-end', 'Month-end', {'finance.read'}),
    ('registers', 'Registers', {'issue.read', 'change.read', 'rfp.read'}),
    ('actions', 'Actions', {'meeting.read'}),
)


def tabs(case, grants):
    return [{'key': key, 'title': title, 'url': reverse('design_project' if key == 'journey' else 'design_project_tab',
                                                       args=[case.pk] if key == 'journey' else [case.pk, key])}
            for key, title, permissions in TABS if not permissions or permissions.intersection(grants)]


def sections(actor, case, tab, grants):
    if not any(item['key'] == tab for item in tabs(case, grants)):
        raise Http404

    def section(title, action, route, items):
        return {'title': title, 'action': action, 'url': reverse(route, args=[case.pk]), 'items': items}

    if tab == 'milestones':
        milestones = Milestone.objects.filter(case=case, evidence__in=public_evidence(case.evidence.all())).order_by('-completed_at', '-pk')[:25]
        return [section('Recorded completions', 'Open milestone records', 'case',
                        [{'title': m.name, 'state': 'Completion recorded', 'at': m.completed_at} for m in milestones])]
    if tab == 'documents':
        evidence = public_evidence(case.evidence.all()).order_by('-created_at', '-pk').only('kind', 'version', 'created_at')[:25]
        return [section('Project evidence', 'Review controlled documents', 'documents',
                        [{'title': e.kind.replace('_', ' ').capitalize(), 'state': f'Version {e.version}', 'at': e.created_at} for e in evidence])]
    if tab == 'money':
        case_access(actor, case)
        invoices = Invoice.objects.filter(case=case).select_related('invoiceissue', 'invoicedelivery').order_by('-pk')[:25]
        return [section('Invoices', 'Open invoices and receipts', 'finance_settlement', [
            {'title': i.reference, 'state': 'Delivered' if hasattr(i, 'invoicedelivery') else 'Issued' if hasattr(i, 'invoiceissue') else 'Draft',
             'detail': f'{i.amount:f} {i.currency} · Version {i.version}', 'at': i.created_at} for i in invoices])]
    if tab == 'actions':
        actions = ActionItem.objects.filter(case=case, current__isnull=False).select_related('current__owner').order_by('current__due_at', 'pk')[:25]
        return [section('Project actions', 'Manage actions and minutes', 'meetings', [
            {'title': a.current.description, 'state': a.current.status.replace('_', ' ').capitalize(),
             'detail': (a.current.owner.get_full_name() or a.current.owner.username) if a.current.owner else 'Owner needed',
             'due': a.current.due_at, 'show_due': True, 'url': reverse('design_project_action', args=[case.pk, a.pk])} for a in actions])]
    if tab == 'registers':
        result = []
        if 'issue.read' in grants:
            issues = Issue.objects.filter(case=case, current__isnull=False).select_related('current').order_by('-pk')[:25]
            result.append(section('Issues', 'Open issues', 'issues', [
                {'title': issue.reference, 'state': issue.current.status.replace('_', ' ').capitalize(),
                 'detail': issue.current.title} for issue in issues]))
        if 'change.read' in grants:
            changes = ChangeRequest.objects.filter(case=case, current__isnull=False).select_related('current').order_by('-pk')[:25]
            result.append(section('Changes', 'Open change requests', 'changes', [
                {'title': change.reference, 'state': f'Version {change.current.number}', 'detail': change.current.module}
                for change in changes]))
        if 'rfp.read' in grants:
            bids = RFPCase.objects.filter(case=case, current_intake__isnull=False).order_by('-pk')[:25]
            result.append(section('Bid requests', 'Open bid requests', 'rfp', [
                {'title': bid.reference, 'state': 'Intake recorded'} for bid in bids]))
        return result
    raise Http404
