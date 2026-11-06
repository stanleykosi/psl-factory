from uuid import UUID
from django.core.management.base import CommandError
from apps.policy.pilot_runtime import PilotWorkerCommand as BaseCommand
from apps.baas.support_channel_delivery import run_once
class Command(BaseCommand):
 help='Verify read-only customer receipt evidence for an exact case; never dispatch a message.'
 def add_arguments(self,p):p.add_argument('--case',type=UUID,required=True);p.add_argument('--limit',type=int,default=1)
 def handle(self,*args,**options):
  if not 1<=options['limit']<=100:raise CommandError('Limit must be 1..100')
  for _ in range(options['limit']):
   if not run_once(options['case']):break
