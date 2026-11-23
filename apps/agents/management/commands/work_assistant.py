from django.core.management.base import BaseCommand

from apps.agents.assistant import worker_once


class Command(BaseCommand):
    help = 'Process one saved synthetic department assistant request.'

    def handle(self, *args, **options):
        if worker_once():
            self.stdout.write('Assistant request processed')
