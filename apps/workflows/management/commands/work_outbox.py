from uuid import UUID
from apps.policy.pilot_runtime import PilotWorkerCommand as BaseCommand
from apps.workflows.services import run_once

class Command(BaseCommand):
    help = 'Process a bounded batch. Schedule repeatedly in a separate worker process.'
    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=50)
        parser.add_argument('--case',dest='case_id',type=UUID)
    def handle(self, *args, **options):
        count = 0
        for _ in range(min(max(options['limit'], 0), 1000)):
            if not run_once(case_id=options['case_id']):
                break
            count += 1
        self.stdout.write(f'Processed {count} handoff(s)')
