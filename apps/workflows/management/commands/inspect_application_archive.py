import json
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from adapters.native_application_archive import inspect_offline


class Command(BaseCommand):
    help = 'Host/operator read-only native archive metadata; requires provisioned keys, no database or restore authority.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--source-ref', required=True)
        parser.add_argument('--operation-key', required=True)

    def handle(self, *args, **options):
        try:
            result = inspect_offline(options['source_ref'], options['operation_key'])
        except ValidationError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(json.dumps(result, sort_keys=True))
