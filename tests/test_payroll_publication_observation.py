from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.core.read_observation import observation_scope
from apps.finance import payroll
from apps.finance.payroll_models import PayrollReportReceipt
from apps.identity.models import Grant
from tests.helpers import rev
from tests.payroll_helpers import fixture, pipeline


class PayrollPublicationObservationTests(TestCase):
    def test_pure_aggregate_read_rechecks_current_source_and_never_records_receipts(self):
        self.assertEqual(connection.vendor, 'postgresql')
        sample = fixture()
        case, recipient = sample['case'], sample['manager']
        *_, publication = pipeline(sample)
        revision = rev(case)
        original_audit_count = case.audit.count()

        with observation_scope(), CaptureQueriesContext(connection) as before:
            value = payroll.observe_publication(recipient, publication.pk)
        self.assertEqual(value['by_bu'], {'BU-A': '250.00'})
        self.assertNotIn('rows', value)
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))
                             for query in before.captured_queries))
        self.assertEqual(rev(case), revision)
        self.assertEqual(case.audit.count(), original_audit_count)
        self.assertFalse(PayrollReportReceipt.objects.filter(publication=publication).exists())

        with observation_scope(), self.assertRaisesMessage(ValidationError, 'Read-only observation cannot execute'):
            payroll.receive_report(recipient, case.pk, publication.pk, revision)
        with observation_scope(), self.assertRaises(PermissionDenied):
            payroll.observe_publication(sample['preparer'], publication.pk)
        with self.assertRaises(PermissionDenied):
            payroll.receive_report(sample['preparer'], case.pk, publication.pk, revision)

        grant = Grant.objects.get(case=case, user=sample['owner'], action='payroll.capture')
        Grant.objects.filter(pk=grant.pk).update(active=False)
        with observation_scope(), self.assertRaises(PermissionDenied):
            payroll.observe_publication(recipient, publication.pk)
        with self.assertRaises(PermissionDenied):
            payroll.receive_report(recipient, case.pk, publication.pk, revision)
        self.assertFalse(PayrollReportReceipt.objects.filter(publication=publication).exists())

        Grant.objects.filter(pk=grant.pk).update(active=True)
        receipt = payroll.receive_report(recipient, case.pk, publication.pk, revision)
        self.assertEqual(receipt.actor_id, recipient.pk)
