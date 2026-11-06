from apps.finance import corrections,invoices,invoice_delivery
from apps.finance.models import InvoiceJob,InvoiceDelivery,InvoiceCorrectionAcceptance,InvoiceCorrectionDelivery
from .correction_helpers import fixture,note,apply
from .helpers import rev

def documents(case_id=None):
    a,c,cov,iss,e=fixture(case_id)
    j=invoices.reserve(a,c.pk,iss.invoice_id,'deliver','Finance',rev(c));invoice_delivery.run_once();j.refresh_from_db();assert j.status=='confirmed',j.error
    for kind,amount in [('credit','5.00'),('debit','3.00'),('void',None)]:
        r=note(a,c,iss,e,kind,amount,'NATIVE-'+kind)
        j=apply(a,c,r,e);j.refresh_from_db();assert j.status=='confirmed',j.error
        j=corrections.reserve(a,c.pk,r.pk,'adjust_deliver','Finance',rev(c));invoice_delivery.run_once();j.refresh_from_db();assert j.status=='confirmed',j.error
    return a,c,iss,e,list(InvoiceJob.objects.filter(invoice=iss.invoice).order_by('pk'))
