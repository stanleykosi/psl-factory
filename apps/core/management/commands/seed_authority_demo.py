import json
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import transition,resolve
from apps.policy.change_drafts import draft_standard_policy

MARKER='Synthetic authority recovery configuration; no operational appointment'


class Command(BaseCommand):
    help='Prepare isolated recovery policy and fresh follow-up evidence on an existing synthetic Emergency case'
    def add_arguments(self,parser):
        parser.add_argument('--case',required=True);parser.add_argument('--username',default='studio-demo')
    @transaction.atomic
    def handle(self,*args,**options):
        case=Case.objects.select_for_update().filter(pk=options['case'],tenant='synthetic-demo',synthetic=True).first()
        actor=get_user_model().objects.filter(username=options['username'],is_active=True).first()
        if not case or not actor:raise CommandError('Requires an existing isolated synthetic demo case and actor')
        if case.evidence.filter(body=MARKER).exists():raise CommandError('Recovery demo exists; refusing overwrite')
        if resolve('D05.revision_invalidation_rules',case).status=='ACTIVE':raise CommandError('Preserve existing revision policy; configure a reviewed version manually')
        for action in ['authority.read','authority.request','authority.decide','authority.finalize','agent.authority','emergency.followup']:
            Grant.objects.get_or_create(case=case,user=actor,action=action,defaults={'active':True})
        evidence=add_evidence(actor,case.pk,'policy_decision',MARKER,'synthetic:authority-demo')
        source=add_evidence(actor,case.pk,'change_request','Synthetic further Emergency scope/cost investigation; impacts are unknown','synthetic:authority-demo')
        fixture=json.loads((Path(settings.BASE_DIR)/'fixtures/authority-recovery.json').read_text())
        config=draft_standard_policy(actor,case.pk,'D05.revision_invalidation_rules',fixture['value'],evidence.pk,timezone.now())
        transition(actor,config.pk,'validated');transition(actor,config.pk,'active')
        self.stdout.write(f'Synthetic policy #{config.pk}; owner evidence #{evidence.pk}; new follow-up source #{source.pk}. No decisions or effects created.')
