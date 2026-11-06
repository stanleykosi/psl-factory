from django.core.management.base import CommandError
from apps.policy.pilot_runtime import PilotWorkerCommand as BaseCommand
from apps.workflows.reconstitution import run_once


class Command(BaseCommand):
    help='Reconcile bounded current receipt evidence and inert reviewed reconstitution artifacts; never dispatch archived work'
    def add_arguments(self,p):p.add_argument('--limit',type=int,default=1)
    def handle(self,*args,**v):
        if not 1<=v['limit']<=20:raise CommandError('Bounded limit1..20 required')
        count=0
        while count<v['limit'] and run_once():count+=1
        self.stdout.write(str(count))
