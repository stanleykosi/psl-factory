"""Real process loss after durable mock acceptance; strictly isolated test PostgreSQL."""
import os,sys
assert os.environ.get('PGDATABASE')=='test_psl','Only the isolated PostgreSQL test database is allowed'
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from apps.finance.models import InvoiceJob
from apps.finance import invoice_delivery
from adapters.factory_invoices import MockFactoryInvoiceAdapter
job=InvoiceJob.objects.select_related('invoice__case').get(pk=int(sys.argv[1]))
assert job.invoice.case.synthetic and job.kind=='issue' and type(job.intent.get('factory_execution',{}).get('work')) is int
class ExitAfterAcceptance(MockFactoryInvoiceAdapter):
    def deliver(self,pk,fence):
        self.lose_response=True
        try:super().deliver(pk,fence)
        except TimeoutError:os._exit(53)
invoice_delivery.run_once(ExitAfterAcceptance(sys.argv[2]),case_id=job.invoice.case_id,job_id=job.pk)
raise AssertionError('Expected process exit after actual durable provider-file acceptance')
