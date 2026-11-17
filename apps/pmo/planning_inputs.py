"""Received department facts and exact human reassessment of changed effort."""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.services import bump, event
from apps.core.models import Audit
from apps.identity.services import require
from apps.policy.services import decision_authority
from . import planning
from .models import CommercialCase, CostingBinding, PlanningDepartmentInput
from .planning_input_models import DEPARTMENTS


def heads(case, packet):
    return list(PlanningDepartmentInput.objects.filter(case=case, packet=packet)
                .order_by('department', '-version').distinct('department').select_related('source', 'previous', 'actor').defer('source__body'))


def pin(row):
    return {'id': row.pk, 'department': row.department, 'version': row.version, 'source': row.source_id,
            'source_hash': row.source.sha256, 'effort_state': row.effort_state,
            'person_days': str(row.person_days) if row.person_days is not None else None}


def changed(row):
    return bool(row.previous_id and (row.effort_state, row.person_days) !=
                (row.previous.effort_state, row.previous.person_days))


@transaction.atomic
def record(actor, case_id, packet_id, department, previous_id, source_id, source_party,
           received_at, summary, effort_state, person_days, expected):
    case = planning.locked(actor, case_id, 'coordinate')
    if case.revision != expected:
        raise ValidationError('Stale revision; refresh before retrying')
    packet, value = planning.packet(case, packet_id)
    if not value['payload'].get('collect_department_inputs'):
        raise ValidationError('Enable department input collection in a new planning packet first.')
    if department not in DEPARTMENTS:
        raise ValidationError('Choose a delivery department.')
    old = PlanningDepartmentInput.objects.filter(packet=packet, department=department).order_by('-version').first()
    if (old.pk if old else None) != previous_id:
        raise ValidationError('The department input changed. Review its current version.')
    source = planning.proof(case, source_id)
    if not isinstance(source_party, str) or not source_party.strip() or len(source_party) > 160:
        raise ValidationError('Record who supplied the department input.')
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 4000:
        raise ValidationError('Describe the received input in at most 4,000 characters.')
    if not received_at or timezone.is_naive(received_at) or received_at > timezone.now():
        raise ValidationError('Use the actual receipt time, up to now.')
    try:
        days = Decimal(str(person_days)) if person_days is not None else None
    except InvalidOperation as exc:
        raise ValidationError('Use a finite person-day amount.') from exc
    if effort_state not in ['known', 'unknown', 'not_applicable'] or (days is not None) != (effort_state == 'known'):
        raise ValidationError('Choose known effort with an amount, unknown, or not applicable.')
    if days is not None and (not days.is_finite() or days < 0 or days > Decimal('999999999.999') or days != days.quantize(Decimal('.001'))):
        raise ValidationError('Use nonnegative person-days with at most three decimal places.')
    row = PlanningDepartmentInput.objects.create(case=case, packet=packet, department=department,
        previous=old, version=old.version + 1 if old else 1, source=source, source_party=source_party.strip(),
        received_at=received_at, summary=summary.strip(), effort_state=effort_state, person_days=days, actor=actor)
    event(actor, case, 'planning.department_input_recorded', input_id=row.pk, packet_id=packet.pk,
          department=department, source_id=source.pk, approval_granted=False)
    bump(case)
    return row


def current_context(case, packet, rows, configuration, rules):
    for row in rows:
        if not Audit.objects.filter(case=case,actor=row.actor,action='planning.department_input_recorded',
            data={'input_id':row.pk,'packet_id':packet.pk,'department':row.department,'source_id':row.source_id,'approval_granted':False}).exists():
            raise ValidationError('The department input needs its native recording provenance.')
        planning.readable(row.actor, case)
        require(row.actor, case, 'planning.coordinate')
        planning.proof(case, row.source_id)
        authorities = []
        for role in rules['recorder_roles']:
            try:
                authorities.append(decision_authority(row.actor, case, role))
            except (ValidationError, PermissionDenied):
                continue
        if not authorities:
            raise ValidationError('Review current recording authority for ' + row.department + '.')
    return {'packet_id': packet.pk, 'packet_hash': packet.sha256, 'policy_id': configuration.pk,
            'inputs': [pin(row) for row in rows]}


def commercial_context(case, rows, disposition):
    if disposition not in ['retain_costing', 'new_costing']:
        raise ValidationError('Record whether a new costing was required.')
    dossier = CommercialCase.objects.filter(case=case).select_related('current').first()
    proposal = dossier.current if dossier else None
    if disposition == 'retain_costing':
        return {'proposal': proposal.pk if proposal else None, 'costing': proposal.sources['costing'] if proposal else None}
    if not proposal:
        raise ValidationError('Prepare and approve a fresh commercial proposal for the changed effort.')
    from . import commercial, costing
    commercial.current_revision(case, proposal.pk)
    approvals = commercial.valid_approvals(proposal)
    binding = CostingBinding.objects.filter(costing_id=proposal.sources['costing'], run__case=case).select_related('run').first()
    changed_at = max(row.created_at for row in rows if changed(row))
    if not binding or binding.run.created_at < changed_at or proposal.created_at < changed_at:
        raise ValidationError('Use costing and a proposal prepared after the changed department input.')
    if proposal.decisions.filter(pk__in=approvals, inherited__isnull=False).exists():
        raise ValidationError('The changed-effort proposal requires fresh direct commercial decisions.')
    costing.current_run(binding.run)
    return {'proposal': proposal.pk, 'costing': binding.costing_id, 'run': binding.run_id, 'approvals': approvals}


def required(case, packet, reader):
    planning.readable(reader, case)
    _, value = planning.packet(case, packet.pk)
    if not value['payload'].get('collect_department_inputs'):
        return None
    configuration, criteria = planning.criteria(case)
    rules = criteria.get('department_inputs')
    if rules is None:
        raise ValidationError('owner_needed: Review department input requirements and changed-effort handling.')
    rows = heads(case, packet)
    names = {row.department for row in rows}
    missing = set(rules['required_departments']) - names
    if missing:
        raise ValidationError('Department inputs still needed: ' + ', '.join(sorted(missing)))
    if any(row.department in rules['effort_required_for'] and row.effort_state != 'known' for row in rows):
        raise ValidationError('Required department effort is still unknown or not applicable.')
    context = current_context(case, packet, rows, configuration, rules)
    if any(changed(row) for row in rows):
        item = planning.latest(case, 'department_review')
        if item is None:
            raise ValidationError('Review the changed effort against these exact department inputs.')
        value = planning.read(case, item, 'department_review', 'coordinate')
        if value.get('context') != context:
            raise ValidationError('Review the changed effort against these exact department inputs.')
        role = value.get('role')
        if role not in rules['reviewer_roles'] or (not rules['allow_recorder_review'] and any(row.actor_id == item.created_by_id for row in rows)):
            raise ValidationError('Current independent department input reviewer required.')
        if value.get('authority') != decision_authority(item.created_by, case, role):
            raise ValidationError('Department input review authority changed.')
        if rules['changed_effort_action'] == 'fresh_costing_required' and value.get('disposition') != 'new_costing':
            raise ValidationError('The configured changed-effort rule requires fresh costing.')
        if value.get('commercial') != commercial_context(case, rows, value.get('disposition')):
            raise ValidationError('The reviewed costing or commercial proposal changed.')
        require(item.created_by, case, 'commercial.read')
        require(item.created_by, case, 'costing.read')
        require(item.created_by, case, 'costing.source.read')
        planning.proof(case, value.get('evidence_id'))
        context['review_id'] = item.pk
    return context


@transaction.atomic
def review(actor, case_id, packet_id, role, disposition, evidence_id, reason, expected):
    case = planning.locked(actor, case_id, 'coordinate')
    if case.revision != expected:
        raise ValidationError('Stale revision; refresh before retrying')
    for action in ['commercial.read', 'costing.read', 'costing.source.read']:
        require(actor, case, action)
    packet, _ = planning.packet(case, packet_id)
    configuration, criteria = planning.criteria(case)
    rules = criteria.get('department_inputs')
    if rules is None or role not in rules['reviewer_roles']:
        raise ValidationError('Choose a configured department input reviewer role.')
    rows = heads(case, packet)
    if not any(changed(row) for row in rows):
        raise ValidationError('No changed effort needs this review.')
    if not rules['allow_recorder_review'] and any(row.actor_id == actor.pk for row in rows):
        raise PermissionDenied('A separate department input reviewer is required.')
    if rules['changed_effort_action'] == 'fresh_costing_required' and disposition != 'new_costing':
        raise ValidationError('The configured rule requires fresh costing and commercial decisions.')
    if not reason.strip() or len(reason) > 2000:
        raise ValidationError('Record the reason for this effort and costing decision.')
    proof = planning.proof(case, evidence_id)
    value = {'context': current_context(case, packet, rows, configuration, rules), 'role': role,
             'authority': decision_authority(actor, case, role), 'disposition': disposition,
             'commercial': commercial_context(case, rows, disposition), 'evidence_id': proof.pk, 'reason': reason.strip()}
    return planning.write(actor, case, 'department_review', value)


def projection(actor, case, packet):
    planning.readable(actor, case)
    _, value = planning.packet(case, packet.pk)
    if not value['payload'].get('collect_department_inputs'):
        return None
    rows = heads(case, packet)
    try:
        context = required(case, packet, actor)
        finding = 'Current received inputs meet the configured collection checks.'
    except (ValidationError, PermissionDenied) as exc:
        context = None
        finding = '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'Department input authority needs review.'
    records = {row.department: {**pin(row), 'source_party': row.source_party, 'received_at': row.received_at.isoformat(),
        'received_at_display': timezone.localtime(row.received_at).strftime('%d %b %Y, %H:%M %Z'),
        'source_version': row.source.version,
        'summary': row.summary, 'actor': row.actor.get_full_name() or row.actor.username,
        'changed_effort': changed(row)} for row in rows}
    return {'rows': [{'department': department, 'record': records.get(department)} for department in DEPARTMENTS],
            'finding': finding, 'context': context, 'changed': any(changed(row) for row in rows),
            'effort_reviewed':bool(context and context.get('review_id'))}
