from apps.policy.pilot_runtime import PilotWorkerCommand as BaseCommand
from apps.finance.invoice_delivery import run_batch

class Command(BaseCommand):
    help='Process bounded local invoice issuance/delivery reservations, receipt-first'
    def add_arguments(self,parser):parser.add_argument('--limit',type=int,default=20)
    def handle(self,*args,**options):
        limit=options['limit']
        processed=run_batch(limit)
        self.stdout.write(f'Processed {processed} invoice jobs')
