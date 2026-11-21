import json
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.views.debug import get_default_exception_reporter_filter

from apps.core.evidence_access import public_evidence, public_timeline
from apps.core.models import Evidence
from apps.core.services import add_evidence
from apps.finance import hrfinance, payroll, payroll_identity as names, payroll_identity_views
from apps.finance.payroll_models import PayrollHRFollowup, PayrollPublication
from apps.identity.models import Grant
from apps.policy.payroll_validators import ACCESS, NAME_CHECK
from tests.helpers import rev
from tests.payroll_helpers import approve, body, combined, fixture, policy


class PayrollIdentityTests(TestCase):
    def setUp(self):
        self.f = f = fixture()
        self.case = f['case']
        # The payroll export and HR snapshot have different actual holders.
        self.payroll_owner, self.hr_owner, self.reader = f['preparer'], f['owner'], f['reviewer']
        access = deepcopy(f['config']['access'])
        for provider in access['providers']:
            provider.update(owner_id=self.payroll_owner.pk, owner_role='Finance')
        policy(f, ACCESS, access)
        f['inputs'] = [payroll.capture(self.payroll_owner, self.case.pk, f['request'].pk,
            source['provider'], 'name-input-' + str(i), body(f, i), rev(self.case))
            for i, source in enumerate(f['config']['exports'])]
        self.input = f['inputs'][0]
        row = self.input.payload['rows'][0]
        self.row, self.employee = row['row_ref'], row['employee_id']
        self.parent = combined(f)
        approve(f, self.parent)
        self.path = reverse('payroll_name_checks', args=[self.case.pk])

    def configure(self, readers):
        policy(self.f, NAME_CHECK, {'comparison': 'exact_as_supplied' if readers else None, 'reader_ids': readers})

    def match(self):
        return payroll.match(self.payroll_owner, self.case.pk, self.parent.pk, self.f['hr'].pk,
                             str(uuid4()), rev(self.case))

    def capture(self, actor, side, record, row, value):
        self.client.force_login(actor)
        return self.client.post(self.path, {'action': side, 'record': record, 'row': row, 'name': value,
            'reference': 'Fictional source holder reference', 'revision': rev(self.case)})

    def test_optional_name_discrepancy_routes_existing_hr_review_without_exposing_names(self):
        self.configure([self.reader.pk, self.payroll_owner.pk])
        match = self.match()
        grants = set(Grant.objects.filter(case=self.case).values_list('user_id', 'action', 'active'))
        self.client.force_login(self.reader)
        fields = {'action': 'check', 'run': match.pk, 'input_record': self.input.pk, 'row': self.row}
        missing = self.client.post(self.path, {**fields, 'revision': rev(self.case)}, follow=True)
        self.assertContains(missing, 'Waiting for both source names.')
        self.assertNotContains(missing, 'Send to HR for correction')
        self.assertEqual(self.capture(self.reader, 'payroll', self.input.pk, self.row, 'Caller claim').status_code, 403)
        self.assertEqual(self.capture(self.payroll_owner, 'hr', self.f['hr'].pk, self.employee, 'Caller claim').status_code, 403)
        payroll_name, hr_name = 'Fictional Ada North', 'Fictional Ada West'
        self.assertRedirects(self.capture(self.payroll_owner, 'payroll', self.input.pk, self.row, payroll_name),
                             self.path, fetch_redirect_response=False)
        self.assertRedirects(self.capture(self.hr_owner, 'hr', self.f['hr'].pk, self.employee, hr_name),
                             self.path, fetch_redirect_response=False)
        self.assertEqual(Evidence.objects.filter(case=self.case, kind=names.KIND).count(), 2)
        self.assertFalse(public_evidence(Evidence.objects.filter(case=self.case, kind=names.KIND)).exists())
        self.assertFalse(public_timeline(self.case).filter(action=names.FACT).exists())

        self.client.force_login(self.reader)
        checked = self.client.post(self.path, {**fields, 'revision': rev(self.case)}, follow=True)
        self.assertContains(checked, 'different names for the same staff ID')
        self.assertNotContains(checked, payroll_name)
        self.assertNotContains(checked, hr_name)
        comparison = checked.context['comparison']['id']
        routed = self.client.post(self.path, {'action': 'route', 'comparison': comparison,
                                               'revision': rev(self.case)}, follow=True)
        self.assertContains(routed, 'Awaiting HR review')
        followup = PayrollHRFollowup.objects.get(run=match)
        self.assertEqual(followup.record.snapshot_id, self.f['hr'].pk)
        self.assertFalse(followup.record.payload['source_write'])
        self.client.force_login(self.payroll_owner)
        same_check = self.client.post(self.path, {**fields, 'revision': rev(self.case)}, follow=True)
        self.assertEqual(same_check.context['comparison']['id'], comparison)
        self.client.post(self.path, {'action': 'route', 'comparison': comparison, 'revision': rev(self.case)})
        self.assertEqual(PayrollHRFollowup.objects.filter(run=match).count(), 1)

        self.client.force_login(self.hr_owner)
        hr_workspace = reverse('design_project_tab', args=[self.case.pk, 'hr'])
        queue_path = reverse('design_hr_payroll_corrections', args=[self.case.pk])
        self.assertContains(self.client.get(hr_workspace), queue_path)
        hr_path = reverse('design_hr_payroll_correction', args=[self.case.pk, followup.pk])
        self.assertContains(self.client.get(queue_path), hr_path)
        self.assertNotContains(self.client.get(hr_path), payroll_name)
        proof = add_evidence(self.hr_owner, self.case.pk, 'hr_correction_response',
                             'Fictional decision evidence for the supplied successor.', 'synthetic:payroll-name')
        old = self.f['hr']
        successor = hrfinance.capture(self.hr_owner, self.case.pk, old.contract_id, 'name-snapshot-successor',
            json.dumps(dict(old.payload, source_version='name-snapshot-v2')), rev(self.case))
        result = self.client.post(hr_path, {'verdict': 'approve', 'successor': successor.pk, 'evidence': proof.pk,
                                            'revision': rev(self.case), 'operation_key': uuid4()})
        self.assertRedirects(result, hr_path, fetch_redirect_response=False)
        self.client.force_login(self.reader)
        reviewed = self.client.get(f'{self.path}?check={comparison}')
        self.assertContains(reviewed, 'Corrected HR export approved')
        self.assertNotContains(reviewed, hr_name)
        self.assertFalse(PayrollPublication.objects.filter(request__case=self.case).exists())
        self.assertNotIn('name', json.dumps(match.result))

        self.client.force_login(self.f['manager'])
        page = self.client.get(f'{self.path}?check={comparison}')
        self.assertNotContains(page, 'Recorded name check')
        self.assertFalse(hrfinance.correction_disposition(followup.record).get().payload['source_write'])
        self.assertEqual(set(Grant.objects.filter(case=self.case).values_list('user_id', 'action', 'active')), grants)

        Grant.objects.filter(user=self.hr_owner, case=self.case, action='hrfinance.respond').update(active=False)
        self.client.force_login(self.hr_owner)
        self.assertNotContains(self.client.get(hr_workspace), queue_path)
        self.assertEqual(self.client.get(hr_path).status_code, 403)

    def test_legacy_and_unset_rule_keep_matching_by_id_without_turning_membership_into_departure(self):
        self.client.force_login(self.reader)
        self.assertContains(self.client.get(self.path), 'Name checks need a reviewed rule')
        legacy = self.match()
        self.assertEqual(legacy.metadata['status'], 'complete')
        with self.assertRaises(ValidationError):
            names.check(self.reader, self.case.pk, legacy.pk, self.input.pk, self.row, rev(self.case))
        approve(self.f, legacy)
        aggregate = payroll.aggregate(self.payroll_owner, self.case.pk, legacy.pk, 'name-continuity-aggregate', rev(self.case))
        approve(self.f, aggregate)
        publication = payroll.publish(self.payroll_owner, self.case.pk, aggregate.pk, 'name-continuity-report', rev(self.case))
        expected = payroll.read_publication(self.f['manager'], publication.pk)

        optional_reader = get_user_model().objects.create_user(username='name-only-reader')
        self.configure([self.reader.pk, optional_reader.pk])
        optional_reader.is_active = False
        optional_reader.save(update_fields=['is_active'])
        self.assertEqual(names.check(self.reader, self.case.pk, legacy.pk, self.input.pk, self.row,
                                     rev(self.case)).data['result'], 'awaiting_source')
        self.assertEqual(payroll.read_publication(self.f['manager'], publication.pk), expected)
        self.configure([])
        current = self.match()
        self.assertEqual(current.result, legacy.result)
        self.assertEqual(payroll.read_publication(self.f['manager'], publication.pk), expected)
        self.assertEqual(payroll.private_run(self.reader, self.case.pk, legacy.pk), legacy.result)
        self.assertNotIn('employment', json.dumps(current.result))
        self.assertNotIn('departure', json.dumps(current.result))
        self.assertFalse(Evidence.objects.filter(case=self.case, kind=names.KIND).exists())

    def test_current_reader_authority_is_required_before_private_name_proof(self):
        self.configure([self.reader.pk])
        match = self.match()
        self.capture(self.payroll_owner, 'payroll', self.input.pk, self.row, 'Fictional Identical Name')
        self.capture(self.hr_owner, 'hr', self.f['hr'].pk, self.employee, 'Fictional Identical Name')
        checked = names.check(self.reader, self.case.pk, match.pk, self.input.pk, self.row, rev(self.case))
        self.assertEqual(checked.data['result'], 'same')
        with self.assertRaisesMessage(ValidationError, 'Only a confirmed name difference'):
            names.route(self.reader, self.case.pk, checked.pk, rev(self.case))
        for actor, action in ((self.payroll_owner, 'evidence.add'), (self.hr_owner, 'hrfinance.read')):
            grant = Grant.objects.filter(case=self.case, user=actor, action=action)
            grant.update(active=False)
            try:
                with patch.object(names, 'current_fact', side_effect=AssertionError('Revoked holder cannot release names')):
                    with self.assertRaises(PermissionDenied):
                        names.readback(self.reader, self.case.pk, checked.pk)
            finally:
                grant.update(active=True)
        self.capture(self.hr_owner, 'hr', self.f['hr'].pk, self.employee, 'Fictional Successor Name')
        with self.assertRaisesMessage(ValidationError, 'Source evidence changed'):
            names.readback(self.reader, self.case.pk, checked.pk)
        Grant.objects.filter(case=self.case, user=self.reader, action='payroll.private.read').update(active=False)
        with patch.object(names, 'current_fact', side_effect=AssertionError('Denied reader cannot open names')):
            with self.assertRaises(PermissionDenied):
                names.readback(self.reader, self.case.pk, checked.pk)

    @override_settings(DEBUG=False)
    def test_name_and_source_reference_are_redacted_from_django_exception_details(self):
        self.configure([self.reader.pk])
        fictional_name = 'Sensitive fictional record holder name'
        request = RequestFactory().post(self.path, {'action': 'payroll', 'record': self.input.pk, 'row': self.row,
            'name': fictional_name, 'reference': 'Sensitive fictional source reference', 'revision': rev(self.case)})
        request.user = self.payroll_owner
        redact = get_default_exception_reporter_filter()
        with patch.object(names, 'add_evidence', side_effect=RuntimeError('Synthetic private capture failure')):
            try:
                payroll_identity_views.workbench(request, self.case.pk)
            except RuntimeError as exc:
                self.assertEqual(str(exc), 'Synthetic private capture failure')
                post = redact.get_post_parameters(request)
                self.assertEqual(post['name'], redact.cleansed_substitute)
                self.assertEqual(post['reference'], redact.cleansed_substitute)
                frames = []
                tb = exc.__traceback__
                while tb is not None:
                    if tb.tb_frame.f_globals.get('__name__') == names.__name__ and tb.tb_frame.f_code.co_name == 'capture':
                        frames.append(dict(redact.get_traceback_frame_variables(request, tb.tb_frame)))
                    tb = tb.tb_next
                self.assertEqual(len(frames), 1)
                self.assertEqual(frames[0]['name'], redact.cleansed_substitute)
                self.assertEqual(frames[0]['body'], redact.cleansed_substitute)
            else:
                self.fail('The guarded test must raise after receiving private fields.')
