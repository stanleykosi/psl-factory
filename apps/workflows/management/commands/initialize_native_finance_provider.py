from django.core.management.base import BaseCommand,CommandError
from django.core.exceptions import ValidationError
from adapters.native_finance import initialize

class Command(BaseCommand):
    help='Initialize only a separately registered current Finance provider marker; no users, roles or business data'
    def add_arguments(self,p):
        p.add_argument('provider_ref');p.add_argument('--synthetic',action='store_true')
    def handle(self,*args,**v):
        try:initialize(v['provider_ref'],v['synthetic'])
        except ValidationError:raise CommandError('Provider initialization held; check separate current database/identity registry') from None
        self.stdout.write('Independent Finance provider marker initialized')
