"""The registered live API and the contract generated from those same operations."""
import re

from django.conf import settings
from django.http import JsonResponse
from django.urls import path, re_path
from django.views.decorators.http import require_safe

from . import agents, assistant_drafts, commands, documents, handoffs, intake, notifications, received_bids, reviews, role_work, roles, work, workspaces
from .http import ID, TEXT, UUID, array, error, missing, obj


PREFIX = '/api/v1/'
ROUTES = (
    ('me', workspaces.me),
    ('projects/<uuid:case_id>/document-reviews/<int:version_id>', documents.preview, documents.decide),
    ('projects/<uuid:case_id>/department-handoffs', handoffs.project),
    ('work/<int:work_id>/coordination/<int:check_id>/retry', handoffs.retry),
    ('projects/<uuid:case_id>/templates/replacements', documents.replace_template),
    ('lines', intake.lines),
    ('lines/projects', intake.projects),
    ('processes', intake.processes),
    ('received-bids/organisations', received_bids.organisations),
    ('received-bids', received_bids.record),
    ('work', work.queue, intake.start),
    ('work/<int:work_id>', work.detail),
    ('work/<int:work_id>/department-handoff', handoffs.detail),
    ('work/<int:work_id>/department-handoff/source-review', handoffs.review),
    ('work/<int:work_id>/department-handoff/finance-acknowledgement', handoffs.acknowledge),
    ('work/<int:work_id>/history', work.history),
    ('work/<int:work_id>/background', work.background),
    ('work/<int:work_id>/actions', work.action),
    ('work/<int:work_id>/reviews', reviews.review),
    ('work/<int:work_id>/aggregate-receipt', reviews.acknowledge_aggregate),
    ('work/<int:work_id>/minutes/confirmation', commands.confirm_minutes),
    ('work/<int:work_id>/minutes/review-request', commands.request_minutes_review),
    ('work/<int:work_id>/bid-pack', commands.bid_pack, commands.save_bid_pack),
    ('work/<int:work_id>/bid-pack/review-request', commands.request_bid_review),
    ('work/<int:work_id>/rfp-outcome', commands.bid_outcome),
    ('tasks/<int:task_id>', work.task),
    ('tasks/<int:task_id>/claim', work.claim),
    ('tasks/<int:task_id>/decision', work.decision),
    ('overview', workspaces.overview),
    ('projects', workspaces.projects),
    ('projects/<uuid:case_id>', workspaces.project),
    ('projects/<uuid:case_id>/money', workspaces.money),
    ('projects/<uuid:case_id>/month-end', workspaces.close),
    ('projects/<uuid:case_id>/hr', workspaces.hr),
    ('projects/<uuid:case_id>/<slug:tab>', workspaces.project_tab),
    ('clients/<uuid:case_id>', workspaces.client),
    ('clients/<uuid:case_id>/contacts', workspaces.save_contact),
    ('setup/<uuid:case_id>/delegations', workspaces.delegations),
    ('setup/primary-roles', roles.built_ins),
    ('setup/<uuid:case_id>/primary-roles', roles.catalogue, roles.create),
    ('setup/<uuid:case_id>/people/<int:person_id>/primary-role', roles.review, roles.apply),
    ('setup/<uuid:case_id>/people/<int:person_id>/team-scope', roles.preview_scope, roles.apply_scope),
    ('setup/<uuid:case_id>/team-decisions', role_work.assign_factory_review),
    ('me/workspaces/<uuid:case_id>/primary-role', roles.own),
    ('role-dashboard', role_work.dashboard),
    ('role-work/<int:assignment_id>', role_work.detail),
    ('role-work/<int:assignment_id>/actions', role_work.action),
    ('role-work/<int:assignment_id>/decision', role_work.decide),
    ('assistant/conversations', agents.conversations, agents.start_conversation),
    ('assistant/conversations/<uuid:conversation_id>', agents.conversation),
    ('assistant/conversations/<uuid:conversation_id>/messages', agents.message),
    ('assistant/turns/<uuid:turn_id>/transfer', agents.transfer),
    ('assistant/turns/<uuid:turn_id>/draft', assistant_drafts.read, assistant_drafts.save),
    ('assistant/turns/<uuid:turn_id>/start', assistant_drafts.start),
    ('cases/<uuid:case_id>/files', agents.uploads, agents.upload),
    ('cases/<uuid:case_id>/files/<int:upload_id>/drafts', agents.queue),
    ('cases/<uuid:case_id>/file-drafts/<int:job_id>', agents.job),
    ('cases/<uuid:case_id>/file-drafts/<int:job_id>/review', agents.review),
    ('cases/<uuid:case_id>/file-drafts/<int:job_id>/recover', agents.recover),
    ('cases/<uuid:case_id>/file-drafts/<int:job_id>/handoff', agents.handoff),
    ('notifications', notifications.inbox),
    ('notifications/<str:notification_id>/read', notifications.mark_read),
    ('me/alert-preferences', notifications.preferences, notifications.save_preferences),
)
PATH_PARAMETER = re.compile(r'<(int|uuid|slug|str):([a-z_]+)>')
PARAMETER_TYPES = {'int': ID, 'uuid': UUID, 'slug': TEXT, 'str': TEXT}
ERROR = obj({'code': TEXT, 'message': TEXT, 'fields': array(obj({'name': TEXT, 'message': TEXT}))},
            optional=('fields',))
ERROR_RESPONSES = {
    '400': 'The request could not be read.',
    '401': 'Sign in with a current Django session.',
    '403': 'Permission or CSRF verification failed.',
    '404': 'The record is unavailable or outside the current user’s access.',
    '405': 'The HTTP method is unavailable on this route.',
    '409': 'A version, state or idempotency conflict requires current readback.',
    '413': 'The request exceeds the application size limit.',
    '415': 'The request uses the wrong content type.',
    '422': 'A field, workflow prerequisite or required configuration needs attention.',
    '500': 'An unexpected application error occurred.',
    '503': 'A dependency or bounded read is unavailable. Check current state before retrying.',
}
READ_ERRORS = ('400', '401', '403', '404', '405', '409', '422', '500', '503')
WRITE_ERRORS = (*READ_ERRORS, '413', '415')


def dispatch(handlers):
    methods = {view.operation['method']: view for view in handlers}
    if 'GET' in methods:
        methods['HEAD'] = methods['GET']

    def view(request, **values):
        if any(type(value) is int and not 1 <= value <= ID['maximum'] for value in values.values()):
            return missing()
        handler = methods.get(request.method)
        if handler is None:
            response = error(405, 'method_not_allowed', 'The requested method is unavailable.')
            response['Allow'] = ', '.join(sorted(methods))
            return response
        return handler(request, **values)

    view.api_handlers = methods
    return view


def json_content(schema):
    return {'application/json': {'schema': schema}}


def operation_id(handler):
    return f'{handler.__module__.split(".")[-1]}_{handler.__name__}'


def contract():
    paths = {}
    for route, *handlers in ROUTES:
        path_name = PREFIX + PATH_PARAMETER.sub(r'{\2}', route)
        operations = {}
        for handler in handlers:
            info = handler.operation
            method = info['method']
            path_params = [
                {'name': key, 'in': 'path', 'required': True,
                 'schema': info['path_parameters'].get(key, PARAMETER_TYPES[kind])}
                for kind, key in PATH_PARAMETER.findall(route)
            ]
            errors = WRITE_ERRORS if method == 'POST' else READ_ERRORS
            operation = {'summary': info['summary'], 'operationId': operation_id(handler),
                         'parameters': path_params + [
                             {'name': name, 'in': 'query', 'required': name in info['required_query'], 'schema': schema}
                             for name, schema in info['query'].items()
                         ], 'responses': {
                             str(info['status']): {'description': 'Success', 'content': json_content(info['response'])},
                             **{code: {'$ref': f'#/components/responses/Http{code}'} for code in sorted(errors)},
                             'default': {'description': 'Request or domain error',
                                         'content': json_content({'$ref': '#/components/schemas/Error'})},
                         }}
            if method == 'POST':
                operation['parameters'].append({'name': 'X-CSRFToken', 'in': 'header', 'required': True, 'schema': TEXT})
                media_type = 'multipart/form-data' if info['multipart'] else 'application/json'
                operation['requestBody'] = {'required': True, 'content': {media_type: {'schema': info['request']}}}
            operations[method.lower()] = operation
        paths[path_name] = operations
    return {
        'openapi': '3.1.0', 'info': {'title': 'PSL Operations Factory live API', 'version': '1.1.1',
            'description': 'Use the current same-origin Django session. For JSON writes, read the session CSRF token from '
                           'GET /api/v1/me. Follow returned Django links for workflow steps that use native forms.'},
        'security': [{'Session': []}], 'paths': paths,
        'components': {
            'schemas': {'Error': ERROR},
            'responses': {f'Http{code}': {'description': description,
                          'content': json_content({'$ref': '#/components/schemas/Error'})}
                          for code, description in ERROR_RESPONSES.items()},
            'securitySchemes': {
                'Session': {'type': 'apiKey', 'in': 'cookie', 'name': settings.SESSION_COOKIE_NAME,
                            'description': 'Sign in at the ordinary Django account page on the same origin.'},
            },
        },
    }


@require_safe
def schema(request):
    return JsonResponse(contract())


def unknown(request):
    return missing()


urlpatterns = [
    path('openapi.json', schema, name='factory_api_schema'),
    *(path(route, dispatch(handlers)) for route, *handlers in ROUTES),
    re_path(r'^.*$', unknown),
]
