import json
from functools import wraps
from itertools import islice

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, RequestDataTooBig, ValidationError
from django.http import Http404, HttpResponseBase, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from jsonschema import Draft202012Validator, FormatChecker, validators

from apps.core.read_budget import ReadLimit


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


@sensitive_variables('raw', 'body', 'failures')
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


def multipart_body(request, schema):
    if request.content_type != 'multipart/form-data':
        raise Problem(415, 'unsupported_media_type', 'Send a multipart form.')
    expected = schema['properties']
    names = (set(request.POST) | set(request.FILES)) - {'csrfmiddlewaretoken'}
    invalid = (names - set(expected)) | (set(schema['required']) - names)
    for name in names & set(expected):
        field = expected[name]
        binary = field.get('format') == 'binary'
        values, other = (request.FILES, request.POST) if binary else (request.POST, request.FILES)
        count = len(values.getlist(name))
        repeated = not binary and field.get('type') == 'array'
        if name in other or (repeated and count > field.get('maxItems', 100)) or (not repeated and count != 1):
            invalid.add(name)
        elif not binary and 'const' in field and values[name] != field['const']:
            invalid.add(name)
    if invalid:
        fields = [{'name': name, 'message': 'Send the declared field once in the correct part.'}
                  for name in sorted(invalid)[:12]]
        raise Problem(422, 'invalid_input', 'Check the multipart fields.', fields=fields)


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


def endpoint(*, method='GET', request=None, response=None, status=200, summary, query=None,
             required_query=(), path_parameters=None, multipart=False, authenticated=True, media_type='application/json'):
    """Describe one operation and apply the same request contract at runtime."""
    def decorate(fn):
        @never_cache
        @wraps(fn)
        @sensitive_post_parameters()
        @sensitive_variables('kwargs')
        def view(http, *args, **kwargs):
            methods = [method, 'HEAD'] if method == 'GET' else [method]
            if authenticated and (not http.user.is_authenticated or not http.user.is_active):
                return error(401, 'unauthenticated', 'Sign in to continue.')
            if http.method not in methods:
                result = error(405, 'method_not_allowed', 'The requested method is unavailable.')
                result['Allow'] = ', '.join(methods)
                return result
            try:
                if request is not None:
                    if multipart:
                        multipart_body(http, request)
                    else:
                        kwargs['body'] = json_body(http, request)
                result = fn(http, *args, **kwargs)
                if media_type != 'application/json':
                    if (not isinstance(result, HttpResponseBase) or result['Content-Type'] != media_type
                            or result.status_code != status):
                        raise TypeError('The declared download response must match its media type and status.')
                    return result
                return JsonResponse(result, status=status)
            except Problem as exc:
                return error(exc.status, exc.code, exc.message, fields=exc.fields)
            except (Http404, ObjectDoesNotExist):
                return missing()
            except RequestDataTooBig:
                return error(413, 'request_too_large', 'The request exceeds the application size limit.')
            except PermissionDenied:
                return error(403, 'forbidden', 'You do not have permission for this action.')
            except ReadLimit:
                return error(503, 'read_limited', 'The source needs a closer review. Check its current record.')
            except ValidationError as exc:
                return validation_problem(exc)
        view.operation = {'method': method, 'request': request, 'response': response, 'status': status,
                          'summary': summary, 'query': query or {}, 'required_query': required_query,
                          'path_parameters': path_parameters or {}, 'multipart': multipart, 'authenticated': authenticated,
                          'media_type': media_type}
        return view
    return decorate
