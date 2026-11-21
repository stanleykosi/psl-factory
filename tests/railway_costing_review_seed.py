"""Separate synthetic calculator with independently supplied proposed examples."""
import copy
import json
import os
from datetime import timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.documents.contracts import digest
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import costing, costing_proposals
from apps.pmo.costing_models import CostingRun
from apps.pmo.costing_proposal_models import CostingProposal, CostingProposalDecision
from apps.policy.costing_drafts import draft_costing_policy
from apps.policy.costing_proposal_validators import COMPONENT
from apps.policy.services import register_reference, transition
from tests.helpers import activate, project_evidence, rev
from tests.operator_helpers import policy as operator_policy
from tests.railway_independent_commercial_seed import PROJECT


TENANT = 'design-independent-costing-review'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
TITLE = 'SAMPLE Harbor Studio calculator version review'
TRIAL = 'psl-agent-trial'
PEOPLE = {'maker': 'sample-calculator-version-preparer', 'owner': 'sample-calculator-rule-owner',
          'oracle_owner': 'sample-calculator-example-owner'}
TRIAL_ACTIONS = {'case.read', 'costing.read', 'costing.source.read', 'costing.rule.review'}
MARKER = 'sample.calculator_version_review_prepared'
ACTIVE = 'sample.calculator_version_review_activated'
VALUES = Path(__file__).resolve().parent.parent / 'fixtures' / 'commercial-costing.json'


def supplied(actor, case, kind, value, source):
    body = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value
    return add_evidence(actor, case.pk, kind, body, f'synthetic:{source}')


def install(actor, case, decision_id, rule, rule_review, oracle, oracle_review):
    value = {'rule_id': rule.pk, 'rule_sha256': rule.sha256, 'rule_review_id': rule_review.pk,
             'oracle_id': oracle.pk, 'oracle_sha256': oracle.sha256, 'oracle_review_id': oracle_review.pk}
    configuration = draft_costing_policy(actor, case.pk, value, decision_id, timezone.now() - timedelta(seconds=1))
    transition(actor, configuration.pk, 'validated')
    transition(actor, configuration.pk, 'active')
    return configuration


def supplied_examples(actor, case, rule_value, examples, locator):
    return supplied(actor, case, 'p14_oracle', {
        'rule_sha256': digest(rule_value), 'calculator_ref': rule_value['calculator_ref'],
        'calculator_version': rule_value['calculator_version'], 'source_class': 'synthetic_fixture',
        'source_locator': locator, 'scenarios': examples,
    }, 'independently-authored-costing-examples')


def calculate(actor, case, sources, key):
    return costing.run(actor, case.pk, sources['plan'], sources['engineering_estimate'], sources['security_estimate'],
                       sources['inputs'], key, rev(case))


def populate(case, trial, people):
    maker, owner, oracle_owner = (people[key] for key in PEOPLE)
    sources = project_evidence(maker, case)
    decision = sources['policy_decision']
    assignments = (('PMO', owner), ('Finance', oracle_owner), ('PMO Lead', trial))
    refs = [register_reference(maker, case.pk, f'sample-costing-review:{role}', 'schema:psl/role-assignment/v1',
                              {'role': role, 'user_id': actor.pk}, decision.pk).ref for role, actor in assignments]
    activate(maker, case, 'D05.role_principal_assignments', refs, decision)
    operator_policy({'actor': maker, 'case': case, 'sources': sources}, COMPONENT,
                    {'reviewer_id': trial.pk, 'reviewer_role': 'PMO Lead', 'independent_review': True})
    raw = json.loads(VALUES.read_text(encoding='utf-8'))
    current = raw['rule']
    current.update(owner_id=owner.pk, oracle_owner_id=oracle_owner.pk)
    current['parameters'][0]['evidence_id'] = supplied(maker, case, 'p14_parameter',
        'SAMPLE version 1 author-supplied rate 10.00 NGN per hour', 'costing-v1-rate').pk
    first_proof = supplied(maker, case, 'p14_rule', current, 'first-sample-calculator')
    rule = costing.capture_rule(maker, case.pk, 'sample-hourly-studio', first_proof.pk, rev(case))
    owner_proof = supplied(owner, case, 'p14_review', 'SAMPLE exact source owner confirmation.', 'costing-owner-review')
    oracle_review_proof = supplied(oracle_owner, case, 'p14_review', 'SAMPLE independent expected output review.', 'costing-oracle-review')
    rule_review = costing.review(owner, case.pk, rule.pk, None, 'confirm', 'sample-v1-source', owner_proof.pk, rev(case))
    old_examples = supplied_examples(oracle_owner, case, current, raw['scenarios'], 'Sample independent version 1 examples')
    oracle = costing.capture_oracle(oracle_owner, case.pk, rule.pk, 'sample-expected-v1', old_examples.pk, rev(case))
    oracle_review = costing.review(oracle_owner, case.pk, rule.pk, oracle.pk, 'confirm', 'sample-v1-examples',
                                   oracle_review_proof.pk, rev(case))
    install(maker, case, decision.pk, rule, rule_review, oracle, oracle_review)
    source_ids = {key: sources[key].pk for key in ('plan', 'engineering_estimate', 'security_estimate')}
    source_ids['inputs'] = supplied(maker, case, 'p14_inputs', raw['scenarios'][0]['inputs'], 'exact-costing-inputs').pk
    prior = calculate(maker, case, source_ids, 'sample-calculation-before-review')

    proposed = copy.deepcopy(current)
    proposed.update(calculator_version='v2', calculator_sha256='b' * 64)
    proposed['parameters'][0].update(value='12.00', evidence_id=supplied(maker, case, 'p14_parameter',
        'SAMPLE version 2 author-supplied rate 12.00 NGN per hour', 'costing-v2-rate').pk)
    proposed_proof = supplied(maker, case, 'p14_rule', proposed, 'proposed-sample-calculator')
    proposal = costing_proposals.propose(maker, case.pk, rule.pk, proposed_proof.pk,
        'SAMPLE engineering rate revised from 10.00 to 12.00', 'sample-hourly-review', rev(case))
    examples = copy.deepcopy(raw['scenarios'])
    expected = {'normal': '24.00', 'unknown': None, 'rounding': '1.21'}
    for scenario in examples:
        scenario['expected']['values'][0]['value'] = expected[scenario['key']]
    proposed_examples = supplied_examples(oracle_owner, case, proposed, examples, 'Sample independent version 2 examples')
    reviewer_proof = supplied(maker, case, 'p14_review', 'SAMPLE Trial review form evidence for version 2.', 'costing-trial-review')
    return event(maker, case, MARKER, trial=trial.pk, **{key: actor.pk for key, actor in people.items()},
        rule=rule.pk, oracle=oracle.pk, proposal=proposal.pk, example_proof=proposed_examples.pk, old_run=prior.pk,
        trial_proof=reviewer_proof.pk, owner_proof=owner_proof.pk, oracle_review_proof=oracle_review_proof.pk,
        policy_proof=decision.pk, sources=source_ids)


@transaction.atomic
def prepare():
    trial = get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    if Case.objects.filter(tenant=TENANT).exclude(pk=CASE_ID).exists():
        raise RuntimeError('Preserve work outside this exact synthetic Studio specimen.')
    case, created = Case.objects.get_or_create(pk=CASE_ID, defaults={
        'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True,
    })
    case = Case.objects.select_for_update().get(pk=case.pk)
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Use only the exact synthetic calculator specimen.')
    if created:
        people = {key: get_user_model().objects.create_user(name) for key, name in PEOPLE.items()}
        Grant.objects.bulk_create([Grant(case=case, user=actor, action=action)
            for actor in people.values() for action in dict.fromkeys(ACTIONS)])
        Grant.objects.bulk_create([Grant(case=case, user=trial, action=action) for action in sorted(TRIAL_ACTIONS)])
        marker = populate(case, trial, people)
    else:
        marker = Audit.objects.get(case=case, action=MARKER)
    data = marker.data
    for key, name in PEOPLE.items():
        actor = get_user_model().objects.get(pk=data[key], username=name, is_active=True, is_staff=False, is_superuser=False)
        if actor.has_usable_password():
            raise RuntimeError('Preserve the noninteractive fixture principals.')
    if (data['trial'] != trial.pk or len({data[key] for key in PEOPLE} | {trial.pk}) != 4
            or set(Grant.objects.filter(case=case, user=trial, active=True).values_list('action', flat=True)) != TRIAL_ACTIONS):
        raise RuntimeError('Preserve the exact independent Trial decisions and case-local review grants.')
    proposed = CostingProposal.objects.get(pk=data['proposal'], base_id=data['rule'], base__case=case, actor_id=data['maker'])
    if not any(entry['proof'].pk == data['example_proof'] for entry in costing_proposals.proposed_example_sources(trial, proposed)):
        raise RuntimeError('The exact original independent example source is required.')
    original = CostingRun.objects.get(pk=data['old_run'], case=case, rule_id=data['rule'])
    if original.result['values'][0]['value'] != '20.00':
        raise RuntimeError('Preserve the original version 1 calculation.')
    review = CostingProposalDecision.objects.filter(proposal=proposed).first()
    if review and (review.actor_id != trial.pk or review.evidence_id != data['trial_proof'] or review.verdict != 'confirm'):
        raise RuntimeError('Preserve the separate Trial confirmation with its exact prepared proof.')
    url = reverse('costing_proposal', args=[case.pk, proposed.pk])
    return {**data, 'case': str(case.pk), 'url': url, 'comparison': f"{url}?proposed_examples={data['example_proof']}",
            'decision': review.pk if review else None, 'preserved': not created}


@transaction.atomic
def activate_reviewed():
    case = Case.objects.select_for_update().get(pk=CASE_ID, synthetic=True, tenant=TENANT, title=TITLE)
    data = prepare()
    if data['decision'] is None:
        raise RuntimeError('An actual exact Trial proposal confirmation must be recorded first.')
    review = CostingProposalDecision.objects.select_related('rule').get(pk=data['decision'], actor_id=data['trial'], verdict='confirm')
    if review.rule_id is None or review.rule.version != 2 or review.rule.sha256 != review.proposal.sha256:
        raise RuntimeError('An actual exact Trial proposal confirmation must be recorded first.')
    rule = review.rule
    maker, owner, oracle_owner = (get_user_model().objects.get(pk=data[key]) for key in PEOPLE)
    done = Audit.objects.filter(case=case, action=ACTIVE, actor=maker).first()
    if done:
        _, active_rule, active_oracle, _ = costing.configured(case, maker)
        if active_rule.pk != rule.pk or active_oracle.evidence_id != data['example_proof']:
            raise RuntimeError('Preserve the original exact activation.')
        return {**data, **done.data, 'activation_preserved': True}
    rule_review = costing.review(owner, case.pk, rule.pk, None, 'confirm', 'sample-v2-source', data['owner_proof'], rev(case))
    oracle = costing.capture_oracle(oracle_owner, case.pk, rule.pk, 'sample-expected-v2', data['example_proof'], rev(case))
    oracle_review = costing.review(oracle_owner, case.pk, rule.pk, oracle.pk, 'confirm', 'sample-v2-examples',
                                   data['oracle_review_proof'], rev(case))
    installed = install(maker, case, data['policy_proof'], rule, rule_review, oracle, oracle_review)
    computed = calculate(maker, case, data['sources'], 'sample-calculation-after-activation')
    if computed.result['values'][0]['value'] != '24.00':
        raise RuntimeError('The successor calculation must match its exact independently defined result.')
    done = event(maker, case, ACTIVE, activated_rule=rule.pk, activated_oracle=oracle.pk, configuration=installed.pk,
                 rule_review=rule_review.pk, oracle_review=oracle_review.pk, new_run=computed.pk)
    return {**data, **done.data, 'activation_preserved': False}


def run(action='prepare'):
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_COSTING_REVIEW_FIXTURE')) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The exact Railway test project and costing fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_') or database != connection.settings_dict['NAME']:
        raise RuntimeError('Set the exact preview database before preparing the costing specimen.')
    commands = {'prepare': prepare, 'activate': activate_reviewed}
    if action not in commands:
        raise RuntimeError('Select specimen preparation or activation after exact Trial review.')
    print('PSL_COSTING_REVIEW_FIXTURE=' + json.dumps(commands[action]()), flush=True)
