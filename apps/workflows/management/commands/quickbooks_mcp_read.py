"""Explicit internal operator entry. No automatic account connection or authority."""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from apps.workflows import quickbooks_mcp

class Command(BaseCommand):
    help = 'Scoped reviewed MCP invoice read; never posting. Disabled without exact configuration.'

    def add_arguments(self, parser):
        parser.add_argument('--actor', type=int, required=True)
        parser.add_argument('--case', required=True)
        parser.add_argument('--lineage', type=int, required=True)
        parser.add_argument('--contract', type=int, required=True)
        parser.add_argument('--revision', type=int, required=True)

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(pk=options['actor'], is_active=True)
            row = quickbooks_mcp.reserve(actor, options['case'], options['lineage'], options['contract'], options['revision'])
            # Print identity before external execution; interruption remains discoverable.
            self.stdout.write('Reserved MCP intent '+str(row.pk))
            quickbooks_mcp.execute(actor, options['case'], row.pk)
            self.stdout.write(str(quickbooks_mcp.status(actor, options['case'], row.pk)))
        except (ValidationError, PermissionDenied, RuntimeError, get_user_model().DoesNotExist):
            raise CommandError('MCP read held; inspect scoped configuration and immutable attempt history') from None
