from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.test import TestCase

from apps.core import client_project_people
from apps.core.models import Case, ClientBillingIdentityRevision, ClientContactRevision, ClientProjectPersonRevision
from apps.core.services import add_evidence
from apps.finance.models import Invoice, InvoiceDelivery, InvoiceIssue, InvoiceJob, InvoiceReview
from apps.identity.models import Grant
from tests.helpers import rev, setup_case
from tests.railway_client_detail_edit_seed import BILLING, CASE_ID, LEGAL, PRIMARY, PROCUREMENT, TRIAL, prepare


class ClientDetailEditFixtureTests(TestCase):
    def setUp(self):
        self.trial = get_user_model().objects.create_user(TRIAL)
        self.sample = prepare()
        self.case = Case.objects.get(pk=CASE_ID)
        self.url = self.sample['detail']
        self.client.force_login(self.trial)

    def person_post(self, **overrides):
        return {'purpose': 'project_person', 'revision': rev(self.case), 'entry': self.sample['person'],
                'name': 'SAMPLE Updated Procurement Lead', 'role': 'Contracting lead',
                'email': 'sample-updated-procurement@example.invalid', 'evidence': self.sample['person_proof'], **overrides}

    def test_trial_updates_legal_billing_and_named_contact_without_changing_invoice_or_primary(self):
        self.assertEqual(connection.vendor, 'postgresql')
        sample = self.sample
        before = {model: list(model.objects.all().values()) for model in (Invoice, InvoiceReview, InvoiceIssue, InvoiceJob)}
        start = self.client.get(self.url)
        for label in (LEGAL, PRIMARY, PROCUREMENT, BILLING, '10 SAMPLE Road', 'Issued invoices and applied receipts'):
            self.assertContains(start, label)
        amount = Decimal(sample['invoice_amount'])
        self.assertEqual(start.context['billing']['amounts'][0]['invoiced'], amount)
        legal = {'purpose': 'billing_identity', 'revision': rev(self.case), 'coverage': sample['coverage'],
                 'evidence': sample['correction'], 'legal_name': LEGAL, 'billing_address': '12 SAMPLE Road',
                 'tax_reference': 'SAMPLE-TAX-REF'}
        self.assertRedirects(self.client.post(self.url, legal), self.url)
        billing = {'purpose': 'billing', 'revision': rev(self.case), 'customer': sample['customer'],
                   'client_name': LEGAL, 'name': 'SAMPLE New Accounts Desk', 'role': 'Accounts',
                   'email': 'sample-billing-update@example.invalid', 'evidence': sample['correction']}
        self.assertRedirects(self.client.post(self.url, billing), self.url)

        edit = self.client.get(self.url + f"?project_contact={sample['person']}")
        self.assertContains(edit, 'Edit contact details')
        person = self.person_post()
        self.assertRedirects(self.client.post(self.url, person), self.url)
        saved = ClientProjectPersonRevision.objects.get(previous_id=sample['person'])
        self.assertEqual((saved.number, saved.evidence_id, saved.actor_id), (2, sample['person_proof'], self.trial.pk))
        original = ClientProjectPersonRevision.objects.get(pk=sample['person'])
        self.assertEqual(saved.person_key, original.person_key)
        newer = self.person_post(entry='', name='SAMPLE Patient Services', role='User liaison', email='')
        self.assertRedirects(self.client.post(self.url, newer), self.url)

        final = self.client.get(self.url)
        for label in ('12 SAMPLE Road', 'Earlier billing details', 'SAMPLE New Accounts Desk', PRIMARY,
                      'SAMPLE Updated Procurement Lead', 'SAMPLE Patient Services'):
            self.assertContains(final, label)
        self.assertNotContains(final, PROCUREMENT)
        self.assertEqual(final.context['billing']['amounts'][0]['invoiced'], amount)
        self.assertEqual(ClientBillingIdentityRevision.objects.get(previous_id=sample['legal']).actor_id, self.trial.pk)
        self.assertEqual(ClientContactRevision.objects.get(case=self.case, purpose='project').pk, sample['primary'])
        billing_history = ClientContactRevision.objects.filter(case=self.case, purpose='billing').order_by('number')
        self.assertEqual(list(billing_history.values_list('name', flat=True)), [BILLING, 'SAMPLE New Accounts Desk'])
        for model, history in before.items():
            self.assertEqual(list(model.objects.all().values()), history)
        self.assertFalse(InvoiceDelivery.objects.filter(invoice__case=self.case).exists())
        self.assertTrue(prepare()['preserved'])

    def test_contact_source_privacy_stale_revision_and_postgresql_history_guards(self):
        permission = get_user_model().objects.create_user('sample-client-finance-reader')
        Grant.objects.bulk_create(Grant(case=self.case, user=permission, action=action)
                                  for action in ('case.read', 'finance.read'))
        self.client.force_login(permission)
        self.assertNotContains(self.client.get(self.url), PROCUREMENT)
        self.assertEqual(self.client.post(self.url, self.person_post()).status_code, 403)
        self.client.force_login(self.trial)
        stale = self.person_post(revision=rev(self.case) - 1)
        self.assertContains(self.client.post(self.url, stale), 'Stale revision')
        outsider, other_case = setup_case(username='unrelated-sample-contact')
        foreign = add_evidence(outsider, other_case.pk, 'engagement_source', 'Another project', 'synthetic:other')
        self.assertContains(self.client.post(self.url, self.person_post(evidence=foreign.pk)), 'Select a valid choice')
        [original] = client_project_people.current(self.case)
        with self.assertRaises(DatabaseError), transaction.atomic():
            ClientProjectPersonRevision.objects.filter(pk=original.pk).update(name='Overwritten')
        with self.assertRaises(DatabaseError), transaction.atomic():
            ClientProjectPersonRevision.objects.create(case=self.case, previous=original, person_key=original.person_key,
                number=2, name='Wrong source', role='Procurement', evidence=foreign, actor=self.trial)
        self.assertEqual(client_project_people.current(self.case).get().pk, original.pk)
