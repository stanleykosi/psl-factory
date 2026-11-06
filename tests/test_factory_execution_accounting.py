"""Replacement-worker accounting through independent review and native receipt."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from apps.agents.models import AgentRun
from apps.documents.models import PublicationReceipt
from apps.finance.models import FinanceRun, FinanceReview
from apps.identity.models import Grant
from apps.policy.factory_recovery_validators import COMPONENT, METHOD
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition, register_reference
from apps.workflows import factory, factory_accounting, factory_execution
from apps.workflows.models import HumanTask
from tests.finance_analysis_helpers import fixture, METRICS
from tests.factory_accounting_helpers import configured
from tests.helpers import activate, rev


class BoundAccountingTests(TestCase):
    def test_replacement_prepares_and_delivers_only_after_independent_native_review(self):
        actor, case, evidence, _, configs, source, template, recipient = fixture(username='bound-accounts-reviewer', recipient_username='bound-accounts-reader', review=False)
        worker = get_user_model().objects.create_user(username='bound-accounts-worker')
        for action in ['case.read', 'factory.read', 'factory.execute', 'finance.read', 'finance.calculate',
                       'agent.finance', 'finance.publish', 'document.draft', 'document.publish', 'evidence.add']:
            Grant.objects.create(case=case, user=worker, action=action)
        # This synthetic publisher needs its own explicit native role; recovery grants none.
        role = register_reference(actor, case.pk, 'finance:replacement-worker', 'schema:psl/role-assignment/v1',
                                  {'role': 'Finance', 'user_id': worker.pk}, evidence['policy_decision'].pk)
        activate(actor, case, 'D05.role_principal_assignments', [*configs['D05.role_principal_assignments'].envelope['value'], role.ref], evidence['policy_decision'])
        from apps.finance import analysis
        analysis.review(actor, case.pk, 'source', source.pk, 'Finance', 'approve', evidence['finance_review'].pk, 'Synthetic current source reviewed', rev(case))
        for component, purpose in analysis.PURPOSE.items():
            analysis.review(actor, case.pk, purpose, configs[component].pk, 'Finance', 'approve', evidence['finance_review'].pk, 'Synthetic exact current rule reviewed', rev(case))
        work = configured(actor, case, evidence, source, template, METRICS, executor_id=worker.pk)['work']
        now = timezone.now()
        rule = dict(definition='finance-accounts/v1', method=METHOD, principal_id=worker.pk, reviewer_id=actor.pk,
                    review_role='Finance', independent_of_worker=True, valid_from=now.isoformat(), valid_until=(now+timedelta(hours=1)).isoformat())
        authority = draft_operator_policy(actor, case.pk, COMPONENT, {'rules': [rule]}, evidence['policy_decision'].pk, now)
        transition(actor, authority.pk, 'validated'); transition(actor, authority.pk, 'active')
        factory_execution.bind(actor, work.pk, work.revision, evidence['policy_decision'].pk, 'Synthetic reviewed independent accounting worker')
        grants = list(Grant.objects.filter(case=case, user=worker).order_by('pk').values())
        Grant.objects.filter(case=case, user=actor, action='factory.execute').update(active=False)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        task = HumanTask.objects.get(case=case, kind='factory_accounting_review', status='open')
        self.assertEqual(task.created_by_id, worker.pk)
        self.assertFalse(FinanceReview.objects.filter(case=case, purpose='output').exists())
        self.assertFalse(PublicationReceipt.objects.filter(publication__version__document__case=case).exists())
        task = factory_accounting.claim(actor, task.pk, task.revision)
        factory_accounting.decide(actor, task.pk, task.revision, 'approve', evidence['finance_review'].pk, 'Synthetic independent exact output and lineage review')
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertEqual(work.status, 'verified', work.finding)
        self.assertEqual(work.actor_id, actor.pk); self.assertEqual(work.execution_actor_id, worker.pk)
        self.assertEqual(set(FinanceRun.objects.filter(case=case).values_list('actor_id', flat=True)), {worker.pk})
        self.assertEqual(set(AgentRun.objects.filter(case=case).values_list('actor_id', flat=True)), {worker.pk})
        output = FinanceRun.objects.get(case=case, kind='formula')
        self.assertEqual(output.result['company']['pbt']['value'], '609.99')
        self.assertEqual(output.result['bu_comparison']['pbt']['difference'], '0.00')
        self.assertFalse(output.result['ledger_posted'])
        decision = FinanceReview.objects.get(case=case, purpose='output', verdict='approve')
        self.assertEqual(decision.actor_id, actor.pk)
        receipt = PublicationReceipt.objects.get(publication__factory_work=work)
        self.assertEqual(receipt.recipient_id, recipient.pk)
        self.assertGreater(work.budget_used, 0); self.assertLessEqual(work.budget_used, work.budget_limit)
        self.assertEqual(list(Grant.objects.filter(case=case, user=worker).order_by('pk').values()), grants)
