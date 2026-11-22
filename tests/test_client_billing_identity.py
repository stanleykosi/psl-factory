"""Legal billing details have their own scoped, source-bound history."""

from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.urls import reverse

from apps.core.client_contacts import save as save_contact
from apps.core.models import ClientBillingIdentityRevision, ClientContactRevision
from apps.core.services import add_evidence
from apps.finance.models import Invoice, InvoiceIssue, InvoiceJob, InvoiceReview
from apps.identity.models import Grant
from tests import settlement_helpers
from tests.billing_helpers import coverage
from tests.helpers import rev
from tests.obligation_helpers import issue_identified


class ClientBillingIdentityTests(TestCase):
    def test_separate_author_readers_and_predecessor_preserve_contact_and_issued_invoice(self):
        self.assertEqual(connection.vendor, 'postgresql')
        preparer, case, customer, preparation, proofs = settlement_helpers.fixture()
        invoice = settlement_helpers.draft(preparer, case, preparation)
        issue = issue_identified(preparer, case, invoice, proofs)
        snapshots = {
            Invoice: list(Invoice.objects.filter(case=case).values()),
            InvoiceReview: list(InvoiceReview.objects.filter(invoice=invoice).values()),
            InvoiceIssue: list(InvoiceIssue.objects.filter(invoice=invoice).values()),
            InvoiceJob: list(InvoiceJob.objects.filter(invoice=invoice).values()),
        }
        self.assertEqual(snapshots[InvoiceIssue][0]['id'], issue.pk)
        contact = save_contact(preparer, case, 'billing', {'revision': rev(case), 'evidence': customer.evidence,
            'customer': customer.customer, 'client_name': 'Sample client', 'name': 'Accounts office',
            'email': 'billing@example.invalid', 'role': 'Billing'})
        old_contact = list(ClientContactRevision.objects.filter(pk=contact.pk).values())
        other = coverage(preparer, case, reference='other-customer-coverage', customer='SAMPLE-OTHER')
        revised_proof = add_evidence(preparer, case.pk, 'policy_decision', 'Sample corrected legal billing details.',
                                     'synthetic:billing-identity')
        create = get_user_model().objects.create_user
        author = create('sample-legal-billing-author')
        reader = create('sample-legal-billing-reader')
        project_reader = create('sample-project-contact-reader')
        for actor, actions in (
            (author, ('case.read', 'finance.read', 'finance.billing.register')),
            (reader, ('case.read', 'finance.read')),
            (project_reader, ('case.read', 'engagement.read')),
        ):
            Grant.objects.bulk_create([Grant(case=case, user=actor, action=action) for action in actions])
        url = reverse('design_client_project', args=[case.pk])
        values = {'purpose': 'billing_identity', 'coverage': customer.pk, 'evidence': customer.evidence_id,
                  'revision': rev(case), 'legal_name': 'Sample First Legal Name',
                  'billing_address': 'Test street 1\r\nSample city', 'tax_reference': ''}

        self.client.force_login(project_reader)
        self.assertNotContains(self.client.get(url), 'Legal billing details')
        self.assertEqual(self.client.post(url, values).status_code, 403)
        self.client.force_login(reader)
        page = self.client.get(url)
        self.assertContains(page, 'Legal billing details')
        self.assertContains(page, '<dt>Tax reference</dt><dd>Unknown</dd>', html=True)
        self.assertNotContains(page, 'Save billing details')
        self.assertEqual(self.client.post(url, values).status_code, 403)
        self.client.force_login(author)
        self.assertContains(self.client.get(url), 'Save billing details')
        self.assertContains(self.client.post(url, {**values, 'evidence': other.evidence_id}),
                            'the evidence for the selected coverage')
        self.assertFalse(ClientBillingIdentityRevision.objects.exists())
        self.assertRedirects(self.client.post(url, values), url, fetch_redirect_response=False)
        original = ClientBillingIdentityRevision.objects.get(case=case)
        self.assertEqual((original.coverage_id, original.customer_ref, original.actor_id),
                         (customer.pk, customer.customer, author.pk))
        self.assertEqual((original.number, original.previous_id, original.tax_reference, original.billing_address),
                         (1, None, None, 'Test street 1\nSample city'))
        stale = {**values, 'legal_name': 'Overwritten history'}
        self.assertContains(self.client.post(url, stale), 'Stale revision')
        self.assertEqual(ClientBillingIdentityRevision.objects.count(), 1)
        new_values = {**values, 'revision': rev(case), 'evidence': revised_proof.pk, 'legal_name': 'Sample Revised Legal Name',
                      'billing_address': '', 'tax_reference': 'SAMPLE-REF-002'}
        self.assertRedirects(self.client.post(url, new_values), url, fetch_redirect_response=False)
        successor = ClientBillingIdentityRevision.objects.get(case=case, number=2)
        self.assertEqual((successor.previous_id, successor.billing_address, successor.evidence_id),
                         (original.pk, None, revised_proof.pk))
        self.assertRedirects(self.client.post(url, {**new_values, 'revision': rev(case)}), url,
                             fetch_redirect_response=False)
        self.assertEqual(ClientBillingIdentityRevision.objects.count(), 2)
        with self.assertRaises(DatabaseError), transaction.atomic():
            ClientBillingIdentityRevision.objects.filter(pk=original.pk).update(legal_name='Overwrite')
        with self.assertRaises(DatabaseError), transaction.atomic():
            ClientBillingIdentityRevision.objects.create(
                case=case, coverage=other, customer_ref=customer.customer, number=3, previous=successor,
                evidence=revised_proof, actor=author,
            )

        self.client.force_login(reader)
        page = self.client.get(url)
        for label in ['Sample Revised Legal Name', 'SAMPLE-REF-002', 'Earlier billing details',
                      'Sample First Legal Name', 'Accounts office']:
            self.assertContains(page, label)
        self.assertNotContains(page, 'Save billing details')
        self.client.force_login(project_reader)
        self.assertNotContains(self.client.get(url), 'SAMPLE-REF-002')
        self.assertEqual(list(ClientContactRevision.objects.filter(case=case).values()), old_contact)
        for model, before in snapshots.items():
            query = model.objects.filter(case=case) if model is Invoice else model.objects.filter(invoice=invoice)
            self.assertEqual(list(query.values()), before)
