from django.core.management.base import BaseCommand
from apps.pmo.delivery_obligations import scan_due


class Command(BaseCommand):
    help='Resume bounded delivery/hypercare observation scans; no approval, publication or deployment'
    def add_arguments(self,parser):parser.add_argument('--limit',type=int,default=100)
    def handle(self,*args,**options):self.stdout.write(str(scan_due(options['limit']))+' new delivery signals')
