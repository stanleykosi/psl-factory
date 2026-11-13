from django.core.management.base import BaseCommand

from apps.agents.upload_jobs import run_once


class Command(BaseCommand):
    help = 'Process one scoped synthetic OpenRouter document task.'

    def handle(self, *args, **options):
        self.stdout.write('Agent task processed' if run_once() else 'Agent queue idle')
