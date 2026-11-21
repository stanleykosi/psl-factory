import json
from functools import wraps
from itertools import islice

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, RequestDataTooBig, ValidationError
from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from jsonschema import Draft202012Validator, FormatChecker, validators


MAX_JSON_BYTES = 256 * 1024
FORMATS = FormatChecker()
STRICT_VALIDATOR = validators.extend(
    Draft202012Validator,
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine('integer', lambda _, value: type(value) is int),
)

TEXT = {'type': 'string', 'minLength': 1}
ID = {'type': 'integer', 'minimum': 1, 'maximum': 2**63 - 1}
REVISION = {'type': 'integer', 'minimum': 1, 'maximum': 2**31 - 1}
BOOLEAN = {'type': 'boolean'}
UUID = {'type': 'string', 'format': 'uuid'}
DATETIME = {'type': 'string', 'format': 'date-time'}


def obj(properties, *, optional=()):
    return {'type': 'object', 'properties': properties,
            'required': [key for key in properties if key not in optional],
            'additionalProperties': False}


def array(items, *, limit=None):
    schema = {'type': 'array', 'items': items}
    if limit is not None:
        schema['maxItems'] = limit
    return schema


def choice(*values):
    return {'type': 'string', 'enum': list(values)}


def nullable(schema):
    return {'anyOf': [schema, {'type': 'null'}]}


class Problem(Exception):
    def __init__(self, status, code, message, *, fields=None):
        self.status, self.code, self.message, self.fields = status, code, message, fields


def error(status, code, message, *, fields=None):
    body = {'code': code, 'message': message}
    if fields:
        body['fields'] = fields
    return JsonResponse(body, status=status, headers={'Cache-Control': 'no-store'})


def missing():
    return error(404, 'not_found', 'This record is unavailable.')


def json_body(request, schema):
    if request.content_type != 'application/json':
        raise Problem(415, 'unsupported_media_type', 'Send an application/json request.')
    try:
        raw = request.body
        if len(raw) > MAX_JSON_BYTES:
            raise Problem(413, 'request_too_large', 'The request exceeds the JSON size limit.')
        body = json.loads(raw, parse_constant=_invalid_constant)
    except RequestDataTooBig:
        raise Problem(413, 'request_too_large', 'The request exceeds the JSON size limit.') from None
    except (ValueError, RecursionError):
        raise Problem(400, 'invalid_json', 'Send a valid JSON document.') from None
    failures = list(islice(STRICT_VALIDATOR(schema, format_checker=FORMATS).iter_errors(body), 12))
    if failures:
        fields = [{'name': '.'.join(map(str, item.absolute_path)) or 'body',
                   'message': 'Check the required fields and allowed values.'} for item in failures]
        raise Problem(422, 'invalid_input', 'Check the request fields.', fields=fields)
    return body


def _invalid_constant(value):
    raise ValueError(value)


def validation_problem(exc):
    message = exc.messages[0]
    prefix, _, reason = message.partition(':')
    if prefix in {'STALE_VERSION', 'CONFLICT', 'IDEMPOTENCY_CONFLICT'}:
        return error(409, prefix.lower(), reason.strip() or 'Reload and check the current record.')
    if message.startswith('Stale revision'):
        return error(409, 'stale_version', 'Reload and check the current record.')
    if prefix in {'policy_unconfigured', 'policy_missing', 'owner_needed', 'configuration_needed'}:
        return error(422, 'setup_required', reason.strip() or 'This action needs current setup.')
    return error(422, 'action_unavailable', message)


def endpoint(*, method='GET', request=None, response=None, status=200, summary, query=None, multipart=False):
    """Describe one operation and apply the same request contract at runtime."""
    def decorate(fn):
        @never_cache
        @wraps(fn)
        def view(http, *args, **kwargs):
            methods = [method, 'HEAD'] if method == 'GET' else [method]
            if not http.user.is_authenticated or not http.user.is_active:
                return error(401, 'unauthenticated', 'Sign in to continue.')
            if http.method not in methods:
                result = error(405, 'method_not_allowed', 'The requested method is unavailable.')
                result['Allow'] = ', '.join(methods)
                return result
            try:
                if request is not None and not multipart:
                    kwargs['body'] = json_body(http, request)
                return JsonResponse(fn(http, *args, **kwargs), status=status)
            except Problem as exc:
                return error(exc.status, exc.code, exc.message, fields=exc.fields)
            except (Http404, ObjectDoesNotExist):
                return missing()
            except PermissionDenied:
                return error(403, 'forbidden', 'You do not have permission for this action.')
            except ValidationError as exc:
                return validation_problem(exc)
        view.operation = {'method': method, 'request': request, 'response': response, 'status': status,
                          'summary': summary, 'query': query or {}, 'multipart': multipart}
        return view
    return decorate
