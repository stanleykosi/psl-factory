from apps.policy.pilot_runtime import PilotWorkerCommand as BaseCommand
from apps.finance.invoice_delivery import run_once

class Command(BaseCommand):
    help='Process bounded local invoice issuance/delivery reservations, receipt-first'
    def add_arguments(self,parser):parser.add_argument('--limit',type=int,default=20)
    def handle(self,*args,**options):
        limit=options['limit']
        if not 1<=limit<=100:raise ValueError('Limit must be 1-100')
        processed=0
        while processed<limit and run_once():processed+=1
        self.stdout.write(f'Processed {processed} invoice jobs')
