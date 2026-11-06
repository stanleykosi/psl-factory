from uuid import UUID
from django.core.management.base import CommandError
from apps.policy.pilot_runtime import PilotWorkerCommand as BaseCommand
from apps.baas.support_release_delivery import run_once
class Command(BaseCommand):
 help='Reconcile/deliver human-released internal support response packets, scoped to one case.'
 def add_arguments(self,parser):
  parser.add_argument('--case',required=True,type=UUID);parser.add_argument('--limit',type=int,default=1)
 def handle(self,*args,**options):
  if not 1<=options['limit']<=100:raise CommandError('Limit must be 1..100')
  for _ in range(options['limit']):
   if not run_once(options['case']):break
