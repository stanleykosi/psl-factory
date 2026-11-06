from django.core.management.base import BaseCommand
from apps.pmo.schedules import run_report_once

class Command(BaseCommand):
    help='Generate a bounded batch of due PMO report drafts/human waits; never publish automatically'
    def add_arguments(self,parser):parser.add_argument('--limit',type=int,default=50)
    def handle(self,*args,**options):
        count=0
        for _ in range(min(max(options['limit'],0),1000)):
            if not run_report_once():break
            count+=1
        self.stdout.write(f'Processed {count} report occurrence(s)')
