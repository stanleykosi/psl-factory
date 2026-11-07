"""Optional exact-ID QBO reads. No OAuth lifecycle or Finance adjudication."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from http.client import HTTPException
import math
import re
import urllib.request
import urllib.error

ORIGINS = {'sandbox': 'https://sandbox-quickbooks.api.intuit.com',
           'production': 'https://quickbooks.api.intuit.com'}
MAX_BODY = 65536
KEY = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}\Z')
ID = re.compile(r'[0-9]{1,40}\Z')


def require(ok):
    if not ok:
        raise ValueError('Invalid QBO read binding')


def validate_binding(value, secrets):
    require(isinstance(value, dict) and set(value) == {
        'enabled', 'environment', 'realm', 'entity', 'minor_version',
        'credential_ref', 'credential_revision', 'principal_ref'})
    require(type(value['enabled']) is bool)
    require(value['environment'] in ORIGINS and value['entity'] == 'Invoice')
    require(isinstance(value['realm'], str) and ID.fullmatch(value['realm']))
    require(isinstance(value['minor_version'], str) and re.fullmatch(r'[1-9][0-9]{0,2}', value['minor_version']))
    for key in ('credential_ref', 'credential_revision', 'principal_ref'):
        require(isinstance(value[key], str) and KEY.fullmatch(value[key]))
    credential = secrets.get(value['credential_ref'])
    require(isinstance(credential, dict) and set(credential) == {'env', 'revision'})
    require(credential['revision'] == value['credential_revision'])
    require(isinstance(credential['env'], str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}', credential['env']))
    return value


@dataclass(frozen=True)
class ReadIntent:
    """Caller owns current authorization, case/revision and retention checks."""
    case_ref: str
    source_revision: str
    binding_json: str
    object_id: str

    @classmethod
    def create(cls, case_ref, source_revision, binding, object_id, secrets):
        validate_binding(binding, secrets)
        require(binding['enabled'])
        require(all(isinstance(v, str) and KEY.fullmatch(v) for v in (case_ref, source_revision)))
        require(isinstance(object_id, str) and ID.fullmatch(object_id))
        return cls(case_ref, source_revision, json.dumps(binding, sort_keys=True), object_id)


@dataclass(frozen=True)
class Observation:
    intent: ReadIntent
    observed_at: str
    status: str
    sync_token: str | None = None
    transaction_date: str | None = None
    retry_after_seconds: int | None = None
    # Never a ledger SOURCE/RESPONSE; no accounting period, treatment or business key.


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def transport(url, token):
    require(isinstance(url, str) and re.fullmatch(
        r'https://(?:sandbox-)?quickbooks\.api\.intuit\.com/v3/company/[0-9]{1,40}/invoice/[0-9]{1,40}\?minorversion=[1-9][0-9]{0,2}', url))
    require(isinstance(token, str) and 0 < len(token) <= 4096 and all(32 < ord(c) < 127 for c in token))
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token,
                                                 'Accept': 'application/json'}, method='GET')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=5) as response:
            return response.status, response.headers.get_content_type(), response.read(MAX_BODY + 1)
    except urllib.error.HTTPError as error:
        # Do not read or expose provider error bodies/headers.
        code = error.code
        error.close()
        return code, '', b''


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result)
        result[key] = value
    return result


def finite_float(value):
    number = float(value)
    require(math.isfinite(number))
    return number


def invalid_constant(_):
    raise ValueError('Nonfinite JSON')


def read(intent, current_binding, secrets, resolve_secret, *, send=transport):
    """Single bounded read. Caller must recheck permission/currentness before recording.

    Token resolution is injected using the existing env/revision reference registry.
    No automatic retry, persistence, token refresh or remote writes.
    """
    validate_binding(current_binding, secrets)
    require(current_binding['enabled'])
    require(isinstance(intent, ReadIntent))
    expected = ReadIntent.create(intent.case_ref, intent.source_revision, current_binding,
                                 intent.object_id, secrets)
    require(expected == intent)
    token = resolve_secret(secrets[current_binding['credential_ref']]['env'])
    require(isinstance(token, str) and 0 < len(token) <= 4096 and
            all(32 < ord(c) < 127 for c in token))
    url = (ORIGINS[current_binding['environment']] + '/v3/company/' + current_binding['realm'] +
           '/invoice/' + intent.object_id + '?minorversion=' + current_binding['minor_version'])
    def result(status, **kwargs):
        return Observation(intent, datetime.now(timezone.utc).isoformat(), status, **kwargs)
    try:
        status, content_type, raw = send(url, token)
    except (OSError, TimeoutError, HTTPException):
        return result('unavailable')
    if status in (401, 403):
        return result('authentication_required')
    if status == 429:
        return result('throttled', retry_after_seconds=60)
    if status == 404:
        return result('not_observed')  # Not proof of business nonexistence.
    if status >= 500:
        return result('unavailable')
    if status != 200:
        return result('request_rejected')
    try:
        require(content_type == 'application/json' and isinstance(raw, bytes) and len(raw) <= MAX_BODY)
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid_constant, parse_float=finite_float)
        require(isinstance(value, dict) and 'Fault' not in value)
        obj = value['Invoice']
        require(isinstance(obj, dict) and obj['Id'] == intent.object_id)
        version, txn_date = obj['SyncToken'], obj['TxnDate']
        require(isinstance(version, str) and ID.fullmatch(version))
        require(isinstance(txn_date, str) and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', txn_date))
        date.fromisoformat(txn_date)
    except (ValueError, TypeError, KeyError, RecursionError):
        return result('protocol_mismatch')
    return result('observed_object', sync_token=version, transaction_date=txn_date)
