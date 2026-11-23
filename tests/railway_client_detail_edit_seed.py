"""Guarded sample for editing client details around an existing internal invoice."""
import json
import os
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse

from apps.core import client_billing_identity, client_contacts, client_project_people
from apps.core.models import Audit, Case, ClientBillingIdentityRevision, ClientContactRevision, ClientProjectPersonRevision
from apps.core.services import add_evidence, event
from apps.finance import invoice_delivery, invoices
from apps.finance.models import InvoiceDelivery, InvoiceIssue, InvoiceJob
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from tests import settlement_helpers as settlement
from tests.billing_helpers import coverage, evidence, prepare as billing_prepare, prices, usage
from tests.helpers import rev
from tests.obligation_helpers import identified
from tests.railway_independent_commercial_seed import PROJECT


TENANT = 'design-client-detail-edit'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
TITLE = 'SAMPLE Harbour Clinics contact update'
TRIAL = 'psl-agent-trial'
MAKER = 'sample-harbour-contact-edit-preparer'
TRIAL_ACTIONS = {'case.read', 'engagement.read', 'engagement.capture', 'finance.read', 'finance.billing.register'}
MARKER = 'sample.client_detail_edit_prepared'
LEGAL = 'SAMPLE Harbour Clinics Ltd'
PRIMARY = 'SAMPLE Product Contact'
PROCUREMENT = 'SAMPLE Procurement Contact'
BILLING = 'SAMPLE Accounts Desk'
INVOICE = 'SAMPLE-CLIENT-CONTACT-INVOICE'


def populate(owner, trial, case):
    scope = coverage(owner, case)
    proof = add_evidence(owner, case.pk, 'engagement_source', 'Separate named product and procurement contacts.',
                         'synthetic:harbour-project-contacts')
    correction = add_evidence(owner, case.pk, 'policy_decision', 'Fictional billing contact and address correction.',
                              'synthetic:harbour-billing-correction')
    people = add_evidence(owner, case.pk, 'engagement_source', 'Fictional updated procurement role/contact wording.',
                          'synthetic:harbour-project-contact-update')
    primary = client_contacts.save(owner, case, 'project', {'revision': rev(case), 'evidence': proof,
        'customer': '', 'client_name': LEGAL, 'name': PRIMARY, 'email': 'sample-product@example.invalid',
        'role': 'Product owner'})
    person = client_project_people.save(owner, case, {'revision': rev(case), 'entry': None, 'evidence': proof,
        'name': PROCUREMENT, 'email': 'sample-procurement@example.invalid', 'role': 'Procurement'})
    billing = client_contacts.save(owner, case, 'billing', {'revision': rev(case), 'evidence': scope.evidence,
        'customer': scope.customer, 'client_name': LEGAL, 'name': BILLING, 'email': 'sample-accounts@example.invalid',
        'role': 'Accounts'})
    identity = client_billing_identity.save(owner, case, {'revision': rev(case), 'coverage': scope,
        'evidence': scope.evidence, 'legal_name': LEGAL, 'billing_address': '10 SAMPLE Road', 'tax_reference': ''})
    prices(owner, case, scope)
    source = usage(owner, case, scope)
    preparation = billing_prepare(owner, case, scope, u=source)
    settlement.configured(owner, case)
    draft = settlement.draft(owner, case, preparation, INVOICE)
    identified(owner, case, draft)
    approval = evidence(owner, case, 'invoice_review', 'Synthetic original invoice approval')
    settlement.approve(owner, case, draft, {'invoice_review': approval})
    job = invoices.reserve(owner, case.pk, draft.pk, 'issue', 'Finance', rev(case))
    if not invoice_delivery.run_once(case_id=case.pk, job_id=job.pk):
        raise RuntimeError('The scoped internal synthetic invoice must be issued before contact edits.')
    issue = InvoiceIssue.objects.get(invoice=draft, job=job)
    return event(owner, case, MARKER, trial=trial.pk, customer=scope.customer, coverage=scope.pk,
                 legal=identity.pk, billing=billing.pk, primary=primary.pk, person=person.pk, invoice=draft.pk,
                 issue=issue.pk, invoice_sha256=issue.sha256, correction=correction.pk, person_proof=people.pk)


@transaction.atomic
def prepare():
    trial = get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    if Case.objects.filter(tenant=TENANT).exclude(pk=CASE_ID).exists():
        raise RuntimeError('Preserve work outside this exact synthetic client specimen.')
    case, created = Case.objects.get_or_create(pk=CASE_ID, defaults={
        'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True,
    })
    case = Case.objects.select_for_update().get(pk=case.pk)
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('This setup only supports its exact synthetic client specimen.')
    if created:
        owner = get_user_model().objects.create_user(MAKER)
        Grant.objects.bulk_create([
            *[Grant(user=owner, case=case, action=action) for action in dict.fromkeys(ACTIONS)],
            *[Grant(user=trial, case=case, action=action) for action in sorted(TRIAL_ACTIONS)],
        ])
        marker = populate(owner, trial, case)
    else:
        marker = Audit.objects.select_related('actor').get(case=case, action=MARKER)
    data = marker.data
    if data['trial'] != trial.pk or marker.actor.username != MAKER or marker.actor.has_usable_password():
        raise RuntimeError('Preserve the exact Trial account and separate noninteractive source author.')
    if set(Grant.objects.filter(case=case, user=trial, active=True).values_list('action', flat=True)) != TRIAL_ACTIONS:
        raise RuntimeError('Preserve the exact case-local contact editing grants.')
    ClientBillingIdentityRevision.objects.get(case=case, pk=data['legal'], number=1, legal_name=LEGAL)
    ClientContactRevision.objects.get(case=case, pk=data['billing'], purpose='billing', number=1, name=BILLING)
    ClientContactRevision.objects.get(case=case, pk=data['primary'], purpose='project', number=1, name=PRIMARY)
    ClientProjectPersonRevision.objects.get(case=case, pk=data['person'], number=1, name=PROCUREMENT)
    issue = InvoiceIssue.objects.get(pk=data['issue'], invoice__case=case, invoice_id=data['invoice'],
                                    sha256=data['invoice_sha256'], job__kind='issue', job__status='confirmed')
    if (InvoiceJob.objects.filter(invoice__case=case).exclude(pk=issue.job_id).exists()
            or InvoiceDelivery.objects.filter(invoice__case=case).exists()):
        raise RuntimeError('Only the original exact internal invoice effect belongs to this specimen.')
    return {**data, 'case': str(case.pk), 'preparer': marker.actor_id, 'preserved': not created,
            'detail': reverse('design_client_project', args=[case.pk]),
            'invoice_reference': INVOICE, 'invoice_amount': str(issue.invoice.amount)}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_CLIENT_DETAIL_EDIT_FIXTURE')) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The exact Railway acceptance project and client detail guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_') or database != connection.settings_dict['NAME']:
        raise RuntimeError('Set the explicit preview database before preparing the client specimen.')
    print('PSL_CLIENT_DETAIL_EDIT_FIXTURE=' + json.dumps(prepare()), flush=True)
