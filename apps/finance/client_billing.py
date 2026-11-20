"""Read captured client billing facts with the same access as settlement."""
from decimal import Decimal, localcontext

from django.db.models import Exists, OuterRef, Sum

from apps.core.read_budget import ReadBudget, limit_queries
from apps.identity.services import require

from . import cash, corrections
from .fixed_charge import case_access
from .models import BillingCoverage, BillingPreparation, InvoiceCorrectionAcceptance, InvoiceIssue, InvoiceJob


def current_coverages(case):
    successors = BillingCoverage.objects.filter(case_id=OuterRef('case_id'), reference=OuterRef('reference'),
                                               version__gt=OuterRef('version'))
    return BillingCoverage.objects.filter(case=case).filter(~Exists(successors))


def overview(actor, case):
    require(actor, case, 'finance.read')
    limit = ReadBudget()
    with limit_queries(450):
        limit.take(BillingPreparation.objects.filter(case=case, kind='fixed_contract').only('pk'), 50)
        case_access(actor, case)
        coverage = limit.take(current_coverages(case).defer('actor', 'evidence').order_by('customer', 'contract', 'pk'), 100)
        limit.take(InvoiceCorrectionAcceptance.objects.filter(correction__case=case).only('pk'), 500)
        issues = limit.take(InvoiceIssue.objects.filter(invoice__case=case).select_related('invoice__preparation__coverage')
                            .only('invoice__amount', 'invoice__amount_basis', 'invoice__currency',
                                  'invoice__preparation__coverage__customer').order_by('pk'), 100)
        uncertain = InvoiceJob.objects.filter(invoice__case=case, invoice__invoiceissue__isnull=True, kind='issue',
                                              status__in=['leased', 'unknown']).exists()
        groups = {}
        with localcontext() as context:
            context.prec = 512
            for issue in issues:
                invoice = issue.invoice
                source = invoice.preparation.coverage
                key = (source.customer, invoice.currency, invoice.amount_basis)
                face = corrections.adjusted_face(issue)
                applied = cash.allocations(issue=issue).aggregate(total=Sum('amount'))['total'] or Decimal(0)
                group = groups.setdefault(key, {'customer': key[0], 'currency': key[1], 'basis': key[2],
                                                'invoiced': Decimal(0), 'applied': Decimal(0), 'owed': Decimal(0)})
                group['invoiced'] += face
                group['applied'] += applied
                if face < applied:
                    group['owed'] = None
                elif group['owed'] is not None:
                    group['owed'] += face - applied
        return {'coverage': coverage, 'amounts': list(groups.values()), 'uncertain': uncertain}
