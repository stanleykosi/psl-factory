from django.core.management.base import BaseCommand, CommandError

from apps.workflows.factory_progress import run_once


class Command(BaseCommand):
    help = 'Advance only due work items with a recorded background request.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=32)

    def handle(self, *args, **options):
        limit = options['limit']
        if type(limit) is not int or not 1 <= limit <= 128:
            raise CommandError('Choose a batch size between 1 and 128 steps.')
        processed = 0
        for _ in range(limit):
            if run_once() is None:
                break
            processed += 1
        if processed:
            self.stdout.write(f'Background work steps checked: {processed}')
