import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo.gates import register_candidate
from apps.pmo.models import DeliveryCandidate


class Command(BaseCommand):
    help = 'Provision one scoped synthetic account for the hosted agent trial.'

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.getenv('PSL_AGENT_TRIAL_PASSWORD')
        if not password or len(password) < 24:
            raise CommandError('A dedicated trial password is required.')
        users = get_user_model().objects
        if users.filter(username='psl-agent-trial').exists():
            return
        actor = users.create_user('psl-agent-trial', password=password)
        case = Case.objects.create(tenant='psl-agent-trial', title='Synthetic agent trial',
                                   kind='project', synthetic=True)
        Grant.objects.bulk_create([
            Grant(user=actor, case=case, action=action)
            for action in ('case.read', 'evidence.add', 'agent.extract', 'document.review', 'factory.read')
        ])
        self.stdout.write('Synthetic agent trial case: ' + str(case.pk))


def prepare_workflows():
    case = Case.objects.filter(pk='919b157e-f212-4a3e-8cf2-2082a72128e3', synthetic=True,
                               tenant='psl-agent-trial', kind='project').first()
    if case is None:
        return
    actor = get_user_model().objects.get(username='psl-agent-trial', is_superuser=False)
    for action in (
        'engagement.capture', 'engagement.read', 'issue.manage', 'issue.own', 'issue.read',
        'planning.read', 'planning.coordinate', 'recognition.prepare', 'recognition.read',
        'meeting.record', 'meeting.read', 'pmo.candidate', 'pmo.gate_record',
        'validation.source.capture', 'validation.package.prepare', 'validation.read',
    ):
        Grant.objects.get_or_create(case=case, user=actor, action=action)
    reference = 'agent-trial-release-candidate'
    if not DeliveryCandidate.objects.filter(case=case, reference=reference).exists():
        evidence = add_evidence(actor, case.pk, 'requirements', 'Synthetic release candidate requirements.',
                                'synthetic:agent-workflow-trial')
        case.refresh_from_db()
        register_candidate(actor, case.pk, reference, evidence.pk, case.revision)
