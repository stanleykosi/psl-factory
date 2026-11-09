"""Evidenced declarations about one exact supplied input. Never conversion policy."""
import hashlib
import json
import re
from django.core.exceptions import ValidationError
from apps.pmo.services import subject

SCHEMA = 'finance-source-units/v1'
ASSERTION = 'finance-source-unit-assertion/v1'
UNITS = {'major_currency', 'thousands_currency', 'unknown'}


def evidence_identity(batch_id, input_key, feed):
    # Canonical JSON tuple retains delimiters without ambiguous concatenation.
    return 'source-unit:' + json.dumps([batch_id, input_key, feed])


def capture(batch, value):
    if value is None:
        value = {'schema': SCHEMA, 'batch': {'id': batch.pk, 'sha256': batch.source_sha256},
                 'input_key': None, 'declarations': []}
    if not isinstance(value, dict) or set(value) != {'schema', 'batch', 'input_key', 'declarations'}:
        raise ValidationError('Exact typed source-unit envelope required')
    if value['schema'] != SCHEMA or value['batch'] != {'id': batch.pk, 'sha256': batch.source_sha256} or type(value['batch'].get('id')) is not int:
        raise ValidationError('Source-unit declaration must pin this exact import and hash')
    rows = value['declarations']
    if not isinstance(rows, list) or len(rows) > 20:
        raise ValidationError('Supply at most 20 evidenced feed declarations')
    key = value['input_key']
    if (rows and (not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}', key))) or (not rows and key is not None):
        raise ValidationError('Explicit same-input linkage required; no linkage inferred from amounts')
    feeds = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'feed', 'unit', 'evidence'}:
            raise ValidationError('Exact feed, unit and evidence pin required')
        if not isinstance(row['feed'], str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}', row['feed']) or row['feed'] in feeds or not isinstance(row['unit'], str) or row['unit'] not in UNITS:
            raise ValidationError('Distinct bounded feed identities and explicit supported unit labels required')
        feeds.add(row['feed'])
        pin = row['evidence']
        if not isinstance(pin, dict) or set(pin) != {'id', 'version', 'sha256'} or type(pin['id']) is not int or type(pin['version']) is not int:
            raise ValidationError('Exact evidence id/version/hash required')
        evidence = subject(batch.case, pin['id'], 'finance_source_unit')
        identity = evidence_identity(batch.pk, key, row['feed'])
        if evidence.source != identity or batch.case.evidence.filter(kind='finance_source_unit', source=identity, version__gt=evidence.version).exists():
            raise ValidationError('Select current evidence for this exact import/input/feed identity')
        expected = {'schema': ASSERTION, 'batch_id': batch.pk, 'source_sha256': batch.source_sha256,
                    'input_key': key, 'feed': row['feed'], 'unit': row['unit']}
        try:
            content = json.loads(evidence.body)
        except (TypeError, ValueError):
            raise ValidationError('Source-unit evidence must contain the typed assertion') from None
        if pin != {'id': evidence.pk, 'version': evidence.version, 'sha256': evidence.sha256} or hashlib.sha256(evidence.body.encode()).hexdigest() != evidence.sha256 or json.dumps(content,sort_keys=True) != json.dumps(expected,sort_keys=True):
            raise ValidationError('Source-unit evidence binding does not match the exact supplied assertion')
    return json.loads(json.dumps(value))


def inspect(source):
    value = source.unit_declaration
    if value is None:
        return {'status': 'legacy_undeclared', 'declaration': None, 'findings': ['Historical source has no unit declaration; legacy behavior is not unit-confirmed.']}
    value = capture(source.batch, value)
    units = {row['unit'] for row in value['declarations']}
    if len(units - {'unknown'}) > 1:
        status = 'conflict'
    elif not units or 'unknown' in units:
        status = 'unknown'
    elif units != {'major_currency'}:
        status = 'unsupported'
    else:
        status = 'declared_major_currency'
    return {'status': status, 'declaration': value,
            'findings': [] if status == 'declared_major_currency' else ['Source unit ' + status + '; no conversion, selected winner or numeric preview.']}


def require_mapping(source):
    state = inspect(source)
    if state['status'] not in {'legacy_undeclared', 'declared_major_currency'}:
        raise ValidationError(state['findings'])
    return state
