from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.finance import hrfinance
from apps.identity.models import Grant
from apps.policy.hrfinance_drafts import draft_disclosure_fields, review_disclosure_fields
from apps.policy.hrfinance_validators import DISCLOSURE, REQUIRED
from apps.policy.models import Configuration, RegisteredReference
from apps.policy.services import active_component, reference_values, transition
from tests.helpers import rev
from tests.hrfinance_helpers import capture, fixture, policy


class DisclosureSetupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f = fixture()

    def values(self, fields=None):
        f = self.f
        return {'fields': fields or REQUIRED, 'base_id': f['disclosure_policy'].pk,
                'latest_revision': f['disclosure_policy'].revision, 'revision': rev(f['case']),
                'evidence': f['e']['owner'].pk, 'effective_from': timezone.now().isoformat(),
                'reason': 'SAMPLE job role needed for the approved handoff.'}

    def test_roles_show_current_named_principals_with_one_batched_name_read(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        f = self.f
        self.client.force_login(f['hr'])
        with CaptureQueriesContext(connection) as queries:
            page = self.client.get(reverse('workspace_settings', args=[f['case'].pk]))
        self.assertContains(page, 'Current assignments')
        self.assertContains(page, 'Human resources')
        self.assertContains(page, f['finance'].username)
        self.assertEqual(len(page.context['role_rows']), 2)
        names = [row['sql'] for row in queries if '"auth_user"."first_name"' in row['sql'] and ' IN (' in row['sql']]
        self.assertEqual(len(names), 1)
        Grant.objects.filter(case=f['case'], user=f['hr'], action='policy.read').update(active=False)
        self.assertEqual(self.client.get(reverse('workspace_settings', args=[f['case'].pk])).status_code, 403)

    def test_api_field_visibility_discussion_through_live_native_revision(self):
        f = self.f
        self.client.force_login(f['hr'])
        path = f'/api/v1/setup/{f["case"].pk}/hr-field-visibility'
        choices = self.client.get(path)
        self.assertEqual(choices.status_code, 200, choices.content)
        self.assertTrue(choices.json()['can_propose'])
        args = {'case_revision': rev(f['case']), 'base_id': choices.json()['base_id'],
                'latest_version': choices.json()['latest_version'], 'fields': REQUIRED + ['role'],
                'evidence_id': f['e']['owner'].pk, 'effective_from': timezone.now().isoformat(), 'reason': 'SAMPLE field review'}
        draft = self.client.post(path, args, content_type='application/json')
        self.assertEqual(draft.status_code, 201, draft.content)
        current_id = draft.json()['id']
        review = f'{path}/{current_id}'
        before = self.client.get(review)
        self.assertEqual(before.status_code, 200, before.content)
        self.assertEqual(before.json()['proposed'], REQUIRED + ['role'])
        self.assertEqual(active_component(DISCLOSURE, f['case']).pk, f['disclosure_policy'].pk)
        for state, action in (('draft', 'validate'), ('validated', 'activate')):
            decision = self.client.post(review, {'case_revision': rev(f['case']), 'state': state, 'action': action},
                                        content_type='application/json')
            self.assertEqual(decision.status_code, 200, decision.content)
        self.assertEqual(active_component(DISCLOSURE, f['case']).pk, current_id)

    def test_proposal_preserves_terms_and_requires_native_review_before_use(self):
        f = self.f
        snapshot = capture(f)
        before = reference_values(f['disclosure_policy'])[0]
        self.client.force_login(f['hr'])
        url = reverse('workspace_settings', args=[f['case'].pk]) + '?area=payroll'
        page = self.client.get(url)
        self.assertContains(page, 'Staff reference')
        self.assertContains(page, 'Propose field visibility')
        self.assertNotContains(page, 'private-staff-001')
        response = self.client.post(url, self.values(REQUIRED + ['role']), follow=True)
        self.assertContains(response, 'Visibility draft 2 saved')
        self.assertContains(response, 'Proposed version 2')
        from apps.core.models import Audit
        self.assertEqual(Audit.objects.get(action='policy.disclosure_fields_proposed').data['reason'],
                         'SAMPLE job role needed for the approved handoff.')
        draft = Configuration.objects.filter(case=f['case'], component=DISCLOSURE).latest('revision')
        proposed = reference_values(draft)[0]
        self.assertEqual(proposed.pop('allowed_fields'), REQUIRED + ['role'])
        self.assertEqual(proposed, {key: value for key, value in before.items() if key != 'allowed_fields'})
        self.assertEqual(active_component(DISCLOSURE, f['case']).pk, f['disclosure_policy'].pk)
        self.assertTrue(hrfinance.read_snapshot(f['finance'], snapshot)['rows'])
        transition(f['hr'], draft.pk, 'validated')
        transition(f['hr'], draft.pk, 'active')
        with self.assertRaises(ValidationError):
            hrfinance.read_snapshot(f['finance'], snapshot)
        new = hrfinance.contract(f['finance'], f['case'].pk, f['need'].pk, 'new-fields-contract',
                                f['e']['hr_contract_source'].pk, rev(f['case']))
        self.assertEqual(new.payload['fields'], REQUIRED)
        with self.assertRaises(ValidationError):
            hrfinance.authorized(new)

    def test_focused_review_compares_reason_terms_and_uses_native_lifecycle(self):
        f = self.f
        draft = draft_disclosure_fields(f['hr'], f['case'].pk, f['disclosure_policy'].pk, 1,
            REQUIRED + ['role'], f['e']['owner'].pk, timezone.now(), rev(f['case']), reason='SAMPLE field review')
        self.client.force_login(f['hr'])
        url = reverse('visibility_review', args=[f['case'].pk, draft.pk])
        page = self.client.get(url)
        self.assertContains(page, 'Earlier version 1')
        self.assertContains(page, 'Proposed version 2')
        self.assertContains(page, 'SAMPLE field review')
        self.assertContains(page, f['finance'].username)
        self.assertNotContains(page, 'private-staff-001')
        self.assertNotContains(page, 'Activate reviewed version')
        values = {'action': 'validate', 'state': 'draft', 'revision': rev(f['case'])}
        self.assertContains(self.client.post(url, values, follow=True), 'Activate reviewed version')
        self.assertEqual(active_component(DISCLOSURE, f['case']).pk, f['disclosure_policy'].pk)
        self.assertContains(self.client.post(url, values, follow=True), 'The review could not proceed')
        values.update(action='activate', state='validated', revision=rev(f['case']))
        self.assertContains(self.client.post(url, values, follow=True), 'This version is active')
        self.assertEqual(active_component(DISCLOSURE, f['case']).pk, draft.pk)

    def test_focused_review_rechecks_permission_csrf_and_replaced_proposal(self):
        f = self.f
        draft = draft_disclosure_fields(f['hr'], f['case'].pk, f['disclosure_policy'].pk, 1,
            REQUIRED + ['role'], f['e']['owner'].pk, timezone.now(), rev(f['case']), reason='SAMPLE first version')
        self.client.force_login(f['hr'])
        url = reverse('visibility_review', args=[f['case'].pk, draft.pk])
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(f['hr'])
        values = {'action': 'validate', 'state': 'draft', 'revision': rev(f['case'])}
        self.assertEqual(secure.post(url, values).status_code, 403)
        Grant.objects.filter(case=f['case'], user=f['hr'], action='policy.configure').update(active=False)
        self.assertNotContains(self.client.get(url), 'Check proposed version')
        self.assertEqual(self.client.post(url, values).status_code, 403)
        Grant.objects.filter(case=f['case'], user=f['hr'], action='policy.configure').update(active=True)
        draft_disclosure_fields(f['hr'], f['case'].pk, f['disclosure_policy'].pk, draft.revision,
            REQUIRED, f['e']['owner'].pk, timezone.now(), rev(f['case']), reason='SAMPLE replacement')
        self.assertContains(self.client.get(url), 'A newer rule or proposal requires review')
        with self.assertRaises(ValidationError):
            review_disclosure_fields(f['hr'], f['case'].pk, draft.pk, 'draft', 'validate', rev(f['case']))

    def test_service_commands_reject_missing_and_boolean_revisions(self):
        f = self.f
        for expected in [None, True, 0, -1]:
            with self.assertRaises(ValidationError):
                draft_disclosure_fields(f['hr'], f['case'].pk, f['disclosure_policy'].pk, 1,
                    REQUIRED, f['e']['owner'].pk, timezone.now(), expected, reason='SAMPLE typed check')
            with self.assertRaises(ValidationError):
                review_disclosure_fields(f['hr'], f['case'].pk, f['disclosure_policy'].pk,
                    'draft', 'validate', expected)

    def test_invalid_fields_roll_back_every_draft_and_reference(self):
        f = self.f
        self.client.force_login(f['hr'])
        url = reverse('workspace_settings', args=[f['case'].pk]) + '?area=payroll'
        before = (Configuration.objects.count(), RegisteredReference.objects.count(), rev(f['case']))
        for fields in [REQUIRED[1:], REQUIRED + ['monthly_pay'], REQUIRED + ['currency'], REQUIRED + ['private_salary_notes']]:
            response = self.client.post(url, self.values(fields))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, '<details open>')
            self.assertEqual(before, (Configuration.objects.count(), RegisteredReference.objects.count(), rev(f['case'])))

    def test_current_permissions_stale_rules_and_forged_terms_are_rechecked(self):
        f = self.f
        self.client.force_login(f['hr'])
        url = reverse('workspace_settings', args=[f['case'].pk]) + '?area=payroll'
        stale = self.values()
        newer = dict(f['config']['disclosure'], allowed_fields=REQUIRED + ['role'])
        policy(f['hr'], f['case'], DISCLOSURE, newer, f['e']['owner'])
        before = Configuration.objects.count()
        self.assertContains(self.client.post(url, stale), 'Refresh if the source or rule has changed')
        self.assertEqual(Configuration.objects.count(), before)
        forged = self.values()
        forged['recipient_ids'] = [f['hr'].pk]
        self.assertContains(self.client.post(url, forged), 'Use the displayed fields')
        Grant.objects.filter(case=f['case'], user=f['hr'], action='policy.configure').update(active=False)
        self.assertNotContains(self.client.get(url), 'Save visibility draft')
        self.assertEqual(self.client.post(url, stale).status_code, 403)
        Grant.objects.filter(case=f['case'], user=f['hr'], action='policy.read').update(active=False)
        self.assertEqual(self.client.get(url).status_code, 403)
        with self.assertRaises(PermissionDenied):
            draft_disclosure_fields(f['hr'], f['case'].pk, f['disclosure_policy'].pk, 1,
                                    REQUIRED, f['e']['owner'].pk, timezone.now(), rev(f['case']), reason='SAMPLE')

    def test_csrf_and_foreign_base_do_not_create_a_proposal(self):
        f = self.f
        client = Client(enforce_csrf_checks=True)
        client.force_login(f['hr'])
        url = reverse('workspace_settings', args=[f['case'].pk]) + '?area=payroll'
        self.assertEqual(client.post(url, self.values()).status_code, 403)
        self.client.force_login(f['hr'])
        values = self.values()
        values['base_id'] = f['authority_policy'].pk
        before = Configuration.objects.count()
        self.assertEqual(self.client.post(url, values).status_code, 200)
        self.assertEqual(Configuration.objects.count(), before)

    def test_shared_disclosure_rechecks_the_viewers_original_source_access(self):
        from django.contrib.auth import get_user_model
        from apps.core.models import Case
        from apps.core.services import add_evidence
        from apps.policy import scopes
        from apps.policy.hrfinance_drafts import draft_hrfinance_policy

        f = self.f
        source = draft_hrfinance_policy(f['hr'], f['case'].pk, DISCLOSURE,
            f['config']['disclosure'], f['e']['owner'].pk, timezone.now())
        transition(f['hr'], source.pk, 'validated')
        shared = scopes.create(f['hr'], source.pk, 'organization', f['case'].tenant,
                               ['/0/source_evidence_id'])
        scopes.transition(f['hr'], shared.pk, 'validated')
        scopes.transition(f['hr'], shared.pk, 'active')
        target = Case.objects.create(tenant=f['case'].tenant, title='Shared disclosure test',
                                     kind='project', synthetic=True)
        actions = Grant.objects.filter(case=f['case'], user=f['hr'], active=True).values_list('action', flat=True)
        Grant.objects.bulk_create([Grant(case=target, user=f['hr'], action=action) for action in actions])
        proof = add_evidence(f['hr'], target.pk, 'policy_decision', 'SAMPLE local rule decision', 'synthetic:setup')
        contract = add_evidence(f['hr'], target.pk, 'hr_contract_source', 'SAMPLE local HR contract', 'synthetic:setup')
        applied = scopes.apply(f['hr'], shared.pk, target.pk, proof.pk,
                               [{'path': '/0/source_evidence_id', 'value': contract.pk}])
        transition(f['hr'], applied.pk, 'validated')
        transition(f['hr'], applied.pk, 'active')
        viewer = get_user_model().objects.create_user('shared-disclosure-viewer')
        for case in [f['case'], target]:
            for action in ['case.read', 'policy.read', 'policy.configure']:
                Grant.objects.create(case=case, user=viewer, action=action)
        self.client.force_login(viewer)
        url = reverse('workspace_settings', args=[target.pk]) + '?area=payroll'
        self.assertContains(self.client.get(url), 'synthetic-finance-view')
        shared_draft = draft_disclosure_fields(viewer, target.pk, applied.pk, applied.revision,
            REQUIRED + ['role'], proof.pk, timezone.now(), rev(target), reason='SAMPLE shared-field proposal')
        review_url = reverse('visibility_review', args=[target.pk, shared_draft.pk])
        self.assertContains(self.client.get(review_url), 'SAMPLE shared-field proposal')
        for denied in ['policy.read', 'case.read']:
            Grant.objects.filter(case=f['case'], user=viewer, action=denied).update(active=False)
            self.assertEqual(active_component(DISCLOSURE, target).pk, applied.pk)
            page = self.client.get(url)
            self.assertContains(page, 'Current disclosure requires access to its original rules')
            self.assertNotContains(page, 'synthetic-finance-view')
            self.assertNotContains(page, 'Save visibility draft')
            self.assertEqual(self.client.get(review_url).status_code, 403)
            with self.assertRaises(PermissionDenied):
                draft_disclosure_fields(viewer, target.pk, applied.pk, applied.revision, REQUIRED,
                    proof.pk, timezone.now(), rev(target), reason='SAMPLE inaccessible source')
            Grant.objects.filter(case=f['case'], user=viewer, action=denied).update(active=True)


class DisclosureSetupConcurrencyTests(TransactionTestCase):
    def test_competing_reviews_record_one_native_validation(self):
        f = fixture()
        draft = draft_disclosure_fields(f['hr'], f['case'].pk, f['disclosure_policy'].pk, 1,
            REQUIRED + ['role'], f['e']['owner'].pk, timezone.now(), rev(f['case']), reason='SAMPLE competing review')
        expected = rev(f['case'])
        barrier = Barrier(2)

        def validate(_):
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                try:
                    return review_disclosure_fields(f['hr'], f['case'].pk, draft.pk,
                                                    'draft', 'validate', expected).pk
                except ValidationError:
                    return None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(validate, range(2)))
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(draft.states.filter(state='validated').count(), 1)
        self.assertEqual(active_component(DISCLOSURE, f['case']).pk, f['disclosure_policy'].pk)

    def test_competing_field_proposals_preserve_one_current_base(self):
        f = fixture()
        barrier = Barrier(2)
        expected = rev(f['case'])

        def propose(_):
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                try:
                    return draft_disclosure_fields(f['hr'], f['case'].pk, f['disclosure_policy'].pk, 1,
                        REQUIRED + ['role'], f['e']['owner'].pk, timezone.now(), expected, reason='SAMPLE').pk
                except ValidationError:
                    return None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(propose, range(2)))
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(Configuration.objects.filter(case=f['case'], component=DISCLOSURE).count(), 2)
        self.assertEqual(active_component(DISCLOSURE, f['case']).pk, f['disclosure_policy'].pk)
