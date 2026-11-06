import secrets
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.baas.models import SupportCase

from apps.identity.actions import ACTIONS


class Command(BaseCommand):
    help = 'Create isolated synthetic workspaces and a random-password demo account; never operational grants.'
    def add_arguments(self, parser):
        parser.add_argument('--username', default='studio-demo')
    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(username=options['username']).exists():
            raise CommandError('Account already exists; this command does not reset passwords or existing records')
        password = secrets.token_urlsafe(18)
        actor = User.objects.create_user(options['username'], password=password)
        for kind, title in [('project','Synthetic delivery engagement'), ('support','Synthetic partner support case')]:
            case = Case.objects.create(tenant='synthetic-demo', title=title, kind=kind, synthetic=True)
            for action in ACTIONS:
                if kind == 'support' and action.startswith(('baseline.', 'milestone.', 'decision.')):
                    continue
                Grant.objects.create(case=case, user=actor, action=action)
            if kind == 'support':
                SupportCase.objects.create(case=case, channel='synthetic', external_ref=str(case.pk))
                add_evidence(actor,case.pk,'support_message','Partner reports an unresolved settlement reference. No corrective credit is authorized.','synthetic:example')
            else:
                for ek in ['requirements','engineering_estimate','security_estimate','plan','costing','sow','signature','completion','policy_decision']:
                    add_evidence(actor,case.pk,ek,f'Synthetic {ek} evidence. Requires human review.','synthetic:example')
        self.stdout.write(f'Created synthetic-only account: {actor.username}\nOne-time password: {password}')
