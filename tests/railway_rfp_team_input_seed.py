"""Guarded source documents for the Commercial team input browser journey."""

import json
import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo.rfp import TEAMS, current_assignment, root
from apps.workflows.models import FactoryWork
from tests import factory_rfp_helpers
from tests.railway_independent_commercial_seed import PROJECT


TENANT = 'design-rfp-team-input-walkthrough'
TITLE = 'SAMPLE bid team input with cited receipt and effort facts'
KEY = 'SAMPLE-BID-TEAM-INPUT'
MAKER = 'sample-bid-team-input-preparer'
SOURCE = 'synthetic:team-input-walkthrough-'
EXAMPLES = {
    'Engineering': ('Sample Engineering coordinator', 'Check invoice import dependencies and add reconciliation logs.', '2.125'),
    'QA': ('Sample QA coordinator', 'The existing regression suite covers the unchanged import. The team estimates zero additional effort.', '0'),
    'Security': ('Sample Security coordinator', 'The team requested the certificate inventory and has yet to supply an effort figure.', None),
}
RECORDER_ACTIONS = {'case.read', 'factory.read', 'rfp.read', 'agent.rfp', *[f'rfp.contribute:{team}' for team in EXAMPLES]}


@transaction.atomic
def prepare(recorder):
    case, created = Case.objects.get_or_create(tenant=TENANT, kind='project', synthetic=True, title=TITLE)
    if created:
        maker = get_user_model().objects.create_user(username=MAKER)
        Grant.objects.bulk_create([
            *[Grant(case=case, user=maker, action=action) for action in dict.fromkeys(ACTIONS)],
            *[Grant(case=case, user=recorder, action=action) for action in sorted(RECORDER_ACTIONS)],
        ])
        data = factory_rfp_helpers.configured(KEY, include_security=False, context=(maker, case))
        now = timezone.now().replace(microsecond=0)
        for index, (team, (party, summary, days)) in enumerate(EXAMPLES.items()):
            fact = {'team': team, 'received_at': (now - timedelta(minutes=12 - index * 4)).isoformat(),
                    'source_party': party, 'summary': summary, 'person_days': days}
            add_evidence(maker, case.pk, TEAMS[team], json.dumps(fact), SOURCE + team.lower())
        work = factory_rfp_helpers.start(data, key=KEY)
    else:
        work = FactoryWork.objects.get(case=case, actor__username=MAKER, definition='rfp-response/v1', key=KEY)
    grants = sorted(Grant.objects.filter(case=case, user=recorder, active=True).values_list('action', flat=True))
    if set(grants) != RECORDER_ACTIONS:
        raise RuntimeError('Use the original recorder with the exact fixture access.')
    proofs = case.evidence.filter(source__in=[SOURCE + team.lower() for team in EXAMPLES]).order_by('pk')
    return {'case': str(case.pk), 'work': work.pk, 'reference': KEY, 'assigned_pm': current_assignment(root(case)).pm_id,
            'recorder': recorder.pk, 'grants': grants, 'preserved': not created,
            'team_input': reverse('rfp', args=[case.pk]) + '#team-inputs',
            'work_path': reverse('factory_work_response', args=[work.pk]),
            'proofs': [{'id': item.pk, 'source': item.source, **json.loads(item.body)} for item in proofs]}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'), os.getenv('PSL_RFP_TEAM_INPUT_FIXTURE')) != (
            'design-acceptance', PROJECT, '1'):
        raise RuntimeError('The Railway acceptance project and explicit team-input fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    recorder = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    print('PSL_RFP_TEAM_INPUT_FIXTURE=' + json.dumps(prepare(recorder)), flush=True)
