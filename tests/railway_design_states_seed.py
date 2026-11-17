"""Prepare named synthetic cases for the state acceptance walkthrough."""
import json
import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from adapters.publications import InternalPublicationAdapter
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.documents.controlled import review_version
from apps.documents.models import PublicationJob
from apps.finance import invoice_delivery
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy.role_assignments import draft as draft_roles, draft_delegations
from apps.policy.services import resolve, transition
from apps.workflows import factory, factory_minutes
from apps.workflows.models import FactoryWork
from tests import correction_helpers, document_helpers, factory_rfp_helpers, planning_helpers, settlement_helpers, test_commercial_changes, test_rfp
from tests.billing_helpers import coverage, policy, stage_policy
from tests.helpers import rev, signed
from tests.test_change_impacts import ChangeImpactTests
from tests.test_factory_minutes import FactoryMinutesTests
from tests.test_factory_reporting import FactoryReportingTests, artifact


class InterruptedMinutesDelivery(InternalPublicationAdapter):
    def deliver(self, job, fence):
        raise TimeoutError('Synthetic receipt unavailable after original dispatch')


@transaction.atomic
def prepare(key, operator):
    case, created = Case.objects.get_or_create(tenant='design-state-walkthrough', kind='project', synthetic=True,
                                               title='Browser design states · ' + key)
    if key == 'money-read-only':
        Grant.objects.get_or_create(case=case, user=operator, action='case.read')
        return {'case': str(case.pk)}
    if key in {'delegation', 'delegation-periods', 'delegation-read-only'}:
        if created:
            Grant.objects.bulk_create([Grant(case=case, user=operator, action=action) for action in dict.fromkeys(ACTIONS)])
        second, _ = get_user_model().objects.get_or_create(username='state-check-delegation-recipient')
        Grant.objects.get_or_create(case=case, user=second, action='case.read')
        proof = case.evidence.filter(kind='policy_decision', source='synthetic:state-walkthrough').first()
        if proof is None:
            proof = add_evidence(operator, case.pk, 'policy_decision', 'Synthetic draft-only verification decision',
                                 'synthetic:state-walkthrough')
        if resolve('D05.role_principal_assignments', case).status != 'ACTIVE':
            role_policy = draft_roles(operator, case.pk, [{'role': 'PM', 'user_id': operator.pk},
                {'role': 'PM', 'user_id': second.pk}], proof.pk, timezone.now())
            transition(operator, role_policy.pk, 'validated')
            transition(operator, role_policy.pk, 'active')
        if key == 'delegation-periods' and resolve('D05.delegation_rules', case).status != 'ACTIVE':
            now = timezone.now()
            rules = [{'role': 'PM', 'principal_id': operator.pk, 'delegate_id': second.pk,
                      'valid_from': (now + timedelta(days=start)).isoformat(),
                      'valid_until': (now + timedelta(days=end)).isoformat()}
                     for start, end in [(-6, -4), (-2, 2), (4, 6)]]
            configured = draft_delegations(operator, case.pk, rules, proof.pk, now)
            transition(operator, configured.pk, 'validated')
            transition(operator, configured.pk, 'active')
        if key == 'delegation-read-only' and created:
            Grant.objects.filter(case=case, user=operator, action='policy.configure').update(active=False)
        return {'case': str(case.pk), 'evidence': proof.pk, 'delegate': second.pk}
    if not created:
        existing = FactoryWork.objects.filter(case=case).first()
        return {'case': str(case.pk), 'work': existing.pk if existing else None}
    Grant.objects.bulk_create([Grant(case=case, user=operator, action=action) for action in dict.fromkeys(ACTIONS)])
    if key == 'assistant-draft':
        with patch.object(planning_helpers, 'setup_case', return_value=(operator, case)):
            planning = planning_helpers.fixture(configured=True, username='state-assistant-draft')
        return {'case': str(case.pk), 'packet': planning['packet'].pk}
    if key == 'bid-intake-walkthrough':
        with patch.object(test_commercial_changes, 'setup_case', return_value=(operator, case)):
            _, _, evidence, _, _ = test_rfp.fixture(record_intake=False)
        return {'case': str(case.pk), 'intake_source': evidence['rfp_intake'].pk}
    if key == 'corrected-money':
        run_invoice = invoice_delivery.run_once
        with (
            patch.object(settlement_helpers, 'setup_case', return_value=(operator, case)),
            patch.object(invoice_delivery, 'run_once', side_effect=lambda: run_invoice(case_id=case.pk)),
        ):
            _, _, billing, issue, evidence = correction_helpers.fixture(identity=True)
            credit = correction_helpers.note(operator, case, issue, evidence, reference='BROWSER-MONEY-CREDIT')
            correction = correction_helpers.apply(operator, case, credit, evidence)
            correction.refresh_from_db()
            if correction.status != 'confirmed':
                raise ValueError('Synthetic invoice credit was not verified')
            receipt, lot = settlement_helpers.receipt(operator, case, ref='browser-money-corrected-cash')
            settlement_helpers.assign(operator, case, receipt, billing, evidence)
            settlement_helpers.allocate(operator, case, lot, issue, '20.00', evidence)
        return {'case': str(case.pk), 'invoice': issue.invoice_id, 'credit': credit.pk, 'receipt': receipt.pk}
    if key in {'signed-money', 'known-money'}:
        agreement = signed(operator, case)['signature']
        billing = coverage(operator, case)
        stage_policy(operator, case, billing, agreement)
        if key == 'known-money':
            transition(operator, resolve('D12.stage_terms', case).configuration.pk, 'revoked')
            policy(operator, case, 'D12.stage_terms', [
                {'coverage_id': billing.pk, 'stage': 'signed_sow', 'amount': '30.00', 'due_date': '2026-11-01'},
                {'coverage_id': billing.pk, 'stage': 'uat', 'amount': '42.50', 'due_date': '2026-12-02'},
                {'coverage_id': billing.pk, 'stage': 'completion', 'amount': '63.75', 'due_date': '2026-12-16'},
            ])
            policy(operator, case, 'D12.uat_billing_predicate_ref',
                   {'coverage_id': billing.pk, 'stage': 'uat', 'milestone_name': 'Synthetic client acceptance'})
        return {'case': str(case.pk), 'agreement': agreement.pk}
    if key in {'bid-loss-walkthrough', 'bid-win-walkthrough', 'bid-award-walkthrough'}:
        with patch.object(test_commercial_changes, 'setup_case', return_value=(operator, case)):
            data = factory_rfp_helpers.configured(reference='RFP-SAMPLE-' + key.upper())
        work = factory_rfp_helpers.start(data, key=key)
        response, _ = factory_rfp_helpers.reviewed_document(data, work)
        factory.run_until_wait(work.pk)
        submission = response.submissions.get()
        evidence = data['evidence']['rfp_outcome']
        if key == 'bid-award-walkthrough':
            evidence = add_evidence(operator, case.pk, 'rfp_outcome',
                                    'Synthetic award notice for the exact submitted response. Awarded price NGN 101.25.',
                                    'synthetic:priced-award')
        return {'case': str(case.pk), 'work': work.pk, 'submission': submission.pk,
                'evidence': evidence.pk}
    users = get_user_model().objects
    create_user = users.create_user
    if key == 'changed-milestone':
        with patch.object(test_commercial_changes, 'setup_case', return_value=(operator, case)):
            entry = ChangeImpactTests()
            entry.setUp()
        entry.approved_report()
        return {'case': str(case.pk), 'work': None}
    is_minutes = key in {'minutes', 'outward-minutes', 'minutes-uncertain'}
    entry = FactoryMinutesTests() if is_minutes else FactoryReportingTests()
    with (
        patch.object(document_helpers, 'setup_case', return_value=(operator, case)),
        patch.object(users, 'create_user', side_effect=lambda username: create_user(username=f'state-check-{key}-{username}')),
    ):
        entry.setUp()
    if is_minutes:
        outward = key != 'minutes'
        entry.start(outward=outward)
        entry.advance()
        if outward:
            entry.confirm()
            entry.advance()
        if key == 'minutes-uncertain':
            binding = factory_minutes.document(entry.work)
            review_version(operator, case.pk, binding.version_id, 'approve', 'Exact synthetic receipt review', rev(case))
            factory.run_until_wait(entry.work.pk, adapter=InterruptedMinutesDelivery())
            job = PublicationJob.objects.get(publication__factory_work=entry.work)
            if job.status != 'unknown':
                raise ValueError('Expected the original synthetic transmission to remain uncertain')
            return {'case': str(case.pk), 'work': entry.work.pk, 'job': job.pk}
    else:
        artifact(operator, case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v1',
                 {'rules': [{'role': 'PMO Lead', 'actions': ['return']}]}, entry.owner)
        entry.start_work()
        entry.advance()
        entry.review('return')
    return {'case': str(case.pk), 'work': entry.work.pk}


if (os.environ.get('RAILWAY_ENVIRONMENT_NAME') != 'design-acceptance' or
        os.environ.get('RAILWAY_PROJECT_ID') != 'f957481b-c6f7-43af-bc66-449a330a9d53'):
    raise SystemExit('Exact isolated acceptance environment required')

trial = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
workflow = os.environ.get('PSL_STATE_WALKTHROUGH')
if workflow == 'money-and-bids':
    fixtures = ('known-money', 'bid-loss-walkthrough', 'bid-win-walkthrough', 'delegation-periods', 'delegation-read-only')
elif workflow == 'award-and-money-access':
    fixtures = ('bid-award-walkthrough', 'money-read-only', 'bid-intake-walkthrough', 'corrected-money')
else:
    fixtures = ('delegation', 'minutes', 'weekly', 'outward-minutes', 'changed-milestone', 'assistant-draft', 'signed-money', 'minutes-uncertain')
failed = False
for fixture in fixtures:
    try:
        result = prepare(fixture, trial)
    except Exception as exc:
        failed = True
        print(f'PSL_STATE_ERROR={fixture}: {type(exc).__name__}: {str(exc)[:240]}', flush=True)
    else:
        print('PSL_STATE_FIXTURE=' + json.dumps({'fixture': fixture, **result}), flush=True)
if failed:
    raise SystemExit(1)
