"""Dispatch one exact reserved intent. No discovery of arbitrary work or automatic retry."""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from apps.workflows import quickbooks_mcp

class Command(BaseCommand):
    help = 'Execute one existing scoped MCP read intent, preserving original caller mode.'

    def add_arguments(self, parser):
        parser.add_argument('--actor', type=int, required=True)
        parser.add_argument('--case', required=True)
        parser.add_argument('--intent', type=int, required=True)

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(pk=options['actor'], is_active=True)
            quickbooks_mcp.execute(actor, options['case'], options['intent'])
            self.stdout.write(str(quickbooks_mcp.status(actor, options['case'], options['intent'])))
        except (ValidationError, PermissionDenied, RuntimeError, get_user_model().DoesNotExist):
            raise CommandError('MCP dispatch held; inspect original scoped intent and current authority') from None
