from uuid import UUID
from django.core.management.base import CommandError
from apps.policy.pilot_runtime import PilotWorkerCommand as BaseCommand
from apps.workflows.readiness_delivery import run_once
class Command(BaseCommand):
 help='Bounded authenticated health/receipt/public-canary probes; no business dispatch.'
 def add_arguments(self,p):
  p.add_argument('--limit',type=int,default=20)
  p.add_argument('--case',dest='case_id',type=UUID)
 def handle(self,*args,**v):
  if not 1<=v['limit']<=100:raise CommandError('Limit 1..100 required')
  n=0
  while n<v['limit'] and run_once(case_id=v['case_id']):n+=1
  self.stdout.write(str(n))
