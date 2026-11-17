from django.core.management.base import BaseCommand

from apps.pmo.rfp_messages import next_batch, run_once


class Command(BaseCommand):
    help = 'Deliver reviewed sample bid messages and reconcile their original receipts.'

    def handle(self,**options):
        ids=next_batch()
        for pk in ids:
            run_once(pk)
        self.stdout.write(f'Bid follow-up messages checked: {len(ids)}')
