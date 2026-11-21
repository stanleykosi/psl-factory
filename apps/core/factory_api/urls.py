"""The registered live API and the contract generated from those same operations."""
import re

from django.http import JsonResponse
from django.urls import path, re_path
from django.views.decorators.http import require_safe

from . import agents, assistant_drafts, commands, intake, notifications, reviews, roles, work, workspaces
from .http import ID, TEXT, UUID, array, error, missing, obj


PREFIX = '/api/v1/'
ROUTES = (
    ('me', workspaces.me),
    ('lines', intake.lines),
    ('work', work.queue, intake.start),
    ('work/<int:work_id>', work.detail),
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
    ('projects/<uuid:case_id>/<slug:tab>', workspaces.project_tab),
    ('clients/<uuid:case_id>', workspaces.client),
    ('clients/<uuid:case_id>/contacts', workspaces.save_contact),
    ('setup/<uuid:case_id>/delegations', workspaces.delegations),
    ('setup/primary-roles', roles.built_ins),
    ('setup/<uuid:case_id>/primary-roles', roles.catalogue, roles.create),
    ('setup/<uuid:case_id>/people/<int:person_id>/primary-role', roles.review, roles.apply),
    ('me/workspaces/<uuid:case_id>/primary-role', roles.own),
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

    return view


def json_content(schema):
    return {'application/json': {'schema': schema}}


def contract():
    paths = {}
    for route, *handlers in ROUTES:
        path_name = PREFIX + PATH_PARAMETER.sub(r'{\2}', route)
        path_params = [
            {'name': key, 'in': 'path', 'required': True, 'schema': PARAMETER_TYPES[kind]}
            for kind, key in PATH_PARAMETER.findall(route)
        ]
        operations = {}
        for handler in handlers:
            info = handler.operation
            method = info['method']
            operation = {'summary': info['summary'], 'operationId': f'{handler.__module__.split(".")[-1]}_{handler.__name__}',
                         'parameters': path_params + [
                             {'name': name, 'in': 'query', 'required': False, 'schema': schema}
                             for name, schema in info['query'].items()
                         ], 'responses': {
                             str(info['status']): {'description': 'Success', 'content': json_content(info['response'])},
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
        'openapi': '3.1.0', 'info': {'title': 'PSL Operations Factory live API', 'version': '1.0.0'},
        'security': [{'Session': []}], 'paths': paths,
        'components': {'schemas': {'Error': ERROR}, 'securitySchemes': {
            'Session': {'type': 'apiKey', 'in': 'cookie', 'name': 'sessionid',
                        'description': 'Sign in at the ordinary Django account page on the same origin.'},
        }},
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
