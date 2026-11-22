"""Guarded separate test ledger lineage with Unknown and More than one proof inputs."""
import json
import os
from base64 import b64decode
from datetime import timedelta
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case, Evidence
from apps.core.services import event
from apps.finance.models import LedgerCheck, LedgerDecision
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.workflows import factory, factory_ledger as flow
from apps.workflows.models import FactoryWork
from tests import ledger_helpers, test_factory_ledger
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT


GUARD='PSL_LEDGER_OBSERVATION_PROOF_FIXTURE'
TENANT='design-ledger-observation-proof'
CASE_ID=uuid5(NAMESPACE_URL,TENANT)
TITLE='SAMPLE supplied QuickBooks observation remains unresolved'
MARKER='sample.ledger_observation_proof_prepared'
OWNER='sample-ledger-observation-source-holder'
REVIEWER='sample-ledger-observation-independent-reviewer'
TRIAL='psl-agent-trial'
OBSERVER_ACTIONS={'case.read','factory.read','finance.read','ledger.read','ledger.private.read','ledger.verify','evidence.add'}
PNG_BYTES=b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aJygAAAAASUVORK5CYII=')
PNG_NAME='SAMPLE-LEDGER-OBSERVATION-PROOF.png'


def seed(case, owner, trial):
    for user, actions in ((owner, set(ACTIONS)), (trial, OBSERVER_ACTIONS)):
        Grant.objects.bulk_create([Grant(case=case,user=user,action=action) for action in sorted(actions)])
    sample=test_factory_ledger.FactoryLedgerTests()
    with patch.object(ledger_helpers,'setup_case',return_value=(owner,case)):
        sample.fixture_factory=lambda:ledger_helpers.fixture(reviewer_username=REVIEWER)
        sample.setUp()
    work=sample.start()
    factory.run_until_wait(work.pk)
    lineage=flow.lineage(work)
    if lineage is None or lineage.actor_id!=owner.pk or lineage.checks.exists():
        raise RuntimeError('Start at the exact supplied source before any observation or decision.')
    fields=('provider','realm','entity','source_reference','transaction_date','accounting_period','treatment_evidence_id')
    facts={key:lineage.payload[key] for key in fields}
    evidence={}
    for state in ('unknown','multiple'):
        values={**facts,'state':state,'target_reference':None,'observed_at':(timezone.now()-timedelta(seconds=1)).isoformat(),
                'incumbent_version':None}
        evidence[state]=ledger_helpers.evidence(sample.f,'quickbooks_verification',values).pk
    return event(owner,case,MARKER,work=work.pk,lineage=lineage.pk,trial=trial.pk,
                 independent=sample.f['reviewer'].pk,source=lineage.evidence_id,review_proof=sample.f['e'].pk,
                 observations=evidence)


@transaction.atomic
def prepare():
    if os.getenv(GUARD)!='1':
        raise RuntimeError('Explicit opt-in for the isolated supplied QuickBooks observation is required.')
    trial=get_user_model().objects.get(username=TRIAL,is_active=True,is_staff=False,is_superuser=False)
    attrs={'tenant':TENANT,'title':TITLE,'kind':'project','synthetic':True}
    case,created=Case.objects.get_or_create(pk=CASE_ID,defaults=attrs)
    if any(getattr(case,key)!=value for key,value in attrs.items()):
        raise RuntimeError('Use only the exact synthetic ledger observation workspace.')
    if created:
        owner=get_user_model().objects.create_user(username=OWNER)
        marker=seed(case,owner,trial)
    else:
        marker=Audit.objects.select_related('actor').get(case=case,action=MARKER,actor__username=OWNER)
    data=marker.data
    if (data['trial']!=trial.pk or marker.actor.has_usable_password()
            or Grant.objects.filter(user=marker.actor).exclude(case=case).exists()
            or set(Grant.objects.filter(case=case,user=trial,active=True).values_list('action',flat=True))!=OBSERVER_ACTIONS):
        raise RuntimeError('Preserve the original case-local Trial observation and distinct source holder.')
    work=FactoryWork.objects.get(pk=data['work'],case=case,actor=marker.actor,definition=flow.DEFINITION)
    lineage=flow.lineage(work)
    if (lineage is None or (lineage.pk,lineage.evidence_id)!=(data['lineage'],data['source'])
            or lineage.checks.exclude(actor=trial,evidence_id__in=data['observations'].values(),status='held').exists()
            or LedgerDecision.objects.filter(verification__lineage=lineage,verdict='approve').exists()
            or Evidence.objects.filter(case=case,kind='quickbooks_verification',pk__in=data['observations'].values()).count()!=2):
        raise RuntimeError('Preserve exact original source and only held supplied observation history.')
    return {**data,'case':str(case.pk),'preserved':not created,'file_name':PNG_NAME,
            'observation_path':reverse('factory_work_response',args=[work.pk]),
            'decision_path':reverse('factory_invoice_decision',args=[work.pk]),
            'latest_check':LedgerCheck.objects.filter(lineage=lineage).order_by('-pk').values_list('pk',flat=True).first()}


def run():
    if (os.getenv('RAILWAY_PROJECT_ID'),os.getenv('RAILWAY_ENVIRONMENT_NAME'),os.getenv('RAILWAY_SERVICE_ID'),
            os.getenv(GUARD))!=(PREVIEW_PROJECT,'design-acceptance','00c14ca1-5361-4bee-97a5-2ec7aba6ef18','1'):
        raise RuntimeError('Use only the isolated Railway acceptance checks service.')
    database=os.getenv('PGDATABASE','')
    if not database or database.lower().startswith('test_') or connection.vendor!='postgresql':
        raise RuntimeError('Select the existing PostgreSQL preview database.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database()')
        if cursor.fetchone()[0]!=database:
            raise RuntimeError('The configured preview database must match the connection.')
    print(GUARD+'='+json.dumps(prepare()),flush=True)
