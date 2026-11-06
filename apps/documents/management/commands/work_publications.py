from apps.policy.pilot_runtime import PilotWorkerCommand as BaseCommand
from apps.documents.delivery import run_publication_once

class Command(BaseCommand):
    help='Deliver/reconcile a bounded batch of controlled-document publications'
    def add_arguments(self,parser):
        parser.add_argument('--limit',type=int,default=50)
    def handle(self,*args,**options):
        count=0
        for _ in range(min(max(options['limit'],0),1000)):
            if not run_publication_once():break
            count+=1
        self.stdout.write(f'Processed {count} publication(s)')
