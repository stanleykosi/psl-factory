import copy
import json
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.evidence_access import public_evidence
from apps.core.models import Evidence
from apps.identity.models import Grant
from apps.pmo import planning, planning_inputs
from apps.pmo.models import PlanningDepartmentInput
from apps.policy.planning_validators import COMPONENT, DEPARTMENTS
from apps.policy.services import active_component, reference_values
from apps.workflows import factory, factory_planning
from .helpers import rev
from .planning_helpers import criteria, observe, evidence
from .test_factory_planning import setup


RULES = json.loads(Path('fixtures/planning-department-inputs.json').read_text())['rules']


def enhanced(configured=True):
    f = setup()
    payload = dict(f['payload'], collect_department_inputs=True)
    f['packet'] = planning.capture(f['a'], f['c'].pk, payload, f['packet'].pk)
    f['payload'] = payload
    for purpose, meeting in f['meetings'].items():
        planning.align(f['a'], f['c'].pk, f['packet'].pk, purpose, meeting.pk)
    f['pair'] = planning.open_requests(f['a'], f['c'].pk, f['packet'].pk)
    if configured:
        f['rules']['department_inputs'] = copy.deepcopy(RULES)
        criteria(f)
    return f


def record(f, department='Engineering', previous=None, state='known', days=Decimal('0')):
    return planning_inputs.record(f['a'], f['c'].pk, f['packet'].pk, department,
        previous.pk if previous else None, f['e']['plan'].pk, 'Synthetic department colleague',
        timezone.now(), 'Synthetic department work and effort supplied.', state, days, rev(f['c']))


class PlanningDepartmentInputTests(TestCase):
    def test_fresh_costing_decision_binds_new_native_calculation_and_all_direct_approvals(self):
        from apps.core.services import add_evidence
        from apps.pmo import commercial, costing, engagement
        from apps.policy.operator_drafts import draft_operator_policy
        from apps.policy.services import transition
        from .costing_helpers import fixture as costing_fixture, run as calculate
        cost = costing_fixture()
        actor, case, sources = cost['actor'], cost['case'], cost['sources']
        engagement_source = add_evidence(actor, case.pk, 'engagement_source',
            'Synthetic direct project source', 'synthetic:department-costing')
        engagement.capture(actor, case.pk, 'B', engagement_source.pk, 'department-costing', 'capture-department-costing')
        sample = json.loads(Path('fixtures/planning-packet.json').read_text())
        payload = sample['capture']
        payload.update(prd_id=sources['requirements'].pk, scope_id=sources['plan'].pk,
            engineering_estimate_id=sources['engineering_estimate'].pk,
            security_estimate_id=sources['security_estimate'].pk, collect_department_inputs=True)
        packet = planning.capture(actor, case.pk, payload)
        sample['criteria']['department_inputs'] = dict(RULES, changed_effort_action='fresh_costing_required')
        policy = draft_operator_policy(actor, case.pk, COMPONENT, sample['criteria'], sources['policy_decision'].pk, timezone.now())
        transition(actor, policy.pk, 'validated')
        transition(actor, policy.pk, 'active')
        f = {'a': actor, 'c': case, 'e': sources, 'packet': packet}
        rows = {department: record(f, department) for department in DEPARTMENTS}
        record(f, previous=rows['Engineering'], days=Decimal('1'))
        run = calculate(cost, key='changed-department-effort')
        bound = costing.bind(actor, case.pk, run.pk)
        selected = {key: sources[key].pk for key in commercial.SOURCE_KINDS}
        selected['costing'] = bound.costing_id
        proposal = commercial.propose(actor, case.pk, selected, sources['requirements'].pk,
            'Synthetic fresh costing for the exact changed input.', rev(case))
        with self.assertRaises(ValidationError):
            planning_inputs.review(actor, case.pk, packet.pk, 'PM', 'new_costing', sources['policy_decision'].pk,
                'Required commercial reviews remain pending.', rev(case))
        for role in commercial.ROLES:
            commercial.decide_proposal(actor, case.pk, proposal.pk, role, 'approve',
                'Synthetic direct approval of the exact new costing proposal.', rev(case))
        result = planning_inputs.review(actor, case.pk, packet.pk, 'PM', 'new_costing', sources['policy_decision'].pk,
            'Reviewed changed department effort against the fresh calculation and direct approvals.', rev(case))
        context = planning_inputs.required(case, packet, actor)
        self.assertEqual(context['review_id'], result.pk)
        content = json.loads(result.body)
        self.assertEqual(content['commercial']['run'], run.pk)
        self.assertEqual(len(content['commercial']['approvals']), 4)

    def test_received_facts_survive_missing_policy_unknowns_and_cannot_disable_collection(self):
        f = enhanced(False)
        row = record(f, state='unknown', days=None)
        self.assertIsNone(row.person_days)
        self.assertEqual(planning_inputs.projection(f['a'], f['c'], f['packet'])['rows'][0]['record']['effort_state'], 'unknown')
        with self.assertRaisesMessage(ValidationError, 'department input requirements'):
            planning_inputs.required(f['c'], f['packet'], f['a'])
        with self.assertRaisesMessage(ValidationError, 'Retain department input collection'):
            planning.capture(f['a'], f['c'].pk, dict(f['payload'], collect_department_inputs=False), f['packet'].pk)
        f['rules']['department_inputs'] = copy.deepcopy(RULES)
        criteria(f)
        for department in DEPARTMENTS[1:]:
            record(f, department)
        with self.assertRaisesMessage(ValidationError, 'effort is still unknown'):
            planning_inputs.required(f['c'], f['packet'], f['a'])
        current = record(f, previous=row, days=Decimal('0'))
        self.assertEqual(current.person_days, 0)
        with self.assertRaises(ValidationError):
            planning_inputs.required(f['c'], f['packet'], f['a'])
        self.assertEqual(PlanningDepartmentInput.objects.filter(case=f['c']).count(), 6)

    def test_five_departments_reach_native_handoff_and_changed_effort_requires_exact_human_review(self):
        f = enhanced()
        rows = {department: record(f, department) for department in DEPARTMENTS}
        observe(f)
        factory.run_until_wait(f['work'].pk)
        f['work'].refresh_from_db()
        self.assertEqual(f['work'].status, 'verified', f['work'].finding)
        initial = factory_planning.verified_output(f['work'])
        self.assertTrue(initial['verified'])
        successor = record(f, previous=rows['Engineering'], days=Decimal('2.500'))
        with self.assertRaises(ValidationError):
            factory_planning.verified_output(f['work'])
        planning_inputs.review(f['a'], f['c'].pk, f['packet'].pk, 'PM', 'retain_costing',
            f['e']['policy_decision'].pk, 'Synthetic authorised decision to retain costing for this exact change.', rev(f['c']))
        self.assertIn('review_id', planning_inputs.required(f['c'], f['packet'], f['a']))
        review = f['c'].evidence.filter(kind='planning_department_review').latest('pk')
        self.assertFalse(public_evidence(Evidence.objects.filter(pk=review.pk)).exists())
        spent = f['work'].budget_used
        factory_planning.reassess(f['a'], f['work'].pk, f['work'].revision, 'Reassess the exact changed department input.')
        factory.run_until_wait(f['work'].pk)
        f['work'].refresh_from_db()
        self.assertEqual(f['work'].status, 'verified', f['work'].finding)
        self.assertGreater(f['work'].budget_used, spent)
        self.assertEqual(successor.previous_id, rows['Engineering'].pk)
        record(f, previous=successor, days=Decimal('3'))
        with self.assertRaisesMessage(ValidationError, 'exact department inputs'):
            planning_inputs.required(f['c'], f['packet'], f['a'])

    def test_http_typed_capture_draft_rules_access_and_database_provenance(self):
        f = enhanced()
        factory.run_until_wait(f['work'].pk)
        f['work'].refresh_from_db()
        self.client.force_login(f['a'])
        url = reverse('factory_detail', args=[f['work'].pk])
        page = self.client.get(url)
        self.assertContains(page, 'Department inputs')
        self.assertContains(page, 'Record Infrastructure input or correction')
        values = {'action': 'department_input', 'revision': f['work'].revision, 'case_revision': rev(f['c']),
            'packet_id': f['packet'].pk, 'department': 'QA', 'source_id': f['e']['plan'].pk,
            'source_party': 'Synthetic tester', 'received_at': timezone.now().isoformat(),
            'summary': 'Test scope supplied. Effort has not been estimated.', 'effort_state': 'unknown'}
        self.assertEqual(self.client.post(url, values).status_code, 302)
        row = PlanningDepartmentInput.objects.get(case=f['c'])
        self.assertIsNone(row.person_days)
        self.assertContains(self.client.post(url, values), 'planning work changed')
        private = evidence(f, 'qbo_native_intent', 'Private Finance source excluded from Planning capture')
        with self.assertRaises(ValidationError):
            planning_inputs.record(f['a'], f['c'].pk, f['packet'].pk, 'Product', None, private.pk,
                'Synthetic colleague', timezone.now(), 'Wrong source', 'unknown', None, rev(f['c']))
        with self.assertRaises(DatabaseError), transaction.atomic():
            PlanningDepartmentInput.objects.filter(pk=row.pk).update(summary='Overwritten history')
        with self.assertRaises(ValidationError):
            record(f, 'QA')
        f['work'].refresh_from_db()
        base = active_component(COMPONENT, f['c'])
        values = dict(RULES, action='department_input_rules', revision=f['work'].revision,
            case_revision=rev(f['c']), base_configuration=base.pk, evidence_id=f['e']['policy_decision'].pk,
            allow_recorder_review='yes')
        self.assertEqual(self.client.post(url, values).status_code, 302)
        self.assertEqual(active_component(COMPONENT, f['c']).pk, base.pk)
        Grant.objects.filter(case=f['c'], user=f['a'], action='planning.coordinate').update(active=False)
        with self.assertRaises(PermissionDenied):
            record(f, 'QA', previous=row)
        page = self.client.get(url)
        self.assertNotContains(page, 'Record QA input or correction')

    def test_changed_effort_rules_require_fresh_costing_and_current_recorder_and_reviewer_authority(self):
        f = enhanced()
        rows = {department: record(f, department) for department in DEPARTMENTS}
        record(f, previous=rows['Engineering'], days=Decimal('1'))
        f['rules']['department_inputs']['changed_effort_action'] = 'fresh_costing_required'
        criteria(f)
        with self.assertRaisesMessage(ValidationError, 'requires fresh costing'):
            planning_inputs.review(f['a'], f['c'].pk, f['packet'].pk, 'PM', 'retain_costing',
                f['e']['policy_decision'].pk, 'Synthetic retained costing request.', rev(f['c']))
        with self.assertRaisesMessage(ValidationError, 'fresh commercial proposal'):
            planning_inputs.review(f['a'], f['c'].pk, f['packet'].pk, 'PM', 'new_costing',
                f['e']['policy_decision'].pk, 'Synthetic new costing claim without an approved calculation.', rev(f['c']))
        f['rules']['department_inputs']['changed_effort_action'] = 'review_required'
        f['rules']['department_inputs']['allow_recorder_review'] = False
        criteria(f)
        with self.assertRaises(PermissionDenied):
            planning_inputs.review(f['a'], f['c'].pk, f['packet'].pk, 'PM', 'retain_costing',
                f['e']['policy_decision'].pk, 'Synthetic self-review request.', rev(f['c']))
        Grant.objects.filter(case=f['c'], user=f['a'], action='planning.coordinate').update(active=False)
        with self.assertRaises(PermissionDenied):
            planning_inputs.required(f['c'], f['packet'], f['a'])


class PlanningDepartmentInputConcurrencyTests(TransactionTestCase):
    def test_competing_corrections_preserve_one_successor_and_explicit_stale_result(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections
        f = enhanced()
        original = record(f)
        expected = rev(f['c'])
        barrier = Barrier(2)

        def correct(days):
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                result = planning_inputs.record(f['a'], f['c'].pk, f['packet'].pk, 'Engineering', original.pk,
                    f['e']['plan'].pk, 'Synthetic department colleague', timezone.now(),
                    'Competing synthetic correction', 'known', Decimal(days), expected)
                return ('recorded', result.pk)
            except ValidationError:
                return ('stale', None)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(correct, ['1', '2']))
        self.assertCountEqual([status for status, _ in results], ['recorded', 'stale'])
        rows = list(PlanningDepartmentInput.objects.filter(packet=f['packet']).order_by('version'))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1].previous_id, original.pk)
