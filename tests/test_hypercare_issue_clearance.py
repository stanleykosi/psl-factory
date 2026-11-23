import json
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo import delivery_closure
from apps.pmo.hypercare_issues import project_issue_clearance
from apps.pmo.issues import log_issue, update_issue
from apps.pmo.models import DeliveryRecord, Issue, IssueState
from apps.policy.change_drafts import draft_standard_policy
from apps.policy.delivery_validators import HYPERCARE_V2
from apps.policy.models import Configuration, RegisteredReference
from apps.policy.services import active_component, transition
from apps.workflows import factory, factory_hypercare, factory_progress
from apps.workflows.models import FactoryWork
from tests import railway_hypercare_issue_clearance_seed as seed
from tests.helpers import rev
from tests.test_delivery import CRITERIA
from tests.test_factory_hypercare import setup


COMPONENT = 'D11.hypercare_criteria_ref'


class HypercareIssueClearanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sample = setup()
        cls.sample.accepted()
        cls.sample.criteria()
        cls.sample.observations()
        cls.reader = get_user_model().objects.create_user('sample-stability-issue-reader')
        Grant.objects.bulk_create([Grant(case=cls.sample.case, user=cls.reader, action=action)
                                    for action in ('case.read', 'issue.read', 'evidence.add')])

    def value(self):
        return {**CRITERIA, 'issue_clearance': {'scope': 'project_issue_register', 'reader_id': self.reader.pk,
            'blocking_statuses': ['Open', 'In Progress', 'Resolved'], 'blocking_severities': ['High', 'Critical']}}

    def activate(self):
        f = self.sample
        config = draft_standard_policy(f.actor, f.case.pk, COMPONENT, self.value(), f.e['policy_decision'].pk, timezone.now())
        transition(f.actor, config.pk, 'validated')
        transition(f.actor, config.pk, 'active')
        return config

    def log(self, severity='High'):
        f = self.sample
        proof = add_evidence(self.reader, f.case.pk, 'issue_source', 'Exact fictional issue proof.', 'synthetic:hypercare-issue')
        state = log_issue(f.actor, f.case.pk, 'SAMPLE-OPEN-HIGH', 'Cards are failing in sample testing', 'Delivery',
                          f.actor.pk, 'Review the sample fix proof', proof.pk, 'Record fictional issue', rev(f.case), severity)
        return state, proof

    def test_native_hypercare_blocks_on_current_verified_issue_then_qualifies_after_reviewed_change(self):
        self.assertEqual(connection.vendor, 'postgresql')
        f = self.sample
        state, proof = self.log()
        before = delivery_closure.hypercare_inputs(f.d)
        self.assertIs(before['qualified'], True)
        self.assertNotIn('issue_clearance', before)
        self.activate()
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        self.assertEqual(f.work.status, 'waiting')
        blocked = factory_hypercare.assessed(f.work)
        self.assertIs(blocked.snapshot['qualified'], False)
        self.assertEqual(blocked.snapshot['issue_clearance']['status'], 'not_met')
        self.assertNotIn('SAMPLE-OPEN-HIGH', str(blocked.snapshot))

        self.client.force_login(f.actor)
        url = reverse('delivery', args=[f.case.pk])
        issue_url = reverse('issues', args=[f.case.pk]) + f'#issue-{state.issue_id}'
        page = self.client.get(url)
        self.assertContains(page, 'Open SAMPLE-OPEN-HIGH')
        self.assertContains(page, issue_url)
        limited = get_user_model().objects.create_user('sample-stability-delivery-only')
        Grant.objects.bulk_create([Grant(case=f.case, user=limited, action=action)
                                    for action in ('case.read', 'delivery.read')])
        self.client.force_login(limited)
        self.assertContains(self.client.get(url), 'Unknown. The current issue evidence needs review.')
        self.assertNotContains(self.client.get(url), 'SAMPLE-OPEN-HIGH')

        successor = update_issue(f.actor, f.case.pk, state.issue_id, state.pk, 'manage', proof.pk,
                                 'Verified impact is narrower after the fictional fix.', rev(f.case), severity='Medium')
        self.assertNotEqual(successor.pk, state.pk)
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        self.assertEqual(f.work.status, 'verified', f.work.finding)
        qualified = factory_hypercare.assessed(f.work)
        self.assertIs(qualified.snapshot['qualified'], True)
        self.assertEqual(qualified.snapshot['issue_clearance']['status'], 'met')
        self.assertNotEqual(qualified.snapshot['issue_clearance']['source_sha256'], blocked.snapshot['issue_clearance']['source_sha256'])
        self.assertEqual(DeliveryRecord.objects.get(pk=blocked.pk).snapshot, blocked.snapshot)
        Grant.objects.filter(case=f.case, user=self.reader, action='issue.read').update(active=False)
        with self.assertRaisesMessage(ValidationError, 'qualified stability assessment'):
            factory_hypercare.verify(f.work, f.actor)

    def test_unreadable_source_or_original_authority_stays_unknown(self):
        f = self.sample
        self.activate()
        state, proof = self.log()
        self.assertEqual(delivery_closure.hypercare_inputs(f.d)['issue_clearance']['status'], 'not_met')
        self.assertEqual(project_issue_clearance(f.actor, f.d)['blockers'][0]['reference'], state.issue.reference)

        for action in ('issue.read', 'evidence.add'):
            grant = Grant.objects.get(case=f.case, user=self.reader, action=action)
            Grant.objects.filter(pk=grant.pk).update(active=False)
            result = delivery_closure.hypercare_inputs(f.d)
            self.assertIsNone(result['qualified'])
            self.assertEqual(result['issue_clearance']['status'], 'unknown')
            self.assertEqual(project_issue_clearance(f.actor, f.d)['blockers'], [])
            Grant.objects.filter(pk=grant.pk).update(active=True)

        private = f.evidence('approval_source', 'Protected fictional issue details')
        hidden = Issue.objects.create(case=f.case, tenant=f.case.tenant, reference='WITHHELD-ISSUE-REFERENCE')
        hidden.current = IssueState.objects.create(issue=hidden, number=1, title='Private historical issue', kind='Delivery',
            severity='High', status='Open', owner=f.actor, actor=f.actor, evidence=private, next_action='Verify native proof', note='Private test')
        hidden.save(update_fields=['current'])
        alleged = IssueState.objects.create(issue=state.issue, number=2, title='Unverified downgrade', kind='Delivery',
            severity='Low', status='Open', owner=f.actor, actor=f.actor, evidence=proof, next_action='Verify native proof', note='Missing audit')
        Issue.objects.filter(pk=state.issue_id).update(current=alleged)
        result = delivery_closure.hypercare_inputs(f.d)
        self.assertIsNone(result['qualified'])
        self.assertEqual(result['issue_clearance']['status'], 'unknown')
        self.assertEqual(project_issue_clearance(f.actor, f.d)['blockers'], [])
        self.client.force_login(f.actor)
        self.assertNotContains(self.client.get(reverse('delivery', args=[f.case.pk])), hidden.reference)

    def test_native_configuration_draft_chooses_v2_and_typed_review_rejects_invalid_values(self):
        f = self.sample
        self.client.force_login(f.actor)
        url = reverse('delivery', args=[f.case.pk])
        prior = active_component(COMPONENT, f.case)
        self.assertContains(self.client.get(url), 'blocking_severities')
        data = {'action': 'policy', 'revision': rev(f.case), 'component': COMPONENT, 'value': json.dumps(self.value()),
                'evidence': f.e['policy_decision'].pk, 'effective_from': timezone.now().isoformat()}
        self.assertRedirects(self.client.post(url, data), url, fetch_redirect_response=False)
        draft = Configuration.objects.filter(case=f.case, component=COMPONENT).latest('revision')
        ref = RegisteredReference.objects.get(case=f.case, ref=draft.envelope['value'])
        self.assertEqual(ref.schema_ref, HYPERCARE_V2)
        self.assertEqual(active_component(COMPONENT, f.case).pk, prior.pk)
        transition(f.actor, draft.pk, 'validated')
        transition(f.actor, draft.pk, 'active')
        self.assertEqual(delivery_closure.hypercare_inputs(f.d)['issue_clearance']['status'], 'met')

        for changes in ({'blocking_severities': []}, {'blocking_statuses': ['Closed']}, {'reader_id': False},
                        {'scope': 'all_projects'}, {'blocking_severities': ['High', 'High']}):
            value = self.value()
            value['issue_clearance'].update(changes)
            invalid = draft_standard_policy(f.actor, f.case.pk, COMPONENT, value, f.e['policy_decision'].pk, timezone.now())
            with self.assertRaises(ValidationError):
                transition(f.actor, invalid.pk, 'validated')


class HypercareIssueClearanceWalkthroughSeedTests(TestCase):
    def test_separate_original_source_and_scoped_browser_correction(self):
        self.assertEqual(connection.vendor, 'postgresql')
        operator = get_user_model().objects.create_user('psl-agent-trial')
        environment = {'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                       'PGDATABASE': 'synthetic-preview', seed.GUARD: '1'}
        with patch.dict('os.environ', environment | {seed.GUARD: '0'}):
            with self.assertRaisesMessage(RuntimeError, 'Hypercare issue specimen guard'):
                seed.run()
        output = StringIO()
        with patch.dict('os.environ', environment), redirect_stdout(output):
            seed.run()
        prefix, value = output.getvalue().strip().split('=', 1)
        self.assertEqual(prefix, seed.GUARD)
        sample = json.loads(value)
        self.assertNotEqual(sample['source_holder'], operator.pk)
        source = IssueState.objects.get(pk=sample['state'], issue_id=sample['issue'])
        self.assertEqual((source.evidence_id, source.evidence.created_by_id), (sample['original_proof'], sample['source_holder']))
        work = FactoryWork.objects.get(pk=sample['work'])
        limited = get_user_model().objects.create_user('sample-issue-clearance-withheld-reader')
        Grant.objects.bulk_create([Grant(case=work.case, user=limited, action=action)
                                    for action in ('case.read', 'factory.read', 'delivery.read')])
        self.client.force_login(limited)
        withheld = self.client.get(sample['path'])
        self.assertContains(withheld, 'Unknown. The current issue evidence needs review.')
        self.assertNotContains(withheld, sample['reference'])

        self.client.force_login(operator)
        held = self.client.get(sample['path'])
        self.assertContains(held, f"Open {sample['reference']}")
        self.assertContains(held, sample['issue_path'])
        issue_url = reverse('issues', args=[work.case_id])
        self.assertRedirects(self.client.post(issue_url, {'action': 'work', 'revision': rev(work.case), 'operation': 'manage',
            'issue': sample['issue'], 'state': sample['state'], 'evidence': sample['changed_impact_proof'],
            'severity': sample['changed_severity'], 'note': sample['note']}), issue_url, fetch_redirect_response=False)
        current = Issue.objects.get(pk=sample['issue']).current
        self.assertEqual((current.severity, current.evidence_id), ('Medium', sample['changed_impact_proof']))
        self.assertRedirects(self.client.post(sample['path'], {'action': 'advance', 'revision': work.revision}),
                             sample['path'], fetch_redirect_response=False)
        for _ in range(8):
            factory_progress.run_once()
            work.refresh_from_db()
            if work.status == 'verified':
                break
        self.assertEqual(work.status, 'verified', work.finding)
        self.assertContains(self.client.get(sample['path']), 'Current project issues meet the reviewed stability rule.')
        self.assertEqual(seed.prepare(operator), sample | {'preserved': True})
        self.assertIs(DeliveryRecord.objects.get(pk=sample['assessment']).snapshot['qualified'], False)
