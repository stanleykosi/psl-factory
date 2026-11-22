from django.core.management.base import BaseCommand, CommandError

from apps.core.account_delivery import work


class Command(BaseCommand):
    help = 'Deliver enabled account notifications and reconcile the original sends.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=20)

    def handle(self, *args, **options):
        limit = options['limit']
        if not 1 <= limit <= 100:
            raise CommandError('Delivery batch must be between 1 and 100.')
        work(limit)
