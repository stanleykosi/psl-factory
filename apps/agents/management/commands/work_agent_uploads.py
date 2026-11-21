from django.core.management.base import BaseCommand

from apps.agents.upload_jobs import run_once
from apps.finance.document_review import run_once as read_finance_document


class Command(BaseCommand):
    help = 'Process scoped Finance and general document reading tasks.'

    def handle(self, *args, **options):
        finance = read_finance_document()
        general = run_once()
        self.stdout.write('Agent task processed' if finance or general else 'Agent queue idle')
