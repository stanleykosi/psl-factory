import re
from django.conf import settings
from django.db import connection, transaction
from django.core.management.base import BaseCommand, CommandError
from adapters.native_application_archive import digest
from apps.workflows.cold_recovery_models import ColdControlIdentity
from django.contrib.auth import get_user_model
from apps.core.models import Case
from apps.identity.models import Grant
from apps.policy.models import Configuration


class Command(BaseCommand):
    help = 'Bind an independently provisioned fresh control database to its deployment secret; never imports authority'
    @transaction.atomic
    def handle(self, *args, **options):
        r = settings.COLD_RECOVERY
        name = connection.settings_dict['NAME']
        if not re.fullmatch(r'(?:test_)?psl_cold_[a-z0-9_]{1,40}', name) or r.get('control_database') != name or not isinstance(r.get('control_secret'),bytes) or len(r['control_secret']) != 32:
            raise CommandError('Independent control database and 256-bit secret required')
        with connection.cursor() as c:
            c.execute("SELECT current_setting('psl.recovery_quarantined',true),to_regclass('psl_recovery_control.receipt')")
            quarantine, receipt = c.fetchone()
        if quarantine == 'on' or receipt or ColdControlIdentity.objects.exists():
            raise CommandError('Only a fresh non-recovered, uninitialised control database may be bound')
        if any(model.objects.exists() for model in [get_user_model(), Case, Grant, Configuration]):
            raise CommandError('Fresh control initialization refuses preexisting people, cases or authority; never import archived identities')
        ColdControlIdentity.objects.create(reference=r['control_ref'], secret_sha256=digest(r['control_secret']))
        self.stdout.write('Fresh control identity bound; no users, grants, policy or approval created')
