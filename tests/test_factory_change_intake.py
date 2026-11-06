"""P56 request-first HTTP path; independent increment, not whole-process acceptance."""
from django.test import TestCase
from django.urls import reverse
from apps.core.models import Audit
from apps.identity.models import Grant
from apps.agents.models import AgentRun
from apps.pmo.models import ChangeAuthorization, ChangeVersion
from apps.workflows import factory_change_intake as intake
from apps.workflows.models import ChangeIntakeConfirmation
from tests.helpers import rev, setup_case
from tests.test_change_intake import IntakeFixture, BODY, fields


class FactoryChangeIntakeTests(IntakeFixture, TestCase):
    def setUp(self):
        super().setUp(); self.client.force_login(self.actor)

    def url(self, receipt):
        return reverse('p56_intake_detail', args=[self.case.pk, receipt.pk])

    def payload(self, run=None, **changes):
        values = {key: '' if value is None else value for key, value in fields().items()}
        values.update(action='confirm', case_revision=rev(self.case),
                      extraction_id=run.pk if run else '', note='PM checked and edited the source fields')
        values.update(changes)
        return values

    def test_receive_extract_pm_edit_confirm_redirects_to_existing_factory(self):
        start = reverse('p56_intake', args=[self.case.pk])
        before = rev(self.case); page = self.client.get(start)
        self.assertEqual(page.status_code, 200); self.assertEqual(page['Cache-Control'], 'no-store')
        self.assertEqual(rev(self.case), before)
        response = self.client.post(start, {'key': 'http-1', 'body': BODY, 'origin': 'synthetic:request', 'case_revision': before})
        receipt = Audit.objects.get(action=intake.RECEIVED)
        self.assertRedirects(response, self.url(receipt), fetch_redirect_response=False)
        page = self.client.get(self.url(receipt)); self.assertContains(page, 'Synthetic client')
        self.assertFalse(ChangeVersion.objects.exists())
        response = self.client.post(self.url(receipt), {'action': 'extract', 'case_revision': rev(self.case)})
        self.assertRedirects(response, self.url(receipt), fetch_redirect_response=False)
        run = AgentRun.objects.get(process_id='P56')
        page = self.client.get(self.url(receipt)); self.assertContains(page, '2026-01-02')
        response = self.client.post(self.url(receipt), self.payload(run, description='PM edited the view scope'))
        binding = ChangeIntakeConfirmation.objects.get(receipt=receipt)
        self.assertRedirects(response, reverse('factory_detail', args=[binding.work_id]), fetch_redirect_response=False)
        self.assertEqual(binding.version.description, 'PM edited the view scope')
        self.assertEqual(binding.payload['fields']['requestor'], 'Synthetic client')
        self.assertFalse(ChangeAuthorization.objects.exists())
        self.assertEqual(self.client.get(reverse('factory_detail', args=[binding.work_id])).status_code, 200)

    def test_missing_required_fields_and_stale_edit_render_without_native_write(self):
        receipt = self.receive()
        response = self.client.post(self.url(receipt), self.payload(requestor=''))
        self.assertEqual(response.status_code, 200); self.assertFalse(ChangeVersion.objects.exists())
        response = self.client.post(self.url(receipt), self.payload(case_revision=1))
        self.assertEqual(response.status_code, 200); self.assertFalse(ChangeVersion.objects.exists())
        self.assertContains(response, 'STALE_VERSION')

    def test_manual_pm_capture_does_not_require_agent_success(self):
        receipt = self.receive(body='Please discuss the revised scope; details are incomplete.')
        response = self.client.post(self.url(receipt), self.payload())
        self.assertEqual(response.status_code, 302)
        binding = ChangeIntakeConfirmation.objects.get(receipt=receipt)
        self.assertIsNone(binding.extraction_id); self.assertFalse(AgentRun.objects.exists())
        self.assertFalse(ChangeAuthorization.objects.exists())

    def test_get_head_never_extract_confirm_or_change_revision(self):
        receipt = self.receive(); before = rev(self.case); audits = Audit.objects.count()
        for method in [self.client.get, self.client.head]:
            self.assertEqual(method(self.url(receipt)).status_code, 200)
        self.assertEqual(rev(self.case), before); self.assertEqual(Audit.objects.count(), audits)
        self.assertFalse(AgentRun.objects.exists()); self.assertFalse(ChangeIntakeConfirmation.objects.exists())

    def test_missing_domain_read_hides_private_source_even_with_generic_access(self):
        receipt = self.receive(body=BODY+'\nPRIVATE_P56_SOURCE_SENTINEL'); self.extract(receipt)
        Grant.objects.filter(case=self.case, user=self.actor, action='change.read').update(active=False)
        self.assertEqual(self.client.get(self.url(receipt)).status_code, 404)
        self.assertEqual(self.client.get(reverse('p56_intake', args=[self.case.pk])).status_code, 404)
        generic = self.client.get(reverse('case', args=[self.case.pk]))
        self.assertEqual(generic.status_code, 200); self.assertNotContains(generic, 'PRIVATE_P56_SOURCE_SENTINEL')
        self.assertNotContains(generic, 'synthetic-p56-extraction-v1')
        response = self.client.post(self.url(receipt), self.payload())
        self.assertEqual(response.status_code, 404); self.assertFalse(ChangeIntakeConfirmation.objects.exists())

    def test_cross_case_receipt_is_not_readable_through_other_project(self):
        receipt = self.receive(); _, other = setup_case(username='other-project')
        for action in Grant.objects.filter(case=self.case, user=self.actor).values_list('action', flat=True):
            Grant.objects.create(case=other, user=self.actor, action=action)
        response = self.client.get(reverse('p56_intake_detail', args=[other.pk, receipt.pk]))
        self.assertEqual(response.status_code, 404)

    def test_correct_then_cancel_preserves_both_sources(self):
        receipt = self.receive()
        response = self.client.post(self.url(receipt), {
            'action': 'correct', 'case_revision': rev(self.case), 'key': 'http-corrected',
            'body': BODY+'\nCorrected original request', 'origin': 'synthetic:corrected',
            'correction_reason': 'Requester clarified the wording'})
        successor = Audit.objects.get(action=intake.RECEIVED, data__predecessor=receipt.pk)
        self.assertRedirects(response, self.url(successor), fetch_redirect_response=False)
        response = self.client.post(self.url(successor), {'action': 'cancel', 'case_revision': rev(self.case), 'stop_reason': 'Requester withdrew'})
        self.assertRedirects(response, self.url(successor), fetch_redirect_response=False)
        self.assertEqual(intake.source(receipt).body, BODY)
        self.assertIn('Corrected original request', intake.source(successor).body)
        self.assertFalse(intake.projection(self.actor, successor)['can_confirm'])
        self.assertFalse(ChangeVersion.objects.exists())

    def test_primary_queue_links_pending_receipt_without_body_or_read_side_effect(self):
        receipt = self.receive(body=BODY+'\nPRIVATE_QUEUE_BODY_SENTINEL')
        self.extract(receipt); before = rev(self.case); audits = Audit.objects.count()
        page = self.client.get(reverse('factory_intake'))
        self.assertContains(page, 'Change requests awaiting PM classification')
        self.assertContains(page, 'href="'+self.url(receipt)+'"')
        self.assertNotContains(page, 'PRIVATE_QUEUE_BODY_SENTINEL')
        self.assertNotContains(page, 'Add a reconciliation view')
        self.assertEqual(page['Cache-Control'], 'no-store')
        self.assertEqual(rev(self.case), before); self.assertEqual(Audit.objects.count(), audits)
        Grant.objects.filter(case=self.case, user=self.actor, action='change.read').update(active=False)
        page = self.client.get(reverse('factory_intake'))
        self.assertNotContains(page, 'href="'+self.url(receipt)+'"')

    def test_emergency_confirmation_links_native_controls_without_ordinary_work(self):
        from apps.core.services import add_evidence
        from apps.workflows.models import FactoryWork
        receipt = self.receive()
        incident = add_evidence(self.actor, self.case.pk, 'incident', 'Synthetic outage', 'synthetic:test')
        response = self.client.post(self.url(receipt), self.payload(category='Emergency', incident_id=incident.pk))
        self.assertRedirects(response, self.url(receipt), fetch_redirect_response=False)
        binding = ChangeIntakeConfirmation.objects.get(receipt=receipt)
        self.assertIsNone(binding.work_id); self.assertFalse(FactoryWork.objects.exists())
        page = self.client.get(self.url(receipt))
        self.assertContains(page, 'href="'+reverse('emergencies', args=[self.case.pk])+'"')
        self.assertContains(page, 'has not created or authorized an Emergency implementation')
        self.assertFalse(ChangeAuthorization.objects.exists())

    def test_native_revision_links_existing_work_and_requires_explicit_source_correction(self):
        from apps.workflows.models import FactoryWork
        first = self.confirm(self.receive()); receipt = self.receive('http-native-revision')
        response = self.client.post(self.url(receipt), self.payload(predecessor_version_id=first.version_id,
                                                                  description='PM clarified a native revision'))
        self.assertRedirects(response, self.url(receipt), fetch_redirect_response=False)
        binding = ChangeIntakeConfirmation.objects.get(receipt=receipt)
        self.assertIsNone(binding.work_id); self.assertEqual(FactoryWork.objects.count(), 1)
        self.assertEqual(intake.projection(self.actor, receipt)['followup_work'].pk, first.work_id)
        page = self.client.get(self.url(receipt))
        self.assertContains(page, 'href="'+reverse('factory_detail', args=[first.work_id])+'"')
        self.assertContains(page, 'Correct the sources in the existing controlled change work')
        self.assertFalse(ChangeAuthorization.objects.exists())

    def test_http_receive_preserves_original_whitespace_bytes(self):
        import hashlib
        body = '\n  '+BODY+'  \n\n'; origin = '  synthetic:exact-origin  '
        response = self.client.post(reverse('p56_intake', args=[self.case.pk]), {
            'key': 'exact-http', 'body': body, 'origin': origin, 'case_revision': rev(self.case)})
        self.assertEqual(response.status_code, 302)
        receipt = Audit.objects.get(action=intake.RECEIVED); source = intake.source(receipt)
        self.assertEqual(source.body, body); self.assertEqual(source.source, origin)
        self.assertEqual(source.sha256, hashlib.sha256(body.encode()).hexdigest())

    def test_refresh_receive_preserves_request_updates_revision_and_does_not_submit(self):
        from apps.core.services import add_evidence
        payload = {'key': 'refresh-http', 'body': '\n '+BODY+' \n', 'origin': ' synthetic:origin ',
                   'case_revision': rev(self.case)}
        add_evidence(self.actor, self.case.pk, 'note', 'Concurrent update', 'synthetic:test')
        before = rev(self.case); audits = Audit.objects.count()
        url = reverse('p56_intake', args=[self.case.pk])
        response = self.client.post(url, dict(payload, action='refresh'))
        self.assertEqual(response.status_code, 200); form = response.context['form']
        for name in ['body', 'origin', 'key']: self.assertEqual(form[name].value(), payload[name])
        self.assertEqual(int(form['case_revision'].value()), before)
        self.assertEqual(Audit.objects.count(), audits); self.assertEqual(rev(self.case), before)
        self.assertFalse(Audit.objects.filter(action=intake.RECEIVED).exists())
        payload['case_revision'] = form['case_revision'].value()
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.assertEqual(Audit.objects.filter(action=intake.RECEIVED).count(), 1)

    def test_refresh_confirmation_retains_pm_edits_and_selects_latest_extraction_without_confirming(self):
        receipt = self.receive()
        payload = self.payload(description='PM_EDITED_DESCRIPTION_SENTINEL', note='PM_EDITED_NOTE_SENTINEL',
                               requestor='PM corrected requestor', category_basis='PM independently checked classification')
        run = self.extract(receipt); before = rev(self.case); audits = Audit.objects.count()
        response = self.client.post(self.url(receipt), dict(payload, action='refresh'))
        self.assertEqual(response.status_code, 200); form = response.context['form']
        for name in fields(): self.assertEqual(str(form[name].value()), str(payload[name]))
        self.assertEqual(form['note'].value(), payload['note'])
        self.assertContains(response, 'PM_EDITED_DESCRIPTION_SENTINEL'); self.assertContains(response, 'PM_EDITED_NOTE_SENTINEL')
        self.assertEqual(int(form['case_revision'].value()), before)
        self.assertEqual(int(form['extraction_id'].value()), run.pk)
        self.assertEqual(Audit.objects.count(), audits); self.assertEqual(rev(self.case), before)
        self.assertFalse(ChangeVersion.objects.exists()); self.assertFalse(ChangeIntakeConfirmation.objects.exists())
        payload.update(case_revision=form['case_revision'].value(), extraction_id=form['extraction_id'].value())
        self.assertEqual(self.client.post(self.url(receipt), payload).status_code, 302)
        binding = ChangeIntakeConfirmation.objects.get(receipt=receipt)
        self.assertEqual(binding.extraction_id, run.pk)
        self.assertEqual(binding.version.description, payload['description'])
        self.assertEqual(binding.payload['note'], payload['note'])

    def test_refresh_correction_preserves_source_and_reason_without_replacement(self):
        from apps.core.services import add_evidence
        receipt = self.receive()
        payload = {'action': 'correct', 'case_revision': rev(self.case), 'key': 'refresh-corrected',
                   'body': '\n '+BODY+'\nCorrected source  \n', 'origin': ' synthetic:corrected ',
                   'correction_reason': 'CORRECTION_REASON_RETAINED_SENTINEL'}
        add_evidence(self.actor, self.case.pk, 'note', 'Concurrent update', 'synthetic:test')
        before = rev(self.case); audits = Audit.objects.count()
        response = self.client.post(self.url(receipt), dict(payload, action='refresh_correction'))
        self.assertEqual(response.status_code, 200); form = response.context['correction_form']
        for name in ['body', 'origin', 'key']: self.assertEqual(form[name].value(), payload[name])
        self.assertContains(response, 'CORRECTION_REASON_RETAINED_SENTINEL')
        self.assertEqual(int(form['case_revision'].value()), before)
        self.assertEqual(Audit.objects.count(), audits); self.assertEqual(rev(self.case), before)
        self.assertEqual(Audit.objects.filter(action=intake.RECEIVED).count(), 1)
        payload['case_revision'] = form['case_revision'].value()
        self.assertEqual(self.client.post(self.url(receipt), payload).status_code, 302)
        successor = Audit.objects.get(action=intake.RECEIVED, data__predecessor=receipt.pk)
        self.assertEqual(intake.source(successor).body, payload['body'])
        self.assertEqual(intake.source(successor).source, payload['origin'])
        self.assertEqual(successor.data['reason'], payload['correction_reason'])

    def test_confirmed_fields_and_pm_note_remain_private_to_authorized_change_readers(self):
        receipt = self.receive()
        payload = self.payload(requestor='PRIVATE_REQUESTOR_SENTINEL', description='PRIVATE_DESCRIPTION_SENTINEL',
                               note='PRIVATE_PM_NOTE_SENTINEL')
        self.assertEqual(self.client.post(self.url(receipt), payload).status_code, 302)
        binding = ChangeIntakeConfirmation.objects.get(receipt=receipt)
        Grant.objects.filter(case=self.case, user=self.actor, action='change.read').update(active=False)
        page = self.client.get(reverse('case', args=[self.case.pk]))
        self.assertEqual(page.status_code, 200)
        for sentinel in ['PRIVATE_REQUESTOR_SENTINEL', 'PRIVATE_DESCRIPTION_SENTINEL', 'PRIVATE_PM_NOTE_SENTINEL']:
            self.assertNotContains(page, sentinel)
        self.assertEqual(self.client.get(self.url(receipt)).status_code, 404)
        self.assertEqual(self.client.get(reverse('factory_detail', args=[binding.work_id])).status_code, 404)
        Grant.objects.filter(case=self.case, user=self.actor, action='change.read').update(active=True)
        self.assertContains(self.client.get(self.url(receipt)), 'PRIVATE_REQUESTOR_SENTINEL')
        self.assertEqual(self.client.get(reverse('changes', args=[self.case.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('factory_detail', args=[binding.work_id])).status_code, 200)


class FactoryChangeIntakeCompletionTests(TestCase):
    """Synthetic native PMO completion from P56; not whole-process acceptance."""
    def setUp(self):
        import json
        from pathlib import Path
        from django.utils import timezone
        from apps.policy.operator_drafts import draft_operator_policy
        from apps.policy.services import transition
        from tests import test_commercial_changes as native_tests
        self.actor, self.case, self.e, self.t = native_tests.fixture(existing=True)
        native_tests.change_roles(self.actor, self.case, self.e['policy_decision'])
        self.template = native_tests.ChangeExecutionTests.change_template(self)
        value = json.loads(Path('fixtures/factory-change.json').read_text()); value.pop('classification')
        value.update(preparer_id=self.actor.pk, executor_id=self.actor.pk)
        self.profile = draft_operator_policy(self.actor, self.case.pk, 'OPS.factory_change_execution',
                                             value, self.e['policy_decision'].pk, timezone.now())
        transition(self.actor, self.profile.pk, 'validated'); transition(self.actor, self.profile.pk, 'active')
        self.assertFalse(ChangeVersion.objects.exists())
        self.receipt = intake.receive(self.actor, self.case.pk, 'completion-intake', BODY.replace('CR-P56-1', 'CR-001'),
                                      'synthetic:completion-request', rev(self.case))
        self.run = intake.extract_once(self.actor, self.case.pk, self.receipt.pk, rev(self.case))
        self.binding = intake.confirm(self.actor, self.case.pk, self.receipt.pk, self.run.pk,
                                      fields(reference='CR-001', template_id=self.template.pk),
                                      'PM confirmed the exact intake for native controlled change', rev(self.case))
        self.cv = self.binding.version; self.work = self.binding.work; self.source = self.cv.evidence
        self.inputs = {'template_id': self.template.pk, 'authorization_id': None}
        self.assertEqual(ChangeVersion.objects.count(), 1)
        self.assertEqual(self.source.source, 'psl:p56-confirmed-request/v1')

    def start(self, auth=None, version=None):
        # The complete-flow contract must continue this P56-created work, not
        # accidentally log another version or create another factory intake.
        self.assertIsNone(auth); self.assertIsNone(version)
        self.assertEqual(self.work.pk, self.binding.work_id)
        return self.work

    def assessments(self, *args, **kwargs):
        from tests.test_commercial_changes import ControlledChangeTests
        return ControlledChangeTests.assessments(self, *args, **kwargs)

    def authorized(self):
        from tests.test_commercial_changes import ChangeExecutionTests
        return ChangeExecutionTests.authorized(self)

    def ready(self, auth):
        from tests.test_commercial_changes import ChangeExecutionTests
        return ChangeExecutionTests.ready(self, auth)

    def advance(self):
        from tests.test_factory_change import FactoryChangeTests
        return FactoryChangeTests.advance(self)

    def review(self, purpose):
        from tests.test_factory_change import FactoryChangeTests
        return FactoryChangeTests.review(self, purpose)

    def test_private_confirmed_intake_completes_native_assessments_reviews_receipts_and_signed_closure(self):
        from tests.test_factory_change import FactoryChangeTests
        from apps.core.models import Evidence
        from apps.core.evidence_access import public_evidence
        from apps.pmo.models import ChangeClosure
        from apps.workflows.models import FactoryWork
        FactoryChangeTests.test_complete_native_flow_requires_human_assessment_review_execution_signatures_and_receipts(self)
        self.assertEqual(ChangeIntakeConfirmation.objects.count(), 1)
        self.assertEqual(ChangeVersion.objects.count(), 1); self.assertEqual(FactoryWork.objects.count(), 1)
        closure = ChangeClosure.objects.get()
        self.assertEqual(closure.authorization.version_id, self.binding.version_id)
        self.assertEqual(self.cv.assessments.count(), 4)
        self.assertTrue(all(pk == self.source.pk for pk in self.cv.assessments.values_list('evidence_id', flat=True)))
        self.assertFalse(public_evidence(Evidence.objects.all()).filter(pk=self.source.pk).exists())
        self.assertEqual(intake.source(self.receipt).body, BODY.replace('CR-P56-1', 'CR-001'))
