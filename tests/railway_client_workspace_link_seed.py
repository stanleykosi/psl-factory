"""One reviewed client project and one exact independent review still pending."""

import json
import os
from urllib.parse import urlencode
from uuid import NAMESPACE_URL, UUID, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from apps.core import client_workspace_links as links
from apps.core.client_contacts import save as save_contact
from apps.core.evidence_access import CLIENT_WORKSPACE_LINK_PROOF
from apps.core.models import Audit, Case, ClientContactRevision, ClientWorkspaceLink
from apps.core.services import event
from apps.documents.models import Publication
from apps.finance.models import BillingCoverage, Invoice
from apps.identity.models import Grant
from tests.billing_helpers import coverage
from tests.helpers import rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_independent_commercial_seed import PROJECT


TENANT = 'design-client-reviewed-link-sample'
MARKER = 'sample.client_link_fixture_prepared'
TRIAL = 'psl-agent-trial'
HOSTED_ADMISSION = (7, 243)
HOSTED_ADMISSION_CASE = UUID('f01c74c2-81f7-4be8-b9a5-6aae4c71a243')
HOSTED_MAKER = 'sample-correction-preparer-20261120'
NAME = 'SAMPLE Harbour Client'
ISSUER = 'sample.customer.register'
REFERENCE = 'SAMPLE-HARBOUR-CLIENT'
PROJECTS = (
    ('installation', 'SAMPLE Harbour Client installation'),
    ('follow-up', 'SAMPLE Harbour Client follow-up'),
)
CASE_IDS = {key: uuid5(NAMESPACE_URL, f'{TENANT}/{key}') for key, _ in PROJECTS}
MAKER_ACTIONS = {'case.read', 'finance.read', 'finance.billing.register', 'evidence.add'}
REVIEWER_ACTIONS = {'case.read', 'finance.read', 'policy.activate'}


def prepare_project(case, maker, reviewer, key, identities):
    Grant.objects.bulk_create([
        *[Grant(case=case, user=maker, action=action) for action in sorted(MAKER_ACTIONS)],
        *[Grant(case=case, user=reviewer, action=action) for action in sorted(REVIEWER_ACTIONS)],
    ])
    scope = coverage(maker, case, reference='sample-current-billing', customer='HARBOUR-LOCAL')
    if key == 'installation':
        save_contact(maker, case, 'billing', {'revision': rev(case), 'evidence': scope.evidence,
            'customer': scope.customer, 'client_name': NAME, 'name': 'SAMPLE billing desk',
            'email': 'harbour-billing@example.invalid', 'role': 'Billing'})
    proof = links.propose(maker, case, rev(case), action='link', coverage_id=scope.pk, issuer=ISSUER,
                          reference=REFERENCE, name=NAME, source=f'Synthetic customer register entry for {key}')
    original = links.confirm(reviewer, case, rev(case), proof.pk) if key == 'installation' else None
    return event(maker, case, MARKER, **identities, coverage=scope.pk, proof=proof.pk,
                 original_link=original.pk if original else None)


@transaction.atomic
def prepare(invitation_id, user_id, *, hosted=False):
    reviewer = get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    admission, maker = admitted_user(invitation_id, user_id, reviewer)
    if hosted and (admission.invitation.case_id != HOSTED_ADMISSION_CASE or maker.username != HOSTED_MAKER):
        raise RuntimeError('Use the exact earlier accepted hosted sample preparer.')
    identities = {'invitation': invitation_id, 'admission': admission.pk, 'maker': maker.pk, 'reviewer': reviewer.pk}
    if Case.objects.filter(tenant=TENANT).exclude(pk__in=CASE_IDS.values()).exists():
        raise RuntimeError('Preserve every workspace outside this exact two-project specimen.')
    result = {}
    newly_created = []
    for key, title in PROJECTS:
        case, created = Case.objects.get_or_create(pk=CASE_IDS[key],
            defaults={'tenant': TENANT, 'title': title, 'kind': 'project', 'synthetic': True})
        if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, title, 'project', True):
            raise RuntimeError('Preserve the original scoped client specimen.')
        newly_created.append(created)
        marker = (prepare_project(case, maker, reviewer, key, identities) if created else
                  Audit.objects.get(case=case, action=MARKER, actor=maker))
        if any(marker.data.get(field) != value for field, value in identities.items()):
            raise RuntimeError('Preserve the original admission and reviewing account.')
        for actor, actions in ((maker, MAKER_ACTIONS), (reviewer, REVIEWER_ACTIONS)):
            if set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True)) != actions:
                raise RuntimeError('Preserve the two exact case-local roles.')
        scope = BillingCoverage.objects.get(case=case, pk=marker.data['coverage'])
        proof = case.evidence.get(pk=marker.data['proof'], kind=CLIENT_WORKSPACE_LINK_PROOF, created_by=maker)
        facts = links.facts_from(proof)
        if (facts['issuer'], facts['reference'], facts['name'], facts['coverage']) != (ISSUER, REFERENCE, NAME, scope.pk):
            raise RuntimeError('Preserve the exact original register identity and billing scope.')
        original = marker.data['original_link']
        if original:
            ClientWorkspaceLink.objects.get(case=case, pk=original, evidence=proof, reviewer=reviewer)
        if Invoice.objects.filter(case=case).exists() or Publication.objects.filter(version__document__case=case).exists():
            raise RuntimeError('This client grouping specimen requires no invoices or delivery.')
        current = links.current(case)
        result[key] = {'case': str(case.pk), 'title': title, 'coverage': scope.pk, 'proof': proof.pk,
                       'original_link': original, 'current_link': current.pk if current else None,
                       'detail': reverse('design_client_workspace_link', args=[case.pk]),
                       'contact': ClientContactRevision.objects.filter(case=case, purpose='billing').exists()}
    if len(set(newly_created)) != 1:
        raise RuntimeError('Prepare both related projects together or preserve their original state.')
    index = reverse('design_clients')
    group = links.group_key(TENANT, ISSUER, REFERENCE)
    return {'tenant': TENANT, 'client': NAME, **identities, 'projects': result,
            'directory': index + '?' + urlencode({'q': NAME}),
            'group': index + '?' + urlencode({'client': group, 'q': NAME}),
            'missing_filter': index + '?' + urlencode({'q': NAME, 'billing': 'needed'}),
            'preserved': not newly_created[0]}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_CLIENT_LINK_FIXTURE')) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The exact Railway acceptance project and client link fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    print('PSL_CLIENT_LINK_FIXTURE=' + json.dumps(prepare(*HOSTED_ADMISSION, hosted=True)), flush=True)
