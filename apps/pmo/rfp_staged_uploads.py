"""Exact reservation and reconciliation of private bid documents only."""

import hashlib
import os
from contextlib import contextmanager
from secrets import token_hex

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection

from adapters import case_uploads
from apps.documents.contracts import digest

from .rfp_upload_models import RFPStagedUpload


def storage_identity():
    return digest(['psl.rfp-staged-upload/v1',
        [str(connection.settings_dict.get(key) or '') for key in ('HOST', 'PORT', 'NAME')],
        [os.getenv('PSL_UPLOAD_' + key, '') for key in ('ENDPOINT', 'BUCKET', 'REGION')]])


@contextmanager
def serialized(operation, *, wait=True):
    # One live PostgreSQL session spans the reservation and domain commits.
    key = int.from_bytes(bytes.fromhex(operation[:16]), 'big', signed=True)
    query = 'SELECT pg_advisory_lock(%s)' if wait else 'SELECT pg_try_advisory_lock(%s)'
    with connection.cursor() as cursor:
        cursor.execute(query, [key])
        acquired = wait or cursor.fetchone()[0]
    try:
        yield acquired
    finally:
        if acquired:
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_advisory_unlock(%s)', [key])
            except DatabaseError:
                connection.close()


def reserve(*, operation, actor, payload, fingerprint, size, case=None, revision=None, authority=None):
    expected = {'actor_id': actor.pk, 'case_id': case.pk if case else None, 'case_revision': revision,
                'authority_id': authority.pk if authority else None, 'payload_sha256': payload,
                'sha256': fingerprint, 'size': size, 'storage_identity': storage_identity()}
    row, created = RFPStagedUpload.objects.get_or_create(operation=operation,
        defaults={**expected, 'key': 'rfp-intake-' + token_hex(32)})
    if any(getattr(row, field) != value for field, value in expected.items()):
        raise ValidationError('This start request already has different details or its original upload scope changed.')
    return row, created


def ensure_storage(row):
    if row.storage_identity != storage_identity():
        raise ValidationError('The original private storage or database has changed.')


def put_or_verify(row, data, *, first):
    ensure_storage(row)
    if len(data) != row.size or hashlib.sha256(data).hexdigest() != row.sha256:
        raise ValidationError('Choose the same private bid document to finish this upload.')
    if first:
        try:
            case_uploads.put(row.key, data)
        except OSError as exc:
            raise ValidationError('Private storage is unavailable. Check this upload before trying again.') from exc
        return
    if not verified(row):
        raise ValidationError('The earlier file write could not be confirmed. Check this upload before trying again.')


def verified(row):
    """The existing adapter verifies exact bounded bytes without exposing them to the caller."""
    ensure_storage(row)
    try:
        case_uploads.read(row)
    except (OSError, ValidationError):
        return False
    return True
