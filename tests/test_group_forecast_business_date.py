"""Explicit synthetic clock authority; no monetary oracle or live recipients."""
from datetime import datetime
from importlib import import_module
from unittest.mock import patch
from django.conf import settings
from django.db import connection, transaction, DatabaseError
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.finance import group_forecast as group
from apps.documents.controlled import reserve_publication
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationReceipt
from .test_group_forecast import configured
from .helpers import rev

migration = import_module('apps.documents.migrations.0026_group_forecast_business_date')

class GroupForecastBusinessDateTests(TestCase):
    def test_established_default_zone_and_installed_guard_match_native(self):
        self.assertTrue(settings.USE_TZ)
        self.assertEqual(settings.TIME_ZONE, 'Africa/Lagos')
        self.assertEqual(timezone.get_current_timezone_name(), 'Africa/Lagos')
        with connection.cursor() as cursor:
            cursor.execute('SHOW timezone')
            self.assertEqual(cursor.fetchone()[0], 'UTC')
            cursor.execute("SELECT pg_get_functiondef('psl_group_forecast_publication()'::regprocedure)")
            body = cursor.fetchone()[0]
            self.assertIn('psl_group_forecast_business_date(clock_timestamp())::text', body)
            self.assertNotIn('CURRENT_DATE', body)
            for value in ['2026-11-06T22:59:59+00:00', '2026-11-06T23:00:00+00:00',
                          '2026-11-06T23:59:59+00:00', '2026-11-07T00:00:00+00:00',
                          '2026-11-07T12:00:00+00:00']:
                instant = datetime.fromisoformat(value)
                cursor.execute('SELECT psl_group_forecast_business_date(%s)', [instant])
                self.assertEqual(cursor.fetchone()[0], timezone.localdate(instant))

    def publication_at(self, value):
        instant = datetime.fromisoformat(value)
        day = timezone.localdate(instant)
        # Only the explicit clock inputs are supplied by the test. Domain,
        # publication, policy, review, receipt and trigger services stay real.
        fixed = "TIMESTAMPTZ '" + instant.isoformat() + "'"
        sql = migration.PUBLICATION.replace('psl_group_forecast_business_date(clock_timestamp())',
                                            'psl_group_forecast_business_date(' + fixed + ')')
        with connection.cursor() as cursor:
            cursor.execute(sql)
        with patch('django.utils.timezone.localdate', return_value=day):
            actor, case, run, recipient, template, policy, expected = configured()
            version = group.draft(actor, case.pk, run.pk, template.pk, rev(case))
            group.review(actor, case.pk, version.pk, 'Finance', 'approve', 'Exact synthetic clock disclosure', rev(case))
            if day != instant.date():
                # Reproduce the legacy UTC-date defect with the same explicit
                # instant, without changing connection/environment timezone.
                legacy = migration.PREVIOUS.replace('CURRENT_DATE::text',
                    '(' + fixed + " AT TIME ZONE 'UTC')::date::text")
                with connection.cursor() as cursor: cursor.execute(legacy)
                with self.assertRaisesMessage(DatabaseError, 'exact group disclosure'):
                    with transaction.atomic():
                        reserve_publication(actor, case.pk, version.pk, rev(case))
                with connection.cursor() as cursor: cursor.execute(sql)
            publication = reserve_publication(actor, case.pk, version.pk, rev(case))
            run_publication_once(case_id=case.pk)
            publication.job.refresh_from_db()
            self.assertEqual(publication.job.status, 'confirmed')
            self.assertEqual(group.verified(version)['recipient_count'], 1)
            receipt = PublicationReceipt.objects.get(publication=publication)
            self.assertNotIn('RESTRICTED_X', str(receipt.payload))
            self.assertNotIn('7391', str(receipt.payload))
        # The previous reviewed as-of is stale on the next native business day.
        from datetime import timedelta
        with patch('django.utils.timezone.localdate', return_value=day + timedelta(days=1)):
            with self.assertRaises(ValidationError): group.inputs(run)

    def test_real_reviewed_publication_before_lagos_midnight(self):
        self.publication_at('2026-11-06T22:59:59+00:00')

    def test_real_reviewed_publication_after_lagos_midnight_before_utc_midnight(self):
        self.publication_at('2026-11-06T23:00:01+00:00')

    def test_real_reviewed_publication_after_utc_midnight(self):
        self.publication_at('2026-11-07T00:00:01+00:00')

    def test_real_reviewed_publication_nonboundary(self):
        self.publication_at('2026-11-07T12:00:00+00:00')
