from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.models import Evidence
from apps.core.services import lock_case, event, bump
from apps.identity.services import require
from apps.policy.services import role_policy
from apps.workflows.models import Outbox
from .models import Baseline, Decision, Milestone


def subject(case, pk, kind=None):
    evidence = Evidence.objects.filter(case=case, pk=pk).first()
    if not evidence or kind and evidence.kind != kind:
        raise ValidationError('Evidence must match this case and required kind')
    if evidence.kind.startswith('agent_private_'):
        raise ValidationError('Private agent source evidence requires its scoped data interface')
    return evidence


def guard_prepare(actor, case, plan_id, cost_id, sow_id):
    require(actor,case,'baseline.prepare')
    commercial_guard(case)
    if case.kind != 'project':
        raise ValidationError('A project is required')
    for kind in ['requirements', 'engineering_estimate', 'security_estimate']:
        if not case.evidence.filter(kind=kind).exists():
            raise ValidationError('Missing ' + kind + ' evidence')
    plan, cost, sow = subject(case, plan_id, 'plan'), subject(case, cost_id, 'costing'), subject(case, sow_id, 'sow')
    if hasattr(case, 'baseline') and case.baseline.signed_id:
        raise ValidationError('Signed baseline revisions need a change workflow; never overwrite')
    if hasattr(case, 'baseline') and case.baseline.plan_id != plan.pk and case.baseline.costing_id == cost.pk:
        raise ValidationError('Changed plan needs a new costing version; non-cost approval reuse is unconfigured')
    from .costing import verify_costing
    verify_costing(cost,plan.pk)
    return plan, cost, sow


@transaction.atomic
def prepare_baseline(actor, case_id, plan_id, cost_id, sow_id, expected):
    case = lock_case(actor, case_id, 'baseline.prepare', expected)
    plan, cost, sow = guard_prepare(actor,case,plan_id,cost_id,sow_id)
    baseline, _ = Baseline.objects.update_or_create(case=case, defaults={'plan': plan, 'costing': cost, 'sow': sow})
    event(actor, case, 'baseline.prepared', plan=plan.pk, costing=cost.pk, sow=sow.pk)
    bump(case)
    return baseline


def guard_decide(actor, case, role):
    require(actor,case,'decision.record')
    commercial_guard(case)
    policy = role_policy(actor, case, role)
    baseline = Baseline.objects.get(case=case)
    from .costing import verify_costing
    if role!='PMO Lead':verify_costing(baseline.costing,baseline.plan_id)
    if baseline.signed_id:
        raise ValidationError('Signed baseline is immutable')
    if role == 'PMO Lead':
        target = baseline.sow
    else:
        order = ['PM', 'Head of PMO', 'CEO']
        if role not in order:
            raise ValidationError('Unsupported costing role')
        target = baseline.costing
        prior = set(Decision.objects.filter(evidence=target, policy=policy).values_list('role', flat=True))
        if any(r not in prior for r in order[:order.index(role)]):
            raise ValidationError('Required costing order is PM, Head of PMO, CEO')
    if Decision.objects.filter(evidence=target, role=role, policy=policy).exists():
        raise ValidationError('Decision already recorded for this exact version')
    return target, policy


@transaction.atomic
def decide(actor, case_id, role, expected):
    case = lock_case(actor, case_id, 'decision.record', expected)
    target, policy = guard_decide(actor,case,role)
    result = Decision.objects.create(case=case, evidence=target, role=role, actor=actor, policy=policy)
    event(actor, case, 'decision.recorded', evidence=target.pk, sha256=target.sha256, role=role, policy=policy.pk)
    bump(case)
    return result


def guard_sign(actor, case, signature_id):
    require(actor,case,'baseline.sign')
    commercial_guard(case)
    baseline = Baseline.objects.get(case=case)
    from .costing import verify_costing
    verify_costing(baseline.costing,baseline.plan_id)
    if baseline.signed_id:
        raise ValidationError('Baseline already signed')
    roles = set(Decision.objects.filter(evidence=baseline.costing).values_list('role', flat=True))
    if not {'PM', 'Head of PMO', 'CEO'}.issubset(roles) or not Decision.objects.filter(evidence=baseline.sow, role='PMO Lead').exists():
        raise ValidationError('Current cost approvals and distinct document review required')
    for role, target in [('PM', baseline.costing), ('Head of PMO', baseline.costing), ('CEO', baseline.costing), ('PMO Lead', baseline.sow)]:
        decision = Decision.objects.filter(evidence=target, role=role).order_by('-pk').first()
        if not decision:
            raise ValidationError('Current version human decision is missing')
        current_policy = role_policy(decision.actor, case, decision.role)
        if current_policy.pk != decision.policy_id:
            raise ValidationError('Decision authority configuration changed; obtain current version decisions')
    return baseline, subject(case,signature_id,'signature')


@transaction.atomic
def sign_baseline(actor, case_id, signature_id, expected):
    case = lock_case(actor, case_id, 'baseline.sign', expected)
    baseline, signature = guard_sign(actor,case,signature_id)
    baseline.signed = signature
    baseline.save(update_fields=['signed'])
    event(actor, case, 'baseline.signed', signature=baseline.signed_id, plan=baseline.plan_id, costing=baseline.costing_id, sow=baseline.sow_id)
    bump(case)
    return baseline


def guard_complete(actor, case, name, evidence_id):
    require(actor,case,'milestone.complete')
    if not Baseline.objects.filter(case=case, signed__isnull=False).exists():
        raise ValidationError('Signed planning baseline required')
    if not name.strip() or Milestone.objects.filter(case=case, name=name).exists():
        raise ValidationError('Milestone identity must be nonempty and unique')
    evidence = subject(case, evidence_id, 'completion')
    return evidence


@transaction.atomic
def complete_milestone(actor, case_id, name, evidence_id, expected):
    case = lock_case(actor, case_id, 'milestone.complete', expected)
    evidence = guard_complete(actor,case,name,evidence_id)
    milestone = Milestone.objects.create(case=case, name=name, evidence=evidence, completed_by=actor)
    key = f'milestone:{milestone.pk}:finance:v1'
    # Deliberately narrow Finance projection, no entire project payload or automatic invoice.
    Outbox.objects.create(case=case, milestone=milestone, actor=actor, operation_key=key,
        payload={'milestone_id': milestone.pk, 'name': name, 'evidence_id': evidence.pk, 'evidence_sha256': evidence.sha256})
    event(actor, case, 'milestone.completed', milestone=milestone.pk, operation_key=key)
    bump(case)
    return milestone


def commercial_guard(case):
    from .models import CommercialCase,RFPCase
    if CommercialCase.objects.filter(case=case).exists() or RFPCase.objects.filter(case=case).exists():
        raise ValidationError('Use the versioned commercial workbench for this case; legacy commands cannot bypass proposal controls')
