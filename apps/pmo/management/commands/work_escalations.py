from django.core.management.base import BaseCommand
from apps.pmo.escalations import scan_due

class Command(BaseCommand):
    help='Record bounded source-bound issue urgency signals only; never send or approve an escalation.'
    def add_arguments(self,parser):parser.add_argument('--limit',type=int,default=100)
    def handle(self,*args,**options):
        limit=options['limit']
        if not 1<=limit<=1000:
            from django.core.management.base import CommandError
            raise CommandError('Limit must be between 1 and 1000')
        self.stdout.write(f'Created {scan_due(limit)} urgency signal(s); no communications dispatched.')
