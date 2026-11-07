"""Bounded F31/F45 investigation; private evidence, no invoice or outbound tools."""
from datetime import date
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.contrib.auth import get_user_model
from apps.core.services import lock_case, event, bump
from apps.finance import contract_coverage as service
from apps.finance.models import CoverageTerms, CoverageInvoiceReference
from .models import AgentRun

PROVIDER = 'deterministic-contract-coverage-v1'


def questions(result):
    out = []
    for finding in result['findings']:
        out.append({'finding': finding, 'question':
            'Please resolve this exact source finding with a corrected authoritative record/version or an evidenced typed decision: ' + finding})
    for row in result['obligations']:
        if row['status'] in ['missing_invoice', 'conflict', 'indeterminate']:
            out.append({'finding': row['status'], 'obligation': row['key'], 'question':
                f"For contractual period {row['start']} to {row['end']} (bill date {row['bill_on']}), provide the exact issued invoice reference and verification evidence, or confirm the internal preparation work needed. Current status: {row['status']}."})
    return out


@transaction.atomic
def investigate(actor, case_id, terms_id, as_of, process_id, expected):
    case = lock_case(actor, case_id, 'agent.coverage', expected)
    if process_id not in ['F31', 'F45']:
        raise ValidationError('Choose the actual F31 or F45 investigation scope')
    terms = service.exact(case, CoverageTerms, terms_id)
    service.terms_access(actor, terms, 'investigate', current=False)
    snapshot, result = service.projection(actor, terms, as_of)
    citations = [{'id': e.pk, 'kind': e.kind, 'sha256': e.sha256}
                 for e in [terms.evidence, terms.register.evidence, terms.contract.evidence]]
    interpretation=terms.payload.get('schedule_interpretation') or {}
    if interpretation.get('evidence_id'):
        try:
            e=service.evidence(case,interpretation['evidence_id'],'coverage_schedule_interpretation',[terms.contract.reference],'configure')
            citations.append({'id':e.pk,'kind':e.kind,'sha256':e.sha256})
        except ValidationError:pass
    for ref in CoverageInvoiceReference.objects.filter(pk__in=[r['id'] for r in snapshot['invoices']]):
        service.invoice_current(actor, ref)
        for e in [ref.evidence, ref.source.evidence]:
            citations.append({'id': e.pk, 'kind': e.kind, 'sha256': e.sha256})
    output = {'process_id': process_id, 'terms': terms.pk, 'snapshot': snapshot,
              'assessment': result, 'questions': questions(result), 'citations': citations,
              'owner_id': terms.payload['owner_id'],
              'owner_status': 'configured' if terms.payload['owner_id'] else 'unassigned',
              'external_communication': False, 'invoice_issued': False,
              'approval_granted': False, 'policy_changed': False}
    run = AgentRun.objects.create(case=case, actor=actor, evidence=terms.evidence,
        provider=PROVIDER, process_id=process_id, result=output)
    event(actor, case, 'agent.contract_coverage_investigated', run=run.pk, process_id=process_id)
    bump(case)
    return run


def current_run(actor, run):
    if run.provider != PROVIDER or run.process_id not in ['F31', 'F45']:
        raise ValidationError('Exact coverage investigation required')
    terms = service.exact(run.case, CoverageTerms, run.result['terms'])
    service.terms_access(actor, terms, 'read', current=False)
    service.terms_access(run.actor, terms, 'investigate', current=False)
    if run.evidence_id != terms.evidence_id:
        raise ValidationError('Private coverage evidence differs')
    for principal in [actor, run.actor]:
        snapshot, result = service.projection(principal, terms, date.fromisoformat(run.result['snapshot']['as_of']))
        if snapshot != run.result['snapshot'] or result != run.result['assessment']:
            raise ValidationError('Investigation is stale; investigate current evidence again')
    return terms


@transaction.atomic
def request_owner_question(actor, case_id, run_id, expected):
    case = lock_case(actor, case_id, 'agent.coverage', expected)
    run = AgentRun.objects.filter(case=case, pk=run_id, provider=PROVIDER).first()
    if not run:
        raise ValidationError('Exact coverage investigation required')
    terms = current_run(actor, run)
    service.terms_access(actor, terms, 'investigate', current=False)
    owner_id = terms.payload['owner_id']
    if not owner_id:
        raise ValidationError('Owner unassigned; configure an evidenced owner before requesting an internal question')
    owner = get_user_model().objects.get(pk=owner_id)
    service.terms_access(owner, terms)
    if not run.result['questions']:
        raise ValidationError('No unresolved owner questions in this current investigation')
    from apps.workflows.models import HumanTask, TaskEvent
    # Generic task metadata only: no private findings in a broad task inbox.
    key = 'coverage-question:' + service.digest({'run': run.pk, 'owner': owner.pk})
    task, created = HumanTask.objects.get_or_create(factory_key=key, defaults={
        'case': case, 'kind': 'factory_information', 'required_role': 'Configured coverage owner',
        'claimed_by': owner, 'created_by': actor,
        'context': {'purpose':'coverage_owner_question','run_id': run.pk, 'owner_id': owner.pk, 'private_console': 'finance_contract_coverage'}})
    if created:
        TaskEvent.objects.create(task=task, actor=actor, action='requested', data={'run_id': run.pk})
        event(actor, case, 'coverage.owner_question_requested', task=task.pk)
        bump(case)
    return task


@transaction.atomic
def investigate_charge(actor, case_id, charge_id, expected):
    """Explain exact supplied arithmetic and missing choices; no financial policy invention."""
    from apps.finance.fixed_charge import inputs, charge_access, route_for
    from apps.finance.models import CoverageFixedCharge
    case = lock_case(actor, case_id, 'agent.coverage', expected)
    charge = CoverageFixedCharge.objects.filter(pk=charge_id, assessment__terms__case=case).first()
    if not charge: raise ValidationError('Exact same-case fixed charge required')
    terms = charge_access(actor, charge, 'investigate')
    snapshot, result = inputs(actor, charge)
    route = route_for(actor,charge.request,assessment=charge.assessment)
    resumed = route.get('continuation')
    from apps.finance.models import BillingPreparation
    reusable = list(BillingPreparation.objects.filter(fixed_charge=charge,snapshot=snapshot,result=result).values_list('pk',flat=True))
    run = AgentRun.objects.create(case=case, actor=actor, evidence=charge.evidence,
        provider='deterministic-fixed-charge-v1', process_id='F31', result={
            'charge': charge.pk, 'snapshot': snapshot, 'preparation_preview': result,
            'work_route': {'recipient':route['recipient'].pk,'continuation':resumed.pk if resumed else None,'reusable_preparations':reusable},
            'citations': [{'id': e.pk, 'kind': e.kind, 'sha256': e.sha256}
                for e in [charge.evidence, terms.evidence, terms.contract.evidence, terms.register.evidence]],
            'questions': [{'question': 'Supply a corrected exact source-backed declaration: ' + f} for f in result['findings']],
            'next_work': 'The current authorised recipient reuses matching preparation where present. Continuation does not renew an approval or receipt. Existing configured Finance review and separate issuance remain required.',
            'approval_granted': False, 'invoice_issued': False, 'policy_changed': False})
    event(actor, case, 'agent.coverage_fixed_charge', run=run.pk); bump(case)
    return run
