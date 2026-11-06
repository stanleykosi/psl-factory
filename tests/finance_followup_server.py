"""Owned actual Django source inbox, independent PostgreSQL process; synthetic credentials only."""
import sys,json,os
v=json.loads(sys.stdin.readline())
import django;django.setup()
from threading import Thread
from wsgiref.simple_server import make_server,WSGIRequestHandler
from django.core.wsgi import get_wsgi_application
from django.conf import settings
from apps.finance.models import InvoiceJob
from tests.finance_intake_helpers import configure,registry
j=InvoiceJob.objects.select_related('actor','invoice__case').get(invoice_id=v['projection']['source_invoice_id'],kind='issue',generation=1)
assert j.invoice.case.synthetic
configure(j.actor,j.invoice.case)
for k,value in registry(j.invoice.case,v['transport_secret']).items():setattr(settings,k,value)
class Quiet(WSGIRequestHandler):
    def log_message(self,*args):pass
server=make_server('127.0.0.1',0,get_wsgi_application(),handler_class=Quiet)
thread=Thread(target=server.serve_forever,daemon=True);thread.start()
print(json.dumps({'transport_url':f'http://127.0.0.1:{server.server_port}'}),flush=True)
try:sys.stdin.readline()
finally:server.shutdown();server.server_close();thread.join()
