"""Only source-linked clients may be grouped. The current directory lists project records."""

from django.core.paginator import Paginator
from django.db.models import Case, Exists, OuterRef, Q, Subquery, Value, When

from apps.finance.client_billing import current_coverages
from apps.finance.models import BillingPreparation

from .models import ClientContactRevision
from .workbench import granted


BILLING_FILTERS = (
    ('', 'Any billing contact status'),
    ('recorded', 'Billing contacts recorded'),
    ('needed', 'Billing contact missing'),
    ('unknown', 'Billing status unknown'),
)


def page(actor, search, billing, number):
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
    if search:
        results = results.filter(Q(title__icontains=search) | Q(client_name__icontains=search))
    if billing:
        results = results.filter(billing_status=billing)
    return Paginator(results.order_by('title', 'pk'), 25).get_page(number)
