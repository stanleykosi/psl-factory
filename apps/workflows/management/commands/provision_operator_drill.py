from django.core.management.base import BaseCommand
from adapters.operator_protection import provision_target
class Command(BaseCommand):
    help='Provision metadata-only receipt tables in an explicitly configured separate existing drill database. Never creates/deletes a database.'
    def handle(self,*args,**v):provision_target();self.stdout.write('Isolated metadata receipt contract provisioned; no business tables restored')
