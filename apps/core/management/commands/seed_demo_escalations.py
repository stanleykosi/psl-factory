"""Give the PSL demo's Lagoon issue a placeholder escalation profile and one escalation request (D-216).

Synthetic `psl-demo` tenant only; every record goes through the real services. It sets no clock, severity threshold or
recipient: those need PSL's real escalation rule. What it records is explicit about being a placeholder, and unknowns
stay unknown (no timeline impact, no trigger time). Repeatable: what exists is left alone and nothing is deleted.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity import intake
from apps.identity.models import Grant
from apps.pmo.escalations import capture_profile, request_escalation
from apps.pmo.models import EscalationProfile, EscalationRequest, Issue

TENANT = 'psl-demo'
SETUP = 'psl-demo-setup'
PM = 'tunde.bello@psl-demo.test'
LAGOON = 'Lagoon Health · patient app'
REFERENCE = 'ISS-0233'
PLACEHOLDER = 'Placeholder escalation profile (D-216): synthetic, until PSL supplies the real escalation rule.'


class Command(BaseCommand):
    help = 'Add a placeholder escalation profile and one escalation request on the demo Lagoon issue (psl-demo only).'

    @transaction.atomic
    def handle(self, *args, **options):
        case = Case.objects.filter(tenant=TENANT, synthetic=True, title=LAGOON).first()
        user_model = get_user_model()
        admin, pm = (user_model.objects.filter(username=name).first() for name in (SETUP, PM))
        if not case or not admin or not pm:
            raise CommandError('The synthetic psl-demo Lagoon project, its set-up account and its PM are required')
        issue = Issue.objects.select_related('current').filter(case=case, reference=REFERENCE).first()
        if not issue or issue.current.status not in ('Open', 'In Progress'):
            raise CommandError(f'The open demo issue {REFERENCE} is required')
        granted = 0
        if not Grant.objects.filter(case=case, user=pm, action='issue.escalate', active=True).exists():
            intake.change_access(admin, case.pk, pm.pk, 'issue.escalate', True, 'Synthetic PSL demo access (D-216)')
            granted = 1

        def revision():
            case.refresh_from_db()
            return case.revision

        profile = EscalationProfile.objects.filter(state__issue=issue, state_id=issue.current_id).order_by('-pk').first()
        made_profile = made_request = 0
        if not profile:
            source = add_evidence(admin, case.pk, 'issue_impact', PLACEHOLDER, 'synthetic:psl-demo')
            profile = capture_profile(pm, case.pk, issue.pk, issue.current_id, 'internal', None, None, source.pk,
                                      PLACEHOLDER, revision())
            made_profile = 1
        if not EscalationRequest.objects.filter(profile=profile).exists():
            source = add_evidence(admin, case.pk, 'issue_impact',
                                  'Placeholder escalation request (D-216): synthetic demo record, no real communication.',
                                  'synthetic:psl-demo')
            request_escalation(pm, case.pk, profile.pk, 'escalate', 'PMO', source.pk,
                               'Placeholder request to the PMO so the demo has a record to start from (D-216)', revision())
            made_request = 1
        self.stdout.write(f'{LAGOON}, {REFERENCE}: {made_profile} profile, {made_request} request, '
                          f'{granted} access grant added')
