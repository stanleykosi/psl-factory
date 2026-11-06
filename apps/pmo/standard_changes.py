"""Recorded human preapprovals, never authority inferred from catalogue text."""
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.services import lock_case, event, bump
from apps.identity.services import require
from apps.policy.services import require_operation, reference_values, decision_authority
from apps.policy.change_validators import REUSABLE_ROLES
from .models import StandardPreapproval, StandardBinding
from .commercial import note_required
from .services import subject


def catalogue(case):
    configs = require_operation('change.preapproval_evaluate', case)
    policies = {r.component: r.configuration.pk for r in configs}
    values = {r.component: reference_values(r.configuration) for r in configs}
    entries = values['D01.change_type_catalogue']
    if len({e['key'] for e in entries}) != len(entries):
        raise ValidationError('Duplicate Standard catalogue keys')
    return {e['key']: e for e in entries}, values['D01.satisfied_gate_map'][0].get('standard',[]), policies


def entry_policy(case, key):
    entries, gates, policies = catalogue(case)
    matches = [g['roles'] for g in gates if g['catalogue_key'] == key]
    if key not in entries or len(matches) != 1:
        raise ValidationError('Select a configured Standard entry with one explicit satisfied-gate mapping')
    return entries[key], matches[0], policies


@transaction.atomic
def preapprove(actor, case_id, key, role, verdict, evidence_id, note, expected):
    case = lock_case(actor, case_id, 'change.preapprove', expected)
    if case.kind != 'project':
        raise ValidationError('Standard catalogue approval belongs to a project')
    _, roles, policies = entry_policy(case, key)
    if role not in REUSABLE_ROLES or role not in roles or verdict not in ['approve', 'return', 'reject']:
        raise ValidationError('Choose a mapped human preapproval role and explicit verdict')
    note_required(note)
    authority = decision_authority(actor, case, role, verdict)
    record = StandardPreapproval.objects.create(case=case, catalogue_key=key, policies=policies,
        role=role, verdict=verdict, authority=authority, actor=actor,
        evidence=subject(case, evidence_id, 'change_preapproval'), note=note)
    event(actor, case, 'change.standard_preapproval', preapproval=record.pk, role=role, verdict=verdict, policies=policies)
    bump(case)
    return record


@transaction.atomic
def bind_standard(actor, case_id, version_id, key, evidence_id, note, expected):
    from .changes import current_change, require_open_version
    case = lock_case(actor, case_id, 'change.manage', expected)
    version = current_change(case, version_id)
    require_open_version(version)
    if version.category != 'Standard':
        raise ValidationError('Catalogue procedure matching applies only to Standard changes')
    authority = decision_authority(actor, case, 'PM')
    entry, _, policies = entry_policy(case, key)
    if version.module != entry['module']:
        raise ValidationError('Affected module does not match the exact catalogue procedure')
    note_required(note)
    # PM attests exact procedure applicability; no model/text matcher can grant this.
    record = StandardBinding.objects.create(version=version, catalogue_key=key, policies=policies, authority=authority,
        evidence=subject(case, evidence_id, 'change_procedure_match'), note=note, actor=actor)
    event(actor, case, 'change.standard_bound', binding=record.pk, version=version.pk, policies=policies)
    bump(case)
    return record


def evaluate_standard(case, version, flags):
    binding = version.standard_bindings.order_by('-pk').first()
    if not binding:
        raise ValidationError('PM must record exact Standard procedure applicability')
    entry, roles, policies = entry_policy(case, binding.catalogue_key)
    require(binding.actor, case, 'change.manage')
    if decision_authority(binding.actor, case, 'PM') != binding.authority:
        raise ValidationError('Procedure match PM authority changed; record a new applicability attestation')
    if binding.policies != policies or version.module != entry['module'] or flags != entry['expected_impact']:
        raise ValidationError('Standard conditions or policy changed; reassess and record a fresh procedure match')
    approvals = []
    for role in roles:
        latest = StandardPreapproval.objects.filter(case=case, catalogue_key=binding.catalogue_key,
            policies=policies, role=role).order_by('-pk').first()
        if not latest or latest.verdict != 'approve':
            raise ValidationError('Current human catalogue preapproval required: ' + role)
        require(latest.actor, case, 'change.preapprove')
        if decision_authority(latest.actor, case, role) != latest.authority:
            raise ValidationError('Standard preapproval authority changed; obtain a new decision')
        approvals.append(latest.pk)
    return roles, {'binding_id': binding.pk, 'policies': policies,
        'preapproval_ids': approvals, 'procedure_evidence_id': entry['procedure_evidence_id'],
        'procedure_sha256': entry['procedure_sha256']}


def preapproval_snapshot(case, version, flags):
    return evaluate_standard(case, version, flags)[1] if version.category == 'Standard' else {}


def validate_snapshot(case, authorization, flags):
    if authorization.preapproval_snapshot != preapproval_snapshot(case, authorization.version, flags):
        raise ValidationError('Standard preapproval snapshot changed; authorize a new change revision')
