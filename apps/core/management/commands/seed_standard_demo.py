import json
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo.models import ChangeRequest
from apps.pmo.changes import log_change, assess_change, authorize_change, CONTRIBUTORS
from apps.pmo.standard_changes import bind_standard, preapprove
from apps.policy.change_drafts import draft_standard_policy
from apps.policy.services import transition


class Command(BaseCommand):
    help = 'Seed an isolated synthetic Standard catalogue and authorized change; refuses overwrite and operational cases.'

    def add_arguments(self, parser):
        parser.add_argument('--case', required=True)
        parser.add_argument('--username', default='studio-demo')

    @transaction.atomic
    def handle(self, *args, **options):
        case=Case.objects.select_for_update().filter(pk=options['case'],synthetic=True,tenant='synthetic-demo',kind='project').first()
        actor=get_user_model().objects.filter(username=options['username'],is_active=True).first()
        if not case or not actor:
            raise CommandError('Requires an existing isolated synthetic-demo project and active demo actor')
        if ChangeRequest.objects.filter(case=case,reference='SYNTHETIC-STD-01').exists():
            raise CommandError('Standard demonstration exists; refusing overwrite')
        for action in ['change.preapprove','agent.changes']:
            Grant.objects.get_or_create(case=case,user=actor,action=action,defaults={'active':True})
        def evidence(kind,body):return add_evidence(actor,case.pk,kind,body,'synthetic:standard-demonstration')
        def rev():case.refresh_from_db();return case.revision
        owner=evidence('policy_decision','Explicitly synthetic Q04 interface demonstration; no operational policy appointment')
        procedure=evidence('change_procedure','Synthetic API maintenance procedure, exact immutable version; no real system change')
        matching=evidence('change_procedure_match','Synthetic PM checked exact procedure applicability to this request')
        approval=evidence('change_preapproval','Synthetic human owner reviewed exact procedure and explicit impact conditions')
        source=evidence('change_request','Demonstrate Standard preapproval without deploying or calculating money')
        data=json.loads((Path(settings.BASE_DIR)/'fixtures/standard-changes.json').read_text(encoding='utf-8'))
        entry=dict(data['catalogue_entry'],procedure_evidence_id=procedure.pk,procedure_sha256=procedure.sha256)
        for component,value in [('D01.change_type_catalogue',[entry]),('D01.satisfied_gate_map',data['gate_map'])]:
            config=draft_standard_policy(actor,case.pk,component,value,owner.pk,timezone.now())
            transition(actor,config.pk,'validated');transition(actor,config.pk,'active')
        v=log_change(actor,case.pk,'SYNTHETIC-STD-01','Standard',entry['module'],'Apply synthetic exact procedure','Synthetic request',source.pk,rev())
        for team in CONTRIBUTORS:assess_change(actor,case.pk,v.pk,team,False,False,False,source.pk,'Explicitly synthetic owner impact',rev())
        for role in ['Product','Engineering']:preapprove(actor,case.pk,entry['key'],role,'approve',approval.pk,'Synthetic human catalogue decision',rev())
        bind_standard(actor,case.pk,v.pk,entry['key'],matching.pk,'Synthetic PM exact applicability',rev())
        auth=authorize_change(actor,case.pk,v.pk,None,rev())
        self.stdout.write(f'Synthetic Standard change version {v.pk}; authorization {auth.pk}. No deployment or external effect.')
