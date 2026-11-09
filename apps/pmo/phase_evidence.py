"""P63 engineering checklist, not a gate schema or authority to change phases.

Only native currentness validators establish child coverage. Registry values are
metadata, never child payloads or exception text. No historical row is rewritten.
"""
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.utils import timezone
from apps.core.models import Case
from apps.core.read_observation import read_observation
from apps.identity.services import require
from . import delivery, delivery_closure as closure
from .models import Baseline, Decision, DeliveryRecord

QUESTIONS = ['Q05', 'Q06', 'Q12', 'Q16']


@read_observation
def projection(actor, case_id, dossier_id):
    case = Case.objects.get(pk=case_id)
    require(actor, case, 'case.read')
    require(actor, case, 'delivery.read')
    d = delivery.dossier_for(case, dossier_id, current=False)
    registry = {}
    phases = [{'name': name, 'processes': processes, 'checks': [], 'references': [],
               'entry': 'unknown', 'exit': 'unknown', 'source_questions': QUESTIONS[:],
               'transition_authorized': False}
              for name, processes in [('Initiation', 'P16–P20'), ('Planning', 'P21–P26'),
                                     ('Execution', 'P29–P33'), ('Closure', 'P35–P39')]]
    scope_current = True
    try:
        delivery.dossier_for(case, d.pk)
    except (ValidationError, PermissionDenied):
        scope_current = False

    def check(phase, key, title, authority, fn, *, permission=None):
        item = {'key': key, 'title': title, 'authority': authority,
                'status': 'unknown', 'references': [], 'business_outcome': 'not_inferred'}
        phase['checks'].append(item)
        try:
            if permission:
                require(actor, case, permission)
            if not scope_current:
                item['status'] = 'stale_scope'
                return
            rows = fn()
            # Collect atomically: failed validators must not leak partial references.
            refs = {}
            for row in rows:
                identity = f'{row._meta.label_lower}:{row.pk}'
                refs[identity] = {'type': row._meta.label_lower, 'id': row.pk,
                                  'record_identity': 'immutable_child', 'currentness': 'native_validator'}
                if row._meta.label_lower == 'core.evidence':
                    refs[identity].update(version=row.version, sha256=row.sha256)
            registry.update(refs)
            item.update(status='current', references=list(refs))
            phase['references'] = list(dict.fromkeys(phase['references'] + list(refs)))
        except PermissionDenied:
            item['status'] = 'restricted_or_authority_changed'
        except (ValidationError, ObjectDoesNotExist):
            item['status'] = 'unknown_or_stale'

    def baseline():
        from .services import baseline_approval_refs
        base = Baseline.objects.get(case=case)
        from .signatures import baseline_use, current_baseline_documents
        from .models import BaselineAdoption, CommercialDecision
        if BaselineAdoption.objects.filter(revision__dossier__case=case).exists():
            from .commercial import valid_approvals
            base, use = baseline_use(case)
            current_baseline_documents(case, base, use)
            ids = valid_approvals(use.adoption.revision)
            return [*CommercialDecision.objects.filter(pk__in=ids).order_by('pk'), base.plan, base.costing, base.sow]
        ids = baseline_approval_refs(case, base)
        return [*Decision.objects.filter(pk__in=ids).order_by('pk'), base.plan, base.costing, base.sow]

    def signatures():
        from .signatures import assert_current_signed_baseline
        return [assert_current_signed_baseline(case)]

    def signed_finance():
        from .signatures import baseline_use, assert_current_signed_baseline
        from apps.finance.models import SignedBaselineIntake
        assert_current_signed_baseline(case)
        base, use = baseline_use(case)
        if not use.adoption_id:
            raise ValidationError('No native signed-baseline intake link')
        receipt = SignedBaselineIntake.objects.get(case=case, adoption_id=use.adoption_id)
        expected = {name: {'id': getattr(base, name + '_id'),
                           'sha256': getattr(base, name).sha256} for name in ['plan', 'sow', 'signed']}
        if receipt.payload.get('sources') != expected or receipt.payload.get('adoption_id') != use.adoption_id:
            raise ValidationError('Exact signed-baseline receipt source mismatch')
        return [receipt]

    def engagement():
        from .engagement import current_assignment, current_capture
        assignment = current_assignment(case)
        capture = current_capture(case)
        require(capture.actor, case, 'engagement.capture')
        return [capture, assignment]

    def source(kind):
        return list(delivery.verified_source(d, kind))

    def gates(kind):
        # Model names are obtained from the native candidate relation, not a
        # generic approval flag. Verification checks exact source/version/grant.
        pins = delivery.verified_gates(d, [kind])
        gate = d.candidate.gates.get(pk=pins[0][0])
        return [gate, gate.verifications.get(pk=pins[0][1])]

    def release_evidence():
        values = delivery.readiness_inputs(d)
        rows = [DeliveryRecord.objects.get(pk=values['request_id'], dossier=d)]
        for gate_id, verification_id in values['glpi']:
            gate = d.candidate.gates.get(pk=gate_id)
            rows.extend([gate, gate.verifications.get(pk=verification_id)])
        return rows

    def closure_report():
        decision, binding = closure.current_closure_approval(d)
        return [decision, binding.version]

    initiation, planning, execution, closing = phases
    check(initiation, 'engagement', 'Engagement route and assignment', 'PMO', engagement, permission='engagement.read')
    check(initiation, 'costing', 'Costing and document decisions', 'Named costing and document owners', baseline, permission='costing.read')
    check(initiation, 'signatures', 'Explicit SOW and PRD signature facts', 'Client and PMO', signatures)
    # Finance acknowledgement is evidence of notifications, not payment/deposit.
    check(initiation, 'finance', 'Signed-baseline Finance receipt', 'Finance',
          signed_finance, permission='finance.read')
    for kind in delivery.PLANNING:
        check(planning, kind, kind.replace('_', ' ').capitalize(), delivery.SOURCE_OWNERS[kind],
              lambda kind=kind: source(kind), permission='planning.read' if kind == 'scope_baseline' else None)
    check(planning, 'plan', 'Exact Planning decision', 'PMO Lead', lambda: [delivery.approved_plan(d)])
    for kind in delivery.UPSTREAM_GATES:
        check(execution, kind, kind.replace('_', ' ').capitalize(), 'Source-owning team', lambda kind=kind: gates(kind))
    check(execution, 'glpi', 'Exact GLPI request and external decisions', 'GLPI / Security / CTO / CEO', release_evidence)
    check(execution, 'release', 'Actual release evidence', 'Infrastructure', lambda: [delivery.valid_release(d)])
    check(execution, 'go_live', 'Exact go-live report and signature attestation', 'PM and Client', lambda: [closure.accepted_go_live(d)])
    check(closing, 'stability', 'Current release stability', 'Source-owning teams', lambda: [closure.qualified_hypercare(d)])
    check(closing, 'archive', 'Current immutable archive index', 'PMO', lambda: [closure.current_archive(d)])
    check(closing, 'handover', 'Actual Support and Operations receipt', 'Support / Operations',
          lambda: list(DeliveryRecord.objects.filter(dossier=d, pk__in=closure.received_handover(d)).order_by('pk')))
    check(closing, 'finance', 'Finance notification coverage, not debt forgiveness', 'Finance',
          lambda: [closure.current_finance_confirmation(d)], permission='finance.read')
    check(closing, 'report', 'Current PM report and closure decision', 'Head of PMO', closure_report)
    for phase in phases:
        phase['coverage'] = {'current': sum(c['status'] == 'current' for c in phase['checks']),
                             'checked': len(phase['checks']), 'scope': 'bounded_native_child_evidence'}
        phase['child_evidence_current'] = all(c['status'] == 'current' for c in phase['checks'])
        phase['unknown'] = True  # Q05 entry/exit representation remains unresolved.
        phase['stale_or_unknown_child'] = any(c['status'] != 'current' for c in phase['checks'])
    return {'protocol': 'p63-phase-evidence/v1', 'as_of': timezone.now().isoformat(),
            'case_id': str(case.pk), 'dossier_id': d.pk, 'phases': phases, 'evidence_registry': registry,
            'source_questions': QUESTIONS[:], 'scope_current': scope_current,
            'coverage': 'Selected dossier and current native child records; not complete historical inventory',
            'rule_ambiguity': 'Q05: phase entry/exit and PMO sign-off representation remain unknown. Explicit signatures do not acquire a new commencement delay.',
            'financial_status': 'not_assessed', 'debt_waived': False, 'deployment_authorized': False,
            'phase_change_authorized': False, 'approval_tasks_created': False, 'effect_tools': [],
            'external_authenticity_verified': False}
