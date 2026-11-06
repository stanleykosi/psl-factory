from apps.policy.pilot_runtime import PilotWorkerCommand as BaseCommand
from apps.baas.corrective_delivery import run_once

class Command(BaseCommand):
    help='Deliver bounded Engineering requests receipt-first; never execute financial commands'
    def add_arguments(self,p):p.add_argument('--limit',type=int,default=20)
    def handle(self,*args,**options):
        limit=options['limit']
        if not 1<=limit<=100:raise ValueError('Limit must be 1-100')
        count=0
        while count<limit and run_once():count+=1
        self.stdout.write(f'Processed {count} Engineering handoffs')
