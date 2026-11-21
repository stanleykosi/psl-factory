"""Independently reviewed client identity links over exact workspace billing sources."""

import json
import re
from hashlib import sha256

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.finance.client_billing import current_coverages
from apps.identity.services import require

from .evidence_access import CLIENT_WORKSPACE_LINK_PROOF
from .models import ClientWorkspaceLink, Evidence
from .read_budget import ReadLimit, limit_queries
from .services import add_evidence, bump, event, lock_case


SCHEMA = 'psl/client-workspace-link/v1'
KEY = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}')


def current(case):
    return ClientWorkspaceLink.objects.filter(case=case).order_by('-number').first()


def authorise(actor, case, permission=None):
    from .client_contacts import authorize

    if case.kind != 'project':
        raise PermissionDenied('Client links belong to project workspaces.')
    try:
        with limit_queries(300):
            authorize(actor, case, 'billing')
    except ReadLimit as exc:
        raise PermissionDenied('The billing source needs a narrower reading scope before reviewing this link.') from exc
    if permission:
        require(actor, case, permission)


def group_key(tenant, issuer, reference):
    return sha256('\x1f'.join((tenant, issuer, reference)).encode('utf-8')).hexdigest()


def validate(case, value):
    fields = {'schema', 'case', 'previous', 'action'}
    if not isinstance(value, dict) or value.get('schema') != SCHEMA or value.get('case') != str(case.pk):
        raise ValidationError('Choose a recorded client link from this workspace.')
    previous = value.get('previous')
    if previous is not None and (type(previous) is not int or previous < 1):
        raise ValidationError('The preceding client link reference is invalid.')
    if value.get('action') == 'unlink' and set(value) == fields and previous:
        return None, '', ''
    if value.get('action') != 'link' or set(value) != fields | {'coverage', 'customer', 'issuer', 'reference', 'name'}:
        raise ValidationError('Use a complete client identity from the original customer record.')
    issuer, reference, name = value['issuer'], value['reference'], value['name']
    if not all(isinstance(key, str) and KEY.fullmatch(key) for key in (issuer, reference)):
        raise ValidationError('Enter the exact source and client reference from the original customer record.')
    if not isinstance(name, str) or not 1 <= len(name) <= 160 or name != name.strip() or not name.isprintable():
        raise ValidationError('Enter the name recorded on the customer record.')
    if type(value['coverage']) is not int:
        raise ValidationError('Choose current billing coverage from this workspace.')
    coverage = current_coverages(case).filter(pk=value['coverage']).first()
    if not coverage or value['customer'] != coverage.customer:
        raise ValidationError('The selected billing coverage has changed. Prepare a fresh client link.')
    return coverage, group_key(case.tenant, issuer, reference), name


def facts_from(source):
    if not source or not 0 < len(source.body) <= 4096 or sha256(source.body.encode()).hexdigest() != source.sha256:
        raise ValidationError('Choose the original client link evidence from this workspace.')
    try:
        return json.loads(source.body)
    except (ValueError, TypeError) as exc:
        raise ValidationError('The selected evidence is missing the client identity facts.') from exc


@transaction.atomic
def propose(actor, case, expected, *, action, coverage_id=None, issuer='', reference='', name='', source):
    case = lock_case(actor, case.pk, 'finance.billing.register', expected)
    authorise(actor, case, 'evidence.add')
    previous = current(case)
    value = {'schema': SCHEMA, 'case': str(case.pk), 'action': action, 'previous': previous.pk if previous else None}
    if action == 'link':
        coverage = current_coverages(case).filter(pk=coverage_id).first() if type(coverage_id) is int else None
        if not coverage:
            raise ValidationError('Choose current billing coverage from this workspace.')
        value.update(coverage=coverage.pk, customer=coverage.customer, issuer=issuer, reference=reference, name=name)
    if action == 'unlink' and not (previous and previous.coverage_id):
        raise ValidationError('There is no current client link to remove.')
    validate(case, value)
    return add_evidence(actor, case.pk, CLIENT_WORKSPACE_LINK_PROOF, json.dumps(value, ensure_ascii=False),
                        source, case.revision)


@transaction.atomic
def confirm(actor, case, expected, evidence_id):
    case = lock_case(actor, case.pk, 'policy.activate', expected)
    authorise(actor, case)
    evidence = Evidence.objects.filter(case=case, pk=evidence_id, kind=CLIENT_WORKSPACE_LINK_PROOF).select_related('created_by').first()
    facts = facts_from(evidence)
    if evidence.created_by_id == actor.pk:
        raise PermissionDenied('A different authorised person must review this client link.')
    authorise(evidence.created_by, case, 'finance.billing.register')
    previous = current(case)
    if previous and previous.evidence_id == evidence.pk:
        return previous
    coverage, key, name = validate(case, facts)
    if facts['previous'] != (previous.pk if previous else None):
        raise ValidationError('The client link changed. Prepare a new decision against its current record.')
    if not coverage and not (previous and previous.coverage_id):
        raise ValidationError('There is no current client link to remove.')
    record = ClientWorkspaceLink.objects.create(
        case=case, tenant=case.tenant, coverage=coverage, number=previous.number + 1 if previous else 1,
        previous=previous, group_key=key, client_label=name, evidence=evidence, reviewer=actor,
    )
    event(actor, case, 'client.workspace_link_reviewed', link=record.pk, linked=bool(coverage),
          previous=previous.pk if previous else None)
    bump(case)
    return record
