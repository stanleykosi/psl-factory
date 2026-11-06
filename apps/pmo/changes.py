from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.services import lock_case, event, bump
from apps.documents.controlled import baseline_manifest
from apps.policy.services import decision_authority
from .models import ChangeRequest, ChangeVersion, ChangeAssessment, ChangeDecision, ChangeAuthorization, ChangeClosure
from .services import subject

CONTRIBUTORS = ['Engineering', 'QA', 'Infra', 'Security']
DECISION_ROLES = ['Product', 'Engineering', 'Client', 'Engineering Lead', 'Security Manager']


def require_open_version(version):
    if ChangeClosure.objects.filter(authorization__version=version).exists():
        raise ValidationError('Closed change history is immutable; log a new revision')


def current_change(case, pk, adopted_manifest=None):
    v = ChangeVersion.objects.select_related('change__case').filter(pk=pk, change__case=case).first()
    if not v or v.change.current_id != v.pk or (v.base_manifest != baseline_manifest(case) and adopted_manifest != baseline_manifest(case)):
        raise ValidationError('Select a current change revision bound to the active baseline')
    return v


@transaction.atomic
def log_change(actor, case_id, reference, category, module, description, reason, evidence_id, expected, incident_id=None):
    from .commercial import note_required
    case = lock_case(actor, case_id, 'change.manage', expected)
    from apps.policy.services import role_policy
    role_policy(actor, case, 'PM')  # Classification ownership, not an approval.
    if case.kind != 'project' or category not in ['Standard', 'Normal', 'Emergency'] or not reference.strip() or len(reference)>160 or not module.strip() or len(module)>160:
        raise ValidationError('A project, unique reference, affected module and exact change category are required')
    note_required(description); note_required(reason)
    evidence = subject(case, evidence_id, 'change_request')
    incident = subject(case, incident_id, 'incident') if incident_id else None
    if category == 'Emergency' and not incident:
        raise ValidationError('Emergency intake requires the external incident evidence reference')
    change, _ = ChangeRequest.objects.get_or_create(case=case, reference=reference)
    version = ChangeVersion.objects.create(change=change, number=change.versions.count()+1, category=category, module=module,
        description=description, reason=reason, evidence=evidence, incident=incident, base_manifest=baseline_manifest(case), actor=actor)
    change.current = version; change.save(update_fields=['current'])
    event(actor, case, 'change.logged', change=change.pk, version=version.pk, category=category)
    bump(case)
    return version


@transaction.atomic
def assess_change(actor, case_id, version_id, contributor, cost_impact, timeline_impact, client_facing, evidence_id, note, expected, *, outputs=None, production_impact=None, scope_items=None):
    from .commercial import note_required
    case = lock_case(actor, case_id, 'change.assess:'+contributor, expected)
    version = current_change(case, version_id)
    require_open_version(version)
    if contributor not in CONTRIBUTORS or any(v is not None and type(v) is not bool for v in [cost_impact, timeline_impact, client_facing]):
        raise ValidationError('Use an explicit contributor and true/false/unknown impact values')
    note_required(note)
    from .change_impacts import assessment_details
    details = assessment_details(version, contributor, outputs, production_impact, scope_items)
    result = ChangeAssessment.objects.create(impact_details=details, version=version, contributor=contributor, cost_impact=cost_impact,
        timeline_impact=timeline_impact, client_facing=client_facing, evidence=subject(case,evidence_id), note=note, actor=actor)
    event(actor, case, 'change.assessed', assessment=result.pk, version=version.pk, contributor=contributor)
    bump(case)
    return result


def impact(version):
    latest = {}
    for a in version.assessments.order_by('pk'): latest[a.contributor] = a
    if set(latest) != set(CONTRIBUTORS): raise ValidationError('Engineering, QA, Infra and Security assessments required')
    values = [latest[r] for r in CONTRIBUTORS]
    if version.category == 'Normal':
        from .change_impacts import validate_assessments
        validate_assessments(version, latest)
    if any(getattr(a, k) is None for a in values for k in ['cost_impact', 'timeline_impact', 'client_facing']):
        raise ValidationError('Impact remains unknown; obtain the contributing owner clarification')
    flags = {k:any(getattr(a,k) for a in values) for k in ['cost_impact', 'timeline_impact', 'client_facing']}
    return [a.pk for a in values], flags


def required_roles(flags):
    return ['Product','Engineering'] + (['Client'] if flags['client_facing'] else []) + (['Engineering Lead','Security Manager'] if flags['timeline_impact'] else [])


@transaction.atomic
def decide_change(actor, case_id, version_id, role, verdict, evidence_id, note, expected):
    from .commercial import note_required
    case = lock_case(actor, case_id, 'change.decide', expected)
    version = current_change(case, version_id)
    require_open_version(version)
    if role not in DECISION_ROLES or verdict not in ['approve', 'return', 'reject']:
        raise ValidationError('Choose a source-prescribed change role and decision')
    note_required(note)
    ids, _ = impact(version)
    authority = decision_authority(actor, case, role, verdict)
    decision = ChangeDecision.objects.create(version=version, role=role, verdict=verdict, assessment_ids=ids,
        authority=authority, evidence=subject(case,evidence_id), note=note, actor=actor)
    event(actor, case, 'change.decision', decision=decision.pk, version=version.pk)
    bump(case)
    return decision


def authorization_inputs(case, version, adopted_manifest=None, *, check_authority=True):
    current_change(case, version.pk, adopted_manifest)
    if version.category == 'Emergency':
        raise ValidationError('Use Emergency preauthorization/retrospective services; this ordinary scope/cost authorization does not grant the emergency exception')
    ids, flags = impact(version)
    covered = []
    if version.category == 'Standard':
        from .standard_changes import evaluate_standard
        covered, _ = evaluate_standard(case,version,flags)
    latest = {}
    for d in version.decisions.order_by('pk'): latest[d.role] = d
    decision_ids = []
    for role in required_roles(flags):
        # A specific change decision takes precedence over reusable preapproval.
        # Returning/rejecting this request cannot be bypassed by its catalogue.
        if role in covered and role not in latest:
            continue
        d = latest.get(role)
        if not d or d.verdict != 'approve' or d.assessment_ids != ids:
            raise ValidationError('Current assessment-bound decision required: '+role)
        from apps.identity.services import require
        if check_authority:
            require(d.actor, case, 'change.decide')
            if decision_authority(d.actor,case,d.role,d.verdict) != d.authority:
                raise ValidationError('Change decision authority changed')
        decision_ids.append(d.pk)
    return ids, flags, decision_ids


@transaction.atomic
def authorize_change(actor, case_id, version_id, commercial_id, expected):
    from .commercial import current_revision, valid_approvals, terminal
    case = lock_case(actor, case_id, 'change.authorize', expected)
    version = current_change(case, version_id)
    require_open_version(version)
    ids, flags, decisions = authorization_inputs(case, version)
    commercial = current_revision(case, commercial_id) if commercial_id else None
    if flags['cost_impact'] and not commercial:
        raise ValidationError('Cost impact requires a current approved commercial revision')
    if commercial:
        if commercial.context_id != version.evidence_id or terminal(commercial):
            raise ValidationError('Commercial revision must explicitly cite this change request')
        valid_approvals(commercial)
    if ChangeAuthorization.objects.filter(version=version, commercial=commercial).exists():
        raise ValidationError('Authorization already recorded; changes need a new revision')
    from .standard_changes import preapproval_snapshot
    result = ChangeAuthorization.objects.create(version=version, commercial=commercial, assessment_ids=ids, decision_ids=decisions,
        preapproval_snapshot=preapproval_snapshot(case,version,flags), actor=actor)
    event(actor, case, 'change.authorized', authorization=result.pk, version=version.pk, commercial=commercial_id)
    bump(case)
    return result


def require_change_for_adoption(case, revision):
    authorization = ChangeAuthorization.objects.select_related('version').filter(commercial=revision).first()
    if not authorization:
        raise ValidationError('Signed-baseline replacement requires a linked controlled change authorization')
    ids, flags, decisions = authorization_inputs(case, authorization.version)
    from .standard_changes import validate_snapshot
    validate_snapshot(case,authorization,flags)
    if ids != authorization.assessment_ids or decisions != authorization.decision_ids:
        raise ValidationError('Change evidence/decisions changed; obtain a new change revision and authorization')
    return authorization
