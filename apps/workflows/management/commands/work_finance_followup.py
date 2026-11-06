from apps.policy.pilot_runtime import PilotWorkerCommand as BaseCommand
from apps.workflows.followup_transport import run_once
class Command(BaseCommand):
    help='Process one leased authenticated Finance metadata intake; never financial work.'
    def handle(self,*args,**options):self.stdout.write('processed' if run_once() else 'idle')
