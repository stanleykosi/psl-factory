from django.core.management.base import CommandError
from apps.policy.pilot_runtime import PilotWorkerCommand as BaseCommand
from apps.workflows.application_recovery import run_once
class Command(BaseCommand):
    help='Execute/reconcile exact encrypted native PostgreSQL/managed-attachment intents into empty isolated targets only.'
    def add_arguments(self,p):p.add_argument('--limit',type=int,default=1)
    def handle(self,*args,**options):
        if not 1<=options['limit']<=20:raise CommandError('Limit1..20 required')
        n=0
        while n<options['limit'] and run_once():n+=1
        self.stdout.write(str(n))
