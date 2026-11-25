"""Log one synthetic change request on each signed demo project, Lagoon and Delta (D-216).

Synthetic `psl-demo` tenant only, through the real change service by the project's PM. The step stops at "logged": the
owner impact assessments and the five role decisions belong to the people PSL has not yet named, so nothing is assessed
or decided here. Repeatable: an existing reference is left alone and nothing is deleted.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity import intake
from apps.identity.models import Grant
from apps.pmo.changes import log_change
from apps.pmo.models import ChangeRequest

TENANT = 'psl-demo'
SETUP = 'psl-demo-setup'
PROJECTS = [('Lagoon Health · patient app', 'tunde.bello@psl-demo.test', 'DEMO-CR-LAGOON'),
            ('Delta Foods · ordering app', 'chinedu.okeke@psl-demo.test', 'DEMO-CR-DELTA')]


class Command(BaseCommand):
    help = 'Log one placeholder change request on the demo Lagoon and Delta projects (psl-demo only).'

    @transaction.atomic
    def handle(self, *args, **options):
        user_model = get_user_model()
        admin = user_model.objects.filter(username=SETUP).first()
        if not admin:
            raise CommandError('The synthetic psl-demo set-up account is required')
        logged = granted = 0
        for title, username, reference in PROJECTS:
            case = Case.objects.filter(tenant=TENANT, synthetic=True, title=title).first()
            pm = user_model.objects.filter(username=username).first()
            if not case or not pm:
                raise CommandError(f'The synthetic psl-demo project "{title}" and its PM are required')
            if not Grant.objects.filter(case=case, user=pm, action='change.manage', active=True).exists():
                intake.change_access(admin, case.pk, pm.pk, 'change.manage', True, 'Synthetic PSL demo access (D-216)')
                granted += 1
            if ChangeRequest.objects.filter(case=case, reference=reference).exists():
                continue
            source = add_evidence(admin, case.pk, 'change_request',
                                  'Placeholder client change request (D-216): synthetic demo record, no real scope.',
                                  'synthetic:psl-demo')
            case.refresh_from_db()
            log_change(pm, case.pk, reference, 'Normal', 'Demo module (placeholder)',
                       'Placeholder change request for the demo (D-216): no real scope is changed',
                       'Synthetic demo record until a real client change arrives', source.pk, case.revision)
            logged += 1
        self.stdout.write(f'{logged} change requests logged, {granted} access grants added')
