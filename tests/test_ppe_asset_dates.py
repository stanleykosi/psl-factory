"""Exact asset date evidence, independent approval and optional configured fractions."""

import json
from copy import deepcopy
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.evidence_access import public_evidence
from apps.core.models import Evidence
from apps.core.services import add_evidence
from apps.finance import ppe, ppe_dates
from apps.finance.models import ScheduleWork
from apps.identity.models import Grant
from apps.workflows import factory, factory_ppe
from tests import ppe_helpers, test_factory_ppe
from tests.helpers import rev


class PPEAssetDateTests(TestCase):
    def setUp(self):
        fixture = test_factory_ppe.FactoryPPETests()
        fixture.setUp()
        self.f = fixture.f
        self.maker, self.case, self.reviewer = (self.f[key] for key in ('actor', 'case', 'reviewer'))

    def record(self, basis=ppe_dates.DERIVED, service='2026-10-10', register=None, **fields):
        value = {'asset_id': 'A1', 'delivery_date': '2026-10-02', 'in_service_date': service,
                 'fraction_basis': basis, 'evidence_id': self.f['e']['ppe_event'].pk, **fields}
        return ppe.record_dates(self.maker, self.case.pk, (register or self.f['register']).pk,
                                expected=rev(self.case), **value)

    def configured_value(self, *, author=None):
        scope = {'category': 'equipment', 'period_start': '2026-10-01', 'period_end': '2026-10-20'}
        rules = [dict(scope, in_service_from='2026-10-10', in_service_through='2026-10-12', fraction='1')]
        oracles = [dict(scope, in_service_date='2026-10-10', expected_fraction='1'),
                   dict(scope, in_service_date='2026-10-13', expected_fraction=None)]
        proof = add_evidence(author or self.reviewer, self.case.pk, 'finance_oracle',
                             json.dumps({'contract': ppe_dates.ORACLE_CONTRACT, 'cases': oracles}),
                             'synthetic:ppe-in-service-independent-example')
        return {'method_evidence_id': self.f['e']['ppe_policy'].pk, 'oracle_evidence_id': proof.pk,
                'rules': rules, 'oracles': oracles}

    def sql_current(self, schedule):
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_ppe_schedule_current(%s)', [schedule.pk])
            return cursor.fetchone()[0]

    def test_typed_dates_need_independent_review_and_exact_explicit_fraction_rule(self):
        original = self.f['register']
        self.client.force_login(self.maker)
        native_page = reverse('ppe', args=[self.case.pk])
        saved = self.client.post(native_page, {'action': 'record_dates', 'register': original.pk, 'asset_id': 'A1',
            'delivery_date': '2026-10-02', 'in_service_date': '2026-10-10', 'fraction_basis': ppe_dates.DERIVED,
            'evidence': self.f['e']['ppe_event'].pk, 'revision': rev(self.case)})
        self.assertRedirects(saved, native_page, fetch_redirect_response=False)
        dated = ScheduleWork.objects.get(case=self.case, kind='ppe_register', reference=original.reference,
                                         version=original.version + 1)
        self.assertEqual((dated.reference, dated.version), (original.reference, original.version + 1))
        self.assertEqual(dated.payload['assets'][0]['dates']['delivery_date'], '2026-10-02')
        self.assertEqual(dated.payload['assets'][0]['dates']['in_service_date'], '2026-10-10')
        protected = public_evidence(Evidence.objects.filter(case=self.case, pk=dated.evidence_id))
        self.assertFalse(protected.exists())
        self.assertNotIn('dates', original.payload['assets'][0])
        self.assertFalse(dated.result['date_basis_ambiguous'])
        self.assertTrue(ppe_dates.needs_review(dated))
        ppe_helpers.review(self.f, dated, 'register')

        work = factory_ppe.start(self.maker, self.case.pk, 'date-basis-work', dated.pk,
                                 None, self.f['parent'].pk, 'date-basis-work', rev(self.case))
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertEqual(factory_ppe.report(work, self.reviewer)['stage'], 'basis_review')
        self.assertIsNone(factory_ppe.schedule(work))
        decision = reverse('factory_invoice_decision', args=[work.pk])
        self.client.force_login(self.maker)
        self.assertContains(self.client.get(decision), 'Delivery and in-service dates for independent review')
        self.assertNotContains(self.client.get(decision), 'Approve exact basis')
        self.client.force_login(self.reviewer)
        page = self.client.get(decision)
        self.assertContains(page, '2026-10-10')
        self.assertContains(page, 'Approve exact basis')
        basis = ppe_helpers.review(self.f, dated, 'basis')
        held = ppe_helpers.prepare(self.f, dated, reference='asset-date-native')
        self.assertEqual(held.snapshot['basis_review'], basis.pk)
        self.assertIn('in_service_fraction_rule_required', held.result['rows'][0]['findings'])
        self.assertIsNone(held.result['rows'][0]['charge'])
        self.assertFalse(self.sql_current(held))

        config = ppe_helpers.policy(self.f, ppe_dates.COMPONENT, self.configured_value())
        ready = ppe_helpers.prepare(self.f, dated, reference='asset-date-native')
        self.assertEqual(ready.snapshot['policies'][ppe_dates.COMPONENT]['id'], config.pk)
        self.assertEqual((ready.result['status'], ready.result['rows'][0]['charge'],
                          ready.result['rows'][0]['used_fraction']), ('ready', '100.00', '1'))
        self.assertTrue(self.sql_current(ready))
        self.assertFalse(self.sql_current(held))
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_ppe_asset_dates_current(%s,%s,NULL)', [ready.pk, dated.pk])
            self.assertEqual(cursor.fetchone(), (False,))
        copied_source_holder = get_user_model().objects.create_user('sample-asset-register-successor')
        Grant.objects.bulk_create([Grant(case=self.case, user=copied_source_holder, action=action)
                                   for action in ppe_dates.FACT_ACTIONS])
        copy_fixture = dict(self.f, actor=copied_source_holder)
        changed_values = deepcopy(dated.payload)
        changed_values['assets'][0]['dates']['in_service_date'] = '2026-10-11'
        with self.assertRaisesMessage(ValidationError, 'differ from the exact recorded asset evidence'):
            with transaction.atomic():
                ppe_helpers.capture(copy_fixture, changed_values, 'changed-asset-date-evidence')
        repackaged = ppe_helpers.capture(copy_fixture, dated.payload, 'same-date-fact-repackaged')
        for purpose in ('register', 'basis'):
            ppe_helpers.review(self.f, repackaged, purpose)
        repackaged_schedule = ppe_helpers.prepare(self.f, repackaged, reference='repackaged-evidence-schedule')
        self.assertTrue(self.sql_current(repackaged_schedule))
        source_owner = Grant.objects.filter(case=self.case, user=self.maker, action='evidence.add')
        source_owner.update(active=False)
        with self.assertRaises(PermissionDenied):
            ppe.current(ready)
        self.assertFalse(self.sql_current(ready))
        with self.assertRaises(PermissionDenied):
            ppe.current(repackaged)
        self.assertFalse(self.sql_current(repackaged_schedule))
        response = self.client.get(decision)
        self.assertNotContains(response, 'Delivery and in-service dates for independent review')
        self.assertNotContains(response, '2026-10-10')

    def test_unknown_dates_and_optional_review_do_not_change_the_supplied_fraction_method(self):
        unknown = self.record(service=None)
        for purpose in ('register', 'basis'):
            ppe_helpers.review(self.f, unknown, purpose)
        ppe_helpers.policy(self.f, ppe_dates.COMPONENT, self.configured_value())
        held = ppe_helpers.prepare(self.f, unknown, reference='asset-unknown-service')
        self.assertIn('in_service_date_unknown', held.result['rows'][0]['findings'])
        self.assertIsNone(held.result['rows'][0]['used_fraction'])
        self.assertIsNone(held.result['rows'][0]['charge'])
        self.assertFalse(self.sql_current(held))

        legacy = ppe_helpers.capture(self.f, reference='unchanged-asset-fraction')
        ppe_helpers.review(self.f, legacy, 'register')
        ordinary = ppe_helpers.prepare(self.f, legacy, reference='ordinary-supplied-fraction')
        self.assertNotIn(ppe_dates.COMPONENT, ordinary.snapshot['policies'])
        self.assertNotIn('used_fraction', ordinary.result['rows'][0])
        self.assertEqual(ordinary.result['status'], 'ready')
        self.assertTrue(self.sql_current(ordinary))

        dated = self.record(basis=ppe_dates.SUPPLIED, register=legacy)
        for purpose in ('register', 'basis'):
            ppe_helpers.review(self.f, dated, purpose)
        result = ppe_helpers.prepare(self.f, dated, reference='date-facts-supplied-fraction')
        self.assertNotIn(ppe_dates.COMPONENT, result.snapshot['policies'])
        self.assertEqual(result.result, ordinary.result)
        self.assertTrue(self.sql_current(result))

    def test_input_and_policy_validation_reject_missing_provenance_and_overlapping_ranges(self):
        with self.assertRaises(ValidationError):
            self.record(delivery_date=(timezone.localdate() + timedelta(days=1)).isoformat())
        with self.assertRaises(ValidationError):
            self.record(evidence_id=self.f['e']['finance_review'].pk)
        with self.assertRaises(ValidationError):
            self.record(asset_id='unselected-asset')
        self.assertEqual(self.f['register'].version, 1)
        same_author = self.configured_value(author=self.maker)
        with self.assertRaisesMessage(ValidationError, 'independent author'):
            ppe_helpers.policy(self.f, ppe_dates.COMPONENT, same_author)
        config = self.configured_value()
        bad = deepcopy(config)
        bad['rules'].append(dict(bad['rules'][0], in_service_from='2026-10-12', fraction='0'))
        with self.assertRaisesMessage(ValidationError, 'non-overlapping'):
            ppe_helpers.policy(self.f, ppe_dates.COMPONENT, bad)
        bad = deepcopy(config)
        bad['rules'][0]['fraction'] = '0'
        with self.assertRaisesMessage(ValidationError, 'does not match its independent reference example'):
            ppe_helpers.policy(self.f, ppe_dates.COMPONENT, bad)
