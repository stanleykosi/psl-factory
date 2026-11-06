from django.core.management.base import BaseCommand
from apps.pmo.emergency_obligations import scan_due


class Command(BaseCommand):
    help='Persist bounded emergency obligation signals; never approve, publish or deploy.'
    def add_arguments(self,parser):parser.add_argument('--limit',type=int,default=100)
    def handle(self,*args,**options):self.stdout.write(f"Created {scan_due(options['limit'])} emergency obligation signals; no effects dispatched")
