"""Real process loss after durable mock acceptance; strictly isolated test PostgreSQL."""
import os,sys
from tests.invoice_crash_target import target, validate_connection, verify_database, validate_job
expected_target=target(os.environ)
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.db import connection
validate_connection(connection.settings_dict,expected_target)
with connection.cursor() as cursor:verify_database(cursor,expected_target)
from apps.finance.models import InvoiceJob
from apps.finance import invoice_delivery
from adapters.factory_invoices import MockFactoryInvoiceAdapter
job=InvoiceJob.objects.select_related('invoice__case').get(pk=int(sys.argv[1]))
validate_job(job)
class ExitAfterAcceptance(MockFactoryInvoiceAdapter):
    def deliver(self,pk,fence):
        self.lose_response=True
        try:super().deliver(pk,fence)
        except TimeoutError:os._exit(53)
invoice_delivery.run_once(ExitAfterAcceptance(sys.argv[2]),case_id=job.invoice.case_id,job_id=job.pk)
raise AssertionError('Expected process exit after actual durable provider-file acceptance')
