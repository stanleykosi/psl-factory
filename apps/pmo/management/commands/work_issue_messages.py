from django.core.management.base import BaseCommand

from apps.pmo.issue_messages import next_batch, run_once


class Command(BaseCommand):
    help='Check due owner messages and original receipts; no real outbound provider is enabled.'

    def add_arguments(self,parser):
        parser.add_argument('--limit',type=int,default=20)

    def handle(self,*args,**options):
        count=sum(bool(run_once(pk)) for pk in next_batch(options['limit']))
        self.stdout.write(f'Checked {count} owner-message operations; receipts determine delivery.')
