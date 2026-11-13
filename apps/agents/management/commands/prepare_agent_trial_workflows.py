from django.core.management.base import BaseCommand
from django.db import transaction

from .provision_agent_trial import prepare_workflows


class Command(BaseCommand):
    help = 'Prepare native records and scoped grants for the existing Railway synthetic trial.'

    @transaction.atomic
    def handle(self, *args, **options):
        prepare_workflows()
