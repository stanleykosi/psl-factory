"""Additive source fixtures for the native Commercial browser walkthrough."""

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
from apps.pmo import rfp_portal, rfp_pricing
from apps.pmo.models import RFPSubmission
from apps.workflows import factory
from apps.workflows.models import FactoryWork
from tests import factory_rfp_helpers
from tests.helpers import rev


PROJECT = 'f957481b-c6f7-43af-bc66-449a330a9d53'
TENANT = 'design-commercial-outcome-walkthrough'
SCENARIOS = {
    'pending': 'customer decision and internal reminder dates',
    'portal': 'client portal proof validation',
    'match': 'matching quoted and awarded price',
    'basis': 'different quote and award price basis',
}


def evidence(actor, case, kind, source, value):
    return add_evidence(actor, case.pk, kind, json.dumps(value), f'synthetic:commercial-batch-{source}')


def prepare_sources(actor, case, scenario):
    reference = f'SAMPLE-COMMERCIAL-OUTCOME-{scenario.upper()}'
    with_portal = scenario != 'pending'
    data = factory_rfp_helpers.configured(reference, context=(actor, case), portal=with_portal)
    if with_portal:
        quote = evidence(actor, case, 'rfp_commercial_terms', 'quote', {
            'schema': rfp_pricing.QUOTE, 'terms': 'Fictional acceptance pack (no live customer).',
            'amount': '100.00', 'currency': 'NGN', 'basis': 'whole_contract',
        })
        data['payload']['public_terms'] = quote.pk
    work = factory_rfp_helpers.start(data, key=reference)
    response, version = factory_rfp_helpers.reviewed_document(data, work)
    factory.run_until_wait(work.pk)
    if not with_portal:
        submission = response.submissions.get()
        expected_on = timezone.localdate() + timedelta(days=7)
        add_evidence(actor, case.pk, 'rfp_outcome',
            f'Fictional customer response for submission {submission.pk}: we expect a decision on {expected_on}.',
            'synthetic:commercial-batch-pending')
        return work

    receipt = {'schema': rfp_portal.SCHEMA, 'version': version.pk, 'sha256': version.payload_sha256,
        'destination': data['route']['destination_ref'], 'reference': f'SAMPLE-PORTAL-{scenario.upper()}',
        'received_at': timezone.now().isoformat()}
    proof = evidence(actor, case, 'rfp_portal_receipt', 'portal', receipt)
    if scenario == 'portal':
        evidence(actor, case, 'rfp_portal_receipt', 'wrong-portal', {**receipt, 'sha256': '0' * 64})
        return work

    submission = rfp_portal.record(actor, case.pk, version.pk, proof.pk, 'Exact synthetic portal pack and proof reviewed.', rev(case))
    factory.run_until_wait(work.pk)
    evidence(actor, case, 'rfp_outcome', 'award', {
        'schema': rfp_pricing.AWARD, 'submission': submission.pk, 'amount': '100.00', 'currency': 'NGN',
        'basis': 'whole_contract' if scenario == 'match' else 'monthly',
    })
    return work


@transaction.atomic
def prepare(actor, scenario):
    case, created = Case.objects.get_or_create(tenant=TENANT, kind='project', synthetic=True,
        title=f'SAMPLE commercial {SCENARIOS[scenario]}')
    if created:
        Grant.objects.bulk_create([Grant(case=case, user=actor, action=action) for action in dict.fromkeys(ACTIONS)])
        work = prepare_sources(actor, case, scenario)
    else:
        work = FactoryWork.objects.get(case=case, actor=actor, definition='rfp-response/v1',
            key=f'SAMPLE-COMMERCIAL-OUTCOME-{scenario.upper()}')
    sources = dict(case.evidence.filter(source__startswith='synthetic:commercial-batch-').values_list('source', 'pk'))
    submission = RFPSubmission.objects.filter(response__rfp__case=case).order_by('-pk').first()
    result = {'case': str(case.pk), 'work': work.pk, 'submission': submission.pk if submission else None,
        'path': reverse('factory_work_response', args=[work.pk]), 'sources': sources,
        'existing_work_preserved': not created}
    return result


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_COMMERCIAL_OUTCOME_FIXTURES')) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The Railway acceptance environment and explicit Commercial fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    actor = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    for scenario in SCENARIOS:
        print('PSL_COMMERCIAL_OUTCOME_FIXTURE=' + json.dumps({'scenario': scenario, **prepare(actor, scenario)}), flush=True)
