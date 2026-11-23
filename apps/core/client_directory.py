"""Client grouping and billing states use only the current viewer's project records."""

from django.core.paginator import Paginator
from django.db.models import Case, Count, Exists, F, Min, OuterRef, Q, Subquery, Value, When

from apps.finance.client_billing import current_coverages
from apps.finance.models import BillingPreparation

from .models import ClientContactRevision, ClientWorkspaceLink
from .workbench import granted


BILLING_FILTERS = (
    ('', 'Any billing contact status'),
    ('recorded', 'Billing contacts recorded'),
    ('needed', 'Billing contact missing'),
    ('unknown', 'Billing status unknown'),
)


def visible_links(actor):
    return ClientWorkspaceLink.objects.filter(case__in=granted(actor, ['finance.read']))


def active_links(query):
    later = ClientWorkspaceLink.objects.filter(case_id=OuterRef('case_id'), number__gt=OuterRef('number'))
    current_coverage = current_coverages(OuterRef('case_id')).filter(pk=OuterRef('coverage_id'))
    private_cases = BillingPreparation.objects.filter(case_id=OuterRef('case_id'), kind='fixed_contract')
    return query.filter(tenant=F('case__tenant'), case__kind='project').exclude(group_key='').filter(
        ~Exists(later), Exists(current_coverage), ~Exists(private_cases))


def page(actor, search, billing, number, links=None):
    project_grants = granted(actor, ['engagement.read'])
    finance_grants = granted(actor, ['finance.read'])
    project_names = ClientContactRevision.objects.filter(
        case_id=OuterRef('pk'), purpose='project', case__in=project_grants,
    ).order_by('-number')

    coverage = current_coverages(OuterRef('pk'))
    current_email = ClientContactRevision.objects.filter(
        case_id=OuterRef('case_id'), customer=OuterRef('customer'), purpose='billing',
    ).order_by('-number').values('email')[:1]
    missing_contact = coverage.alias(contact_email=Subquery(current_email)).filter(
        Q(contact_email__isnull=True) | Q(contact_email=''))

    # Fixed-contract cases require a separate exact source/terms check in the
    # native billing reader. The directory does not inspect those private records.
    fixed_scope = BillingPreparation.objects.filter(case_id=OuterRef('pk'), kind='fixed_contract')
    results = (project_grants | finance_grants).filter(kind='project').only('title', 'kind', 'synthetic').alias(
        finance_visible=Exists(finance_grants.filter(pk=OuterRef('pk'))),
        fixed_scope=Exists(fixed_scope),
        has_coverage=Exists(coverage),
        missing_contact=Exists(missing_contact),
    ).annotate(
        client_name=Subquery(project_names.values('client_name')[:1]),
        billing_status=Case(
            When(Q(finance_visible=False) | Q(fixed_scope=True) | Q(has_coverage=False), then=Value('unknown')),
            When(missing_contact=True, then=Value('needed')),
            default=Value('recorded'),
        ),
    )
    if links is not None:
        results = results.filter(~Exists(links.filter(case_id=OuterRef('pk'))))
    if search:
        results = results.filter(Q(title__icontains=search) | Q(client_name__icontains=search))
    if billing:
        results = results.filter(billing_status=billing)
    return Paginator(results.order_by('title', 'pk'), 25).get_page(number)


def contact_status(links):
    current_email = ClientContactRevision.objects.filter(
        case_id=OuterRef('case_id'), customer=OuterRef('coverage__customer'), purpose='billing',
    ).order_by('-number').values('email')[:1]
    return links.alias(contact_email=Subquery(current_email)).annotate(billing_status=Case(
        When(Q(contact_email__isnull=True) | Q(contact_email=''), then=Value('needed')),
        default=Value('recorded'),
    ))


def grouped_page(links, search, billing, number):
    if search:
        matches = links.filter(Q(client_label__icontains=search) | Q(case__title__icontains=search))
        links = links.filter(group_key__in=matches.values('group_key'))
    groups = contact_status(links).values('group_key').annotate(
        label=Min('client_label'), project_count=Count('pk'),
        contacts_needed=Count('pk', filter=Q(billing_status='needed')),
    )
    if billing == 'needed':
        groups = groups.filter(contacts_needed__gt=0)
    elif billing == 'recorded':
        groups = groups.filter(contacts_needed=0)
    elif billing == 'unknown':
        groups = groups.none()
    return Paginator(groups.order_by('label', 'group_key'), 25).get_page(number)


def group_members(links, group_key, number):
    members = contact_status(links.filter(group_key=group_key)).select_related('case').only(
        'client_label', 'case__title', 'case__kind', 'case__synthetic')
    title = members.order_by('client_label', 'pk').values_list('client_label', flat=True).first()
    return title, Paginator(members.order_by('case__title', 'case_id'), 25).get_page(number)
