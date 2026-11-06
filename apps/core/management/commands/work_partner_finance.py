from django.core.management.base import CommandError
from apps.policy.pilot_runtime import PilotWorkerCommand as BaseCommand
from apps.baas.partner_delivery import run_once

class Command(BaseCommand):
    help='Deliver reviewed partner activity to the local Finance inbox; never issue invoices'
    def add_arguments(self,parser):parser.add_argument('--limit',type=int,default=1)
    def handle(self,*args,**options):
        if not 1<=options['limit']<=100:raise CommandError('Limit must be1–100')
        n=0
        for _ in range(options['limit']):
            if not run_once():break
            n+=1
        self.stdout.write(f'Processed {n} partner Finance handoffs')
