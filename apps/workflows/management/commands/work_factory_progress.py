from django.core.management.base import BaseCommand

from apps.workflows.factory_progress import run_once


class Command(BaseCommand):
    help = 'Advance only due work items with a recorded background request.'

    def handle(self, *args, **options):
        processed = 0
        for _ in range(8):
            if run_once() is None:
                break
            processed += 1
        if processed:
            self.stdout.write(f'Background work steps checked: {processed}')
