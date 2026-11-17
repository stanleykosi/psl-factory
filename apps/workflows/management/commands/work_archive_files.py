from django.core.management.base import BaseCommand

from apps.pmo.archive_transfer import run_once


class Command(BaseCommand):
    help = 'Copy pending project archive files and reconcile expired reservations by original receipt lookup.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=10)

    def handle(self, *args, **options):
        count = 0
        for _ in range(max(0, min(options['limit'], 100))):
            if not run_once():
                break
            count += 1
        self.stdout.write(f'Processed {count} project archive file operations.')
