"""Acceptance setup serializes account changes without blocking native date evidence commits."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import OperationalError, connection, connections, transaction
from django.test import TransactionTestCase

from apps.core.models import Case, Evidence
from apps.finance import ppe, ppe_dates
from apps.finance.models import ScheduleWork
from apps.identity import staff
from apps.identity.models import StaffAdmission
from tests import railway_admitted_ppe_asset_dates_seed as seed, railway_admitted_schedule_seed as admission_seed
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_staff_profiles import configured


ENVIRONMENT = {'RAILWAY_PROJECT_ID': PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
               'PSL_COMPOSED_WALKTHROUGH': '1', seed.GUARD: '1'}


@patch.dict('os.environ', ENVIRONMENT)
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class AdmittedPPEAssetDateLockingTests(TransactionTestCase):
    def test_fixture_account_lock_allows_independent_browser_commit_with_unknown_date(self):
        initial = configured()
        origin = initial['scopes'][0]['case']
        users = get_user_model().objects
        reviewer = users.create_user('psl-agent-trial')
        invitation, token = staff.invite(initial['actor'], origin.pk, 'sample-asset-dates-locking', 'Sample dates preparer',
                                         'sample-date-locking@example.invalid', ['case.read'], rev(origin),
                                         profile_key='sample-reader')
        maker = staff.accept(token, 'Synthetic!asset.lock.demo.250')
        sample = seed.prepare(invitation.pk, maker.pk)
        case = Case.objects.get(pk=sample['case'], tenant=seed.TENANT, synthetic=True)
        original = ppe.exact(case, sample['register'], 'ppe_register')
        self.client.force_login(maker)
        admitted = Event()
        release = Event()

        def hold_admission():
            try:
                with transaction.atomic():
                    admission, active_user = admission_seed.admitted_user(invitation.pk, maker.pk, reviewer)
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT pg_backend_pid()')
                        backend_id = cursor.fetchone()[0]
                    admitted.set()
                    if not release.wait(30):
                        raise RuntimeError('The concurrent fixture lock was not released by the test.')
                    return admission.pk, active_user.pk, backend_id
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as pool:
            held = pool.submit(hold_admission)
            try:
                self.assertTrue(admitted.wait(10), 'The fixture must hold its admission and user row locks.')
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()')
                    browser_backend = cursor.fetchone()[0]
                    cursor.execute("SET lock_timeout = '3s'")
                try:
                    for rows in (users.filter(pk=maker.pk), StaffAdmission.objects.filter(invitation=invitation)):
                        with self.assertRaises(OperationalError) as locked, transaction.atomic():
                            rows.select_for_update(nowait=True, no_key=True).get()
                        self.assertEqual(locked.exception.__cause__.sqlstate, '55P03')

                    result = self.client.post(sample['asset_path'], {'action': 'record_dates', 'register': original.pk,
                        'asset_id': sample['asset'], 'delivery_date': sample['delivery_date'], 'in_service_date': '',
                        'fraction_basis': ppe_dates.DERIVED, 'evidence': sample['missing_support'], 'revision': rev(case)})
                    self.assertRedirects(result, sample['asset_path'], fetch_redirect_response=False)
                    self.assertFalse(held.done(), 'The browser commit must finish while the fixture still holds its locks.')
                    dates = ScheduleWork.objects.get(case=case, kind='ppe_register', reference=original.reference,
                                                     version=original.version + 1).payload['assets'][0]['dates']
                    self.assertEqual(dates['delivery_date'], sample['delivery_date'])
                    self.assertIsNone(dates['in_service_date'])
                    self.assertEqual(Evidence.objects.filter(case=case, kind=ppe_dates.FACT_KIND,
                                                             created_by=maker).count(), 1)
                finally:
                    with connection.cursor() as cursor:
                        cursor.execute('RESET lock_timeout')
            finally:
                release.set()
            admitted_id, active_user_id, fixture_backend = held.result(timeout=10)

        self.assertEqual(admitted_id, StaffAdmission.objects.get(invitation=invitation).pk)
        self.assertEqual(active_user_id, maker.pk)
        self.assertNotEqual(fixture_backend, browser_backend)
