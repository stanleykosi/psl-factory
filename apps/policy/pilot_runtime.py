from django.core.management.base import BaseCommand,CommandError
from django.core.management.base import OutputWrapper
from django.core.exceptions import ValidationError,PermissionDenied,ObjectDoesNotExist


class PilotWorkerCommand(BaseCommand):
    """Opt-in identity receipts. Observe-only never invokes a worker's handle method."""
    def create_parser(self,*args,**kwargs):
        parser=super().create_parser(*args,**kwargs)
        parser.add_argument('--pilot-binding',type=int)
        parser.add_argument('--pilot-observe-only',action='store_true')
        return parser

    def execute(self,*args,**options):
        pk=options.get('pilot_binding');only=options.get('pilot_observe_only',False)
        if only and not pk:raise CommandError('Observe-only requires an exact pilot binding')
        if pk:
            try:
                from .pilot_bindings import worker
                receipt=worker(pk,self.__class__.__module__,observe_only=only)
            except (ValidationError,PermissionDenied,ObjectDoesNotExist):
                raise CommandError('Current native pilot binding, principal and role credential required') from None
            if only:
                if options.get('stdout'):self.stdout=OutputWrapper(options['stdout'])
                self.stdout.write('Native worker identity observed #'+str(receipt.pk)+'; business worker not invoked')
                return ''
        return super().execute(*args,**options)
