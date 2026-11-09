"""Optional native object observations, never Finance verification or approval."""
from dataclasses import asdict
import hashlib
import hmac
import json
import os
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction, connection
from django.db.models import Max
from django.utils import timezone
from apps.core.models import Evidence, Audit, Case
from apps.core.services import event, bump
from apps.documents.contracts import digest
from adapters.quickbooks_online import ReadIntent, read, validate_binding
from . import ledger

INTENT = 'qbo_native_intent'
OBSERVATION = 'qbo_native_observation'
PREFIX = 'ledger.qbo.'


def registry():
    return getattr(settings, 'QUICKBOOKS_READS', {})


def binding(alias):
    value = registry().get(alias)
    try:
        validate_binding(value, settings.READINESS_SECRET_REFS)
        if not value['enabled']:
            raise ValueError()
    except (ValueError, TypeError, KeyError):
        raise ValidationError('Enabled reviewed QBO read binding required') from None
    return value


def credential_pin(value):
    credential = settings.READINESS_SECRET_REFS[value['credential_ref']]
    secret = os.getenv(credential['env'])
    if not isinstance(secret, str) or not 0 < len(secret) <= 4096 or not all(32 < ord(c) < 127 for c in secret):
        raise ValidationError('QBO credential reference unavailable')
    return hmac.new(settings.SECRET_KEY.encode(), secret.encode(), hashlib.sha256).hexdigest()


def append(actor, case, kind, payload):
    body = json.dumps(payload, sort_keys=True)
    version = (case.evidence.filter(kind=kind).aggregate(v=Max('version'))['v'] or 0) + 1
    evidence = Evidence.objects.create(case=case, kind=kind, version=version, body=body,
        source='native:qbo-read/v1', sha256=hashlib.sha256(body.encode()).hexdigest(), created_by=actor)
    event(actor, case, PREFIX + kind, evidence=evidence.pk, sha256=evidence.sha256)
    return evidence


def authentic(case, pk, kind):
    evidence = Evidence.objects.filter(case=case, pk=pk, kind=kind, source='native:qbo-read/v1').first()
    if not evidence or hashlib.sha256(evidence.body.encode()).hexdigest() != evidence.sha256 or not Audit.objects.filter(
            case=case, actor=evidence.created_by, action=PREFIX + kind,
            data__evidence=evidence.pk, data__sha256=evidence.sha256).exists():
        raise ValidationError('Service-authenticated native read record required')
    return evidence, json.loads(evidence.body)


def scope(actor, case_id, lineage_id, alias, expected=None):
    case = ledger.locked(actor, case_id, 'ledger.verify', expected)
    lineage = ledger.exact(case, lineage_id)
    policy, rules = ledger.context(lineage)
    value = binding(alias)
    if not ledger.is_head(lineage) or ledger.target_conflict(lineage):
        raise ValidationError('Current nonconflicting source target required')
    source = lineage.payload
    if source['provider'] != 'quickbooks' or source['realm'] != value['realm'] or source['entity'] != value['entity'] or not source['target_reference']:
        raise ValidationError('Explicit exact QBO realm/entity/target mapping required')
    intent = ReadIntent.create(str(case.pk), str(lineage.pk), value, source['target_reference'], settings.READINESS_SECRET_REFS)
    pins = {'lineage': lineage.pk, 'source_sha256': lineage.evidence.sha256,
            'source_payload': digest(source), 'policy': policy.pk, 'alias': alias,
            'credential_binding': credential_pin(value), 'intent': asdict(intent),
            'max_age_seconds': rules['max_age_seconds']}
    return case, lineage, value, pins


@transaction.atomic
def reserve(actor, case_id, lineage_id, alias, expected=None):
    case, _, _, pins = scope(actor, case_id, lineage_id, alias, expected)
    payload = dict(pins, actor=actor.pk, reserved_at=timezone.now().isoformat())
    record = append(actor, case, INTENT, payload)
    bump(case)
    return record


@transaction.atomic
def claim(actor, case_id, intent_id, expected=None):
    case = ledger.locked(actor, case_id, 'ledger.verify', expected)
    record, payload = authentic(case, intent_id, INTENT)
    if record.created_by_id != actor.pk:
        raise ValidationError('Original read principal required')
    _, _, value, pins = scope(actor, case_id, payload['lineage'], payload['alias'])
    if any(payload[k] != v for k, v in pins.items()):
        raise ValidationError('Native read context changed; reserve a new read')
    if (timezone.now() - record.created_at).total_seconds() > payload['max_age_seconds']:
        raise ValidationError('Read intent expired; reserve a new read')
    if Audit.objects.filter(case=case, action=PREFIX+'started', data__intent=intent_id).exists():
        raise ValidationError('Read already attempted; inspect outcome or reserve a new read')
    # Serialise company-level throttle decisions, including different cases.
    realm_key = digest({'environment': value['environment'], 'realm': value['realm']})
    ledger.identity_lock(realm_key)
    latest = Audit.objects.filter(action=PREFIX+'throttled', data__realm=realm_key).order_by('-created_at').first()
    if latest and (timezone.now() - latest.created_at).total_seconds() < 60:
        raise ValidationError('QBO throttled; wait at least 60 seconds before another read')
    event(actor, case, PREFIX+'started', intent=intent_id)
    bump(case)
    return payload, value


@transaction.atomic
def record(actor, case_id, intent_id, payload, observation):
    # Retain the bounded remote fact even if permission/context was revoked in flight.
    # No adjudication/link is granted; all readers still require current ledger access.
    ledger.scope_lock(case_id)
    case = Case.objects.select_for_update().get(pk=case_id)
    evidence, stored = authentic(case, intent_id, INTENT)
    if stored != payload or evidence.created_by_id != actor.pk or observation.intent != ReadIntent(**payload['intent']):
        raise ValidationError('Exact reserved native read required')
    if not Audit.objects.filter(case=case, actor=actor, action=PREFIX+'started', data__intent=intent_id).exists():
        raise ValidationError('Claimed native attempt required')
    if Audit.objects.filter(case=case, action=PREFIX+'completed', data__intent=intent_id).exists():
        raise ValidationError('Native read outcome already recorded')
    linked = False
    try:
        _, _, value, pins = scope(actor, case_id, payload['lineage'], payload['alias'])
        linked = (all(payload[k] == v for k, v in pins.items()) and
                  0 <= (timezone.now() - evidence.created_at).total_seconds() <= payload['max_age_seconds'])
    except (ValidationError, PermissionDenied, ValueError, KeyError):
        pass
    value = json.loads(payload['intent']['binding_json'])
    result = append(actor, case, OBSERVATION, {'intent_id': intent_id, 'observation': asdict(observation),
                                            'business_verification': False, 'link_status': 'current_at_capture' if linked else 'stale_or_access_changed'})
    event(actor, case, PREFIX+'completed', intent=intent_id, evidence=result.pk)
    if observation.status == 'throttled':
        event(actor, case, PREFIX+'throttled', realm=digest({'environment':value['environment'], 'realm':value['realm']}))
    bump(case)
    return result


def execute(actor, case_id, intent_id, expected=None):
    # A savepoint is not a durable claim: rollback must never permit a read replay.
    if connection.in_atomic_block or not connection.get_autocommit():
        raise ValidationError('Native QBO execution requires an outer autocommit boundary')
    # No caller-supplied response, transport or token enters this application boundary.
    payload, value = claim(actor, case_id, intent_id, expected)
    secret = os.getenv(settings.READINESS_SECRET_REFS[value['credential_ref']]['env'])
    if not isinstance(secret, str) or not hmac.compare_digest(
            hmac.new(settings.SECRET_KEY.encode(), secret.encode(), hashlib.sha256).hexdigest(),
            payload['credential_binding']):
        raise ValidationError('Credential changed; reserve a new read')
    observation = read(ReadIntent(**payload['intent']), value, settings.READINESS_SECRET_REFS, lambda _: secret)
    return record(actor, case_id, intent_id, payload, observation)


def visible(actor, case):
    ledger.readable(actor, case)
    rows = []
    for evidence in case.evidence.filter(kind__in=[INTENT, OBSERVATION]).order_by('-pk')[:40]:
        try:
            _, payload = authentic(case, evidence.pk, evidence.kind)
        except ValidationError:
            continue
        if evidence.kind == INTENT:
            started = Audit.objects.filter(case=case, action=PREFIX+'started', data__intent=evidence.pk).exists()
            done = Audit.objects.filter(case=case, action=PREFIX+'completed', data__intent=evidence.pk).exists()
            status = 'completed' if done else 'unknown or in progress; never replay automatically' if started else 'reserved'
        else:
            status = payload['observation']['status'] + ' / ' + payload['link_status'] + ' / not Finance verification'
        rows.append({'id':evidence.pk, 'kind':evidence.kind, 'status':status, 'created_at':evidence.created_at})
    return rows
