from django.test import TestCase
from django.urls import reverse

from apps.identity.models import Grant
from tests.helpers import setup_case


class SetupOverviewTests(TestCase):
    def test_setup_filters_current_workspace_permissions_before_pagination(self):
        from apps.core.models import Case

        actor, case = setup_case()
        self.client.force_login(actor)
        others = Case.objects.bulk_create([
            Case(title=f'Setup sample {number:02}', tenant=case.tenant, kind='project', synthetic=True)
            for number in range(26)
        ])
        Grant.objects.bulk_create([Grant(case=row, user=actor, action='case.read') for row in others])
        url = reverse('design_setup')
        page = self.client.get(url)
        self.assertEqual(page.context['workspaces'].paginator.count, 1)
        self.assertContains(page, reverse('workspace_settings', args=[case.pk]))
        self.assertNotContains(page, 'Staff accounts')
        Grant.objects.bulk_create([Grant(case=row, user=actor, action='policy.read') for row in others[:25]])
        page = self.client.get(url)
        self.assertEqual(page.context['workspaces'].paginator.count, 26)
        self.assertTrue(page.context['workspaces'].has_next())
        second = self.client.get(url, {'page': 2})
        self.assertEqual(len(second.context['workspaces']), 1)
        self.assertNotContains(self.client.get(url, {'q': 'missing sample'}), str(case.pk))
        Grant.objects.filter(case=case, user=actor, action='policy.read').update(active=False)
        self.assertNotContains(self.client.get(url), reverse('workspace_settings', args=[case.pk]))

    def test_manage_only_authority_is_independent_of_case_creation_and_is_current(self):
        from datetime import timedelta
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from apps.identity import intake

        actor, case = setup_case()
        Grant.objects.filter(case=case, user=actor, action='policy.read').update(active=False)
        root = get_user_model().objects.create_superuser('setup-test-root', password='test-only-password')
        value = {'format': 'psl.tenant-access/v1', 'create_cases': False, 'manage_access': True,
                 'kinds': ['project'], 'allowed_actions': ['case.read'], 'initial_actions': [],
                 'classification': 'synthetic'}
        expiry = timezone.now() + timedelta(hours=1)
        intake.provision(root, actor, case.tenant, value, expiry, True, 'Sample account manager')
        self.assertEqual(intake.options(actor), [])
        self.assertEqual(len(intake.options(actor, 'manage_access')), 1)
        self.client.force_login(actor)
        page = self.client.get(reverse('design_setup'))
        self.assertContains(page, reverse('case_access', args=[case.pk]))
        self.assertNotContains(page, reverse('workspace_settings', args=[case.pk]))
        intake.provision(root, actor, case.tenant, value, expiry, False, 'Withdraw sample account manager')
        self.assertEqual(self.client.get(reverse('design_setup')).context['workspaces'].paginator.count, 0)

    def test_setup_is_safe_read_only_and_normal_navigation_exposes_it(self):
        from apps.core.models import Audit, Case

        actor, case = setup_case()
        self.client.force_login(actor)
        before = (Audit.objects.count(), Case.objects.count(), Grant.objects.count())
        self.assertContains(self.client.get(reverse('case', args=[case.pk])), reverse('design_setup'))
        self.assertEqual(self.client.post(reverse('design_setup'), {}).status_code, 405)
        self.assertEqual(self.client.get(reverse('design_setup')).status_code, 200)
        self.assertEqual(before, (Audit.objects.count(), Case.objects.count(), Grant.objects.count()))

    def test_read_only_rules_and_deferred_payroll_fields(self):
        actor, case = setup_case()
        self.client.force_login(actor)
        url = reverse('workspace_settings',args=[case.pk])
        finance = self.client.get(url, {'area': 'finance'})
        self.assertContains(finance, 'Stage billing terms')
        self.assertContains(finance, 'Invoice responsibilities')
        self.assertNotContains(finance, 'Go-live milestone handoff')
        delivery = self.client.get(url, {'area': 'delivery'})
        self.assertContains(delivery, 'Hypercare window')
        self.assertContains(delivery, 'What hypercare must meet')
        self.assertContains(delivery, 'Go-live milestone handoff')
        self.assertNotContains(delivery, 'Invoice responsibilities')
        self.assertContains(self.client.get(url,{'area':'payroll'}),'Choose the HR source, recipients, purpose and retention terms')
        Grant.objects.filter(case=case,user=actor,action='policy.configure').update(active=False)
        page = self.client.get(url)
        self.assertContains(page,'View access only.')
        self.assertNotContains(page,'Review rule versions and configuration')

    def test_finance_setup_resolves_the_registered_groups_and_current_profile_fields(self):
        import json
        from pathlib import Path

        from django.db import connection
        from django.utils import timezone

        from apps.core.models import Audit
        from apps.core.setup_finance import ACCOUNTING_PROFILE, FINANCE_RULE_GROUPS
        from apps.policy.models import Configuration, PolicyState
        from apps.policy.operator_drafts import draft_operator_policy
        from apps.policy.registry import components
        from apps.policy.services import transition
        from tests.finance_analysis_helpers import fixture

        self.assertEqual(connection.vendor, 'postgresql')
        actor, case, evidence, _, _, _, template, _ = fixture(username='finance-setup-owner')
        proof = evidence['policy_decision']
        declared = {key for _, _, _, rules in FINANCE_RULE_GROUPS for rule in rules for key in rule.components}
        self.assertLessEqual(declared, components().keys())
        values = json.loads(Path('fixtures/factory-accounting.json').read_text())
        values.pop('classification')
        values.update(information_resolver_id=None, executor_id=None, template_id=None, audience=None,
                      bu_metrics=None, allocation_mode='company_and_bu')
        profile = draft_operator_policy(actor, case.pk, ACCOUNTING_PROFILE, values, proof.pk, timezone.now())
        transition(actor, profile.pk, 'validated')
        transition(actor, profile.pk, 'active')

        self.client.force_login(actor)
        url = reverse('workspace_settings', args=[case.pk]) + '?area=finance'
        before = (Audit.objects.count(), Configuration.objects.count(), PolicyState.objects.count())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        groups = {group['label']: group for group in response.context['finance_groups']}
        self.assertEqual([len(group['rules']) for group in groups.values()], [4, 3, 3, 3, 4, 3, 5])
        accounts = {row['label']: row['status'] for row in groups['Management accounts']['rules']}
        self.assertEqual(accounts, {'Statement contract': 'MISSING', 'Business-unit metrics': 'MISSING',
            'Report template and audience': 'MISSING', 'Finance executor who publishes': 'UNASSIGNED'})
        forecast = {row['label']: row['status'] for row in groups['Cash forecast']['rules']}
        self.assertEqual(forecast['Group reviewer'], 'UNASSIGNED')
        self.assertContains(response, 'Stage billing terms')
        self.assertContains(response, 'Invoice responsibilities')
        self.assertContains(response, reverse('finance_schedules', args=[case.pk]))
        self.assertContains(response, reverse('factory_configuration', args=[case.pk]) + '?definition=finance-accounts/v1')
        self.assertEqual(self.client.post(url, {'action': 'active'}).status_code, 405)
        self.assertEqual(before, (Audit.objects.count(), Configuration.objects.count(), PolicyState.objects.count()))

        successor = draft_operator_policy(actor, case.pk, ACCOUNTING_PROFILE, dict(values, executor_id=actor.pk,
            template_id=template.pk, audience='internal', allocation_mode='company_only'), proof.pk, timezone.now())
        transition(actor, successor.pk, 'validated')
        pending = {row['label']: row for row in self.client.get(url).context['finance_groups'][0]['rules']}
        self.assertEqual(pending['Finance executor who publishes']['status'], 'UNASSIGNED')
        transition(actor, successor.pk, 'active')
        current = {row['label']: row for row in self.client.get(url).context['finance_groups'][0]['rules']}
        self.assertEqual(current['Business-unit metrics']['value'], 'Company totals only')
        self.assertEqual(current['Finance executor who publishes']['revisions'], [successor.revision])
        self.assertEqual(current['Report template and audience']['revisions'], [successor.revision])
        self.assertEqual(current['Statement contract']['status'], 'MISSING')

    def test_finance_setup_payroll_summary_requires_current_private_payroll_access(self):
        import json
        from pathlib import Path
        from unittest.mock import patch

        from django.contrib.auth import get_user_model
        from django.db import connection
        from django.utils import timezone

        from apps.core import setup_finance
        from apps.core.services import add_evidence
        from apps.policy.payroll_drafts import draft_payroll_policy
        from apps.policy.payroll_validators import MERGE
        from apps.policy.services import transition

        self.assertEqual(connection.vendor, 'postgresql')
        actor, case = setup_case()
        proof = add_evidence(actor, case.pk, 'policy_decision', 'Synthetic restricted merge review', 'synthetic:setup-test')
        values = json.loads(Path('fixtures/payroll.json').read_text())['merge']
        version = draft_payroll_policy(actor, case.pk, MERGE, values, proof.pk, timezone.now())
        transition(actor, version.pk, 'validated')
        transition(actor, version.pk, 'active')
        reader = get_user_model().objects.create_user('finance-aggregate-payroll-reader')
        Grant.objects.bulk_create([Grant(user=reader, case=case, action=action)
            for action in ('case.read', 'policy.read', 'finance.read', 'payroll.read', 'payroll.report.read')])
        self.client.force_login(reader)
        url = reverse('workspace_settings', args=[case.pk]) + '?area=finance'
        payroll = reverse('payroll', args=[case.pk])
        with patch.object(setup_finance, 'resolve', wraps=setup_finance.resolve) as resolve:
            restricted = self.client.get(url)
        self.assertContains(restricted, 'Management accounts')
        self.assertContains(restricted, 'Access required to view these settings.')
        self.assertNotContains(restricted, 'Merge rules')
        self.assertNotContains(restricted, payroll)
        self.assertNotIn(MERGE, [call.args[0] for call in resolve.call_args_list])
        private = Grant.objects.create(user=reader, case=case, action='payroll.private.read')
        permitted = self.client.get(url)
        self.assertContains(permitted, payroll)
        self.assertNotContains(permitted, reverse('payroll_row_controls', args=[case.pk]))
        rows = {row['label']: row for row in permitted.context['finance_groups'][-1]['rules']}
        self.assertEqual(rows['Merge rules']['revisions'], [version.revision])
        self.assertEqual(rows['Who reviews payroll']['status'], 'UNASSIGNED')
        self.assertNotContains(permitted, values['method'])
        private.active = False
        private.save(update_fields=['active'])
        self.assertNotContains(self.client.get(url), 'Merge rules')
        self.client.force_login(actor)
        self.assertContains(self.client.get(url), reverse('payroll_row_controls', args=[case.pk]))

    def test_delivery_rows_follow_effective_criteria_templates_store_and_current_confirmation_grant(self):
        from django.contrib.auth import get_user_model
        from django.db import connection
        from django.utils import timezone

        from apps.core.services import add_evidence
        from apps.documents.controlled import register_template
        from apps.policy.change_drafts import draft_standard_policy
        from apps.policy.operator_drafts import draft_operator_policy
        from apps.policy.services import transition
        from tests.document_helpers import artifact
        from tests.helpers import rev

        self.assertEqual(connection.vendor, 'postgresql')
        actor, case = setup_case()
        reader = get_user_model().objects.create_user('read-only-delivery-setup')
        completer = get_user_model().objects.create_user('scoped-finance-notification-recorder')
        Grant.objects.bulk_create([Grant(case=case, user=reader, action=action) for action in ('case.read', 'policy.read')])
        Grant.objects.filter(case=case, user=actor, action='delivery.finance_confirm').update(active=False)
        self.client.force_login(reader)
        url = reverse('workspace_settings', args=[case.pk]) + '?area=delivery'
        labels = (
            'Hypercare window', 'What hypercare must meet', 'Who confirms Finance before closure',
            'When a handover needs review', 'Archive storage rule',
        )

        def rows(page):
            return {item['label']: item for item in page.context['items']}

        empty = self.client.get(url)
        self.assertContains(empty, 'Used by')
        self.assertContains(empty, 'View access only.')
        self.assertNotContains(empty, 'Review rule versions and configuration')
        for label in labels:
            self.assertContains(empty, label)
            self.assertEqual(rows(empty)[label]['status'], 'MISSING')
        self.assertNotContains(empty, 'Keep, never purge')
        self.assertEqual(self.client.post(url, {}).status_code, 405)

        proof = add_evidence(actor, case.pk, 'policy_decision', 'Reviewed synthetic delivery settings', 'synthetic:setup')
        criteria = draft_standard_policy(actor, case.pk, 'D11.hypercare_criteria_ref', {
            'clock': 'elapsed_hours_since_release', 'minimum_hours': 36,
            'confirmation_owners': ['Engineering', 'Infrastructure'],
            'metrics': [{'key': 'availability', 'unit': 'percent', 'owner': 'Infrastructure',
                         'operator': 'gte', 'threshold': 99.5}],
            'financial_controls': 'independent',
        }, proof.pk, timezone.now())
        self.assertNotContains(self.client.get(url), '36 hours after the recorded release')
        for state in ('validated', 'active'):
            transition(actor, criteria.pk, state)
        Grant.objects.bulk_create([Grant(case=case, user=completer, action=action)
                                   for action in ('case.read', 'delivery.read', 'delivery.finance_confirm')])
        common = {
            'document_type': 'project_artifact', 'required_fields': ['executive_summary', 'status'],
            'audience_fields': {'internal': ['executive_summary', 'status', 'scope', 'next_steps']},
        }
        required = register_template(actor, case.pk, 'Reviewed handover', common | {'internal_review_required': True}, proof.pk, rev(case))
        optional = register_template(actor, case.pk, 'Other handover template', common | {'internal_review_required': False}, proof.pk, rev(case))
        incompatible = register_template(actor, case.pk, 'Template without handover sections', common | {
            'required_fields': ['executive_summary', 'status', 'risks'],
            'audience_fields': {'internal': ['executive_summary', 'status', 'scope', 'next_steps', 'risks']},
            'internal_review_required': False,
        }, proof.pk, rev(case))
        storage = {'template_ids': [required.pk, incompatible.pk], 'repository': 'internal-versioned', 'retention_days': 30}
        artifact(actor, case, 'D11.template_storage_retention_rules', 'schema:psl/document-storage/v1', storage, proof)
        active = self.client.get(url)
        self.assertContains(active, '36 hours after the recorded release')
        self.assertContains(active, 'Infrastructure availability at least 99.5 percent')
        self.assertContains(active, 'Authorised Finance recorder')
        self.assertNotContains(active, completer.username)
        self.assertContains(active, 'Review required before publication')
        self.assertEqual(rows(active)['Archive storage rule']['status'], 'MISSING')

        artifact(actor, case, 'D11.template_storage_retention_rules', 'schema:psl/document-storage/v2', storage | {
            'template_ids': [required.pk, optional.pk],
            'closure_inventory': {'required_kinds': ['technical_document', 'test_results', 'project_artifact'],
                                  'archive_mode': 'immutable_local_manifest'},
        }, proof)
        revised = self.client.get(url)
        self.assertContains(revised, 'Review depends on the selected template')
        self.assertContains(revised, 'Immutable project archive inventory')
        transfer = draft_operator_policy(actor, case.pk, 'OPS.archive_file_transfer', {
            'adapter': 'synthetic_archive/v1', 'operator_id': actor.pk, 'max_files': 5, 'max_bytes': 5000, 'lease_seconds': 30,
        }, proof.pk, timezone.now())
        for state in ('validated', 'active'):
            transition(actor, transfer.pk, state)
        self.assertContains(self.client.get(url), 'Sample archive store')

        transition(actor, criteria.pk, 'revoked')
        Grant.objects.filter(case=case, user=completer, action='delivery.finance_confirm').update(active=False)
        stale = self.client.get(url)
        self.assertEqual(rows(stale)['Who confirms Finance before closure']['status'], 'MISSING')
        self.assertEqual(rows(stale)['Hypercare window']['status'], 'REVOKED')
        self.assertNotContains(stale, '36 hours after the recorded release')
        Grant.objects.filter(case=case, user=reader, action='policy.read').update(active=False)
        self.assertEqual(self.client.get(url).status_code, 403)
