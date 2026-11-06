from uuid import UUID
from django.core.management.base import CommandError
from apps.policy.pilot_runtime import PilotWorkerCommand as BaseCommand
from apps.agents.boundary_delivery import run_once
class Command(BaseCommand):
 help='Work reviewed private evidence; optional exact case scope.'
 def add_arguments(self,p):p.add_argument('--case',type=UUID);p.add_argument('--limit',type=int,default=1)
 def handle(self,*args,**options):
  if not 1<=options['limit']<=100:raise CommandError('Limit must be 1..100')
  count=0
  for _ in range(options['limit']):
   if not run_once(options['case']):break
   count+=1
  self.stdout.write(str(count))
