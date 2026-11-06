from django.core.management.base import CommandError
from apps.policy.pilot_runtime import PilotWorkerCommand as BaseCommand
from apps.workflows.operator_delivery import run_once
class Command(BaseCommand):
    help='Reconcile/execute bounded case-metadata protection intents, never restore live business tables.'
    def add_arguments(self,p):p.add_argument('--limit',type=int,default=20)
    def handle(self,*args,**v):
        if not 1<=v['limit']<=100:raise CommandError('Limit1..100 required')
        count=0
        while count<v['limit'] and run_once():count+=1
        self.stdout.write(str(count))
