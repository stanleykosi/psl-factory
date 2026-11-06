from django.core.management.base import CommandError
from apps.policy.pilot_runtime import PilotWorkerCommand as BaseCommand
from apps.workflows.cold_recovery import run_once


class Command(BaseCommand):
    help = 'Reconcile fresh-authority isolated recoveries using the independent control database'
    def add_arguments(self, p):
        p.add_argument('--limit', type=int, default=1)
    def handle(self, *args, **v):
        if not 1 <= v['limit'] <= 20:
            raise CommandError('Limit1..20 required')
        count = 0
        while count < v['limit'] and run_once():
            count += 1
        self.stdout.write(str(count))
