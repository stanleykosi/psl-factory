"""The registered live API and the contract generated from those same operations."""
import re

from django.conf import settings
from django.http import JsonResponse
from django.urls import path, re_path
from django.views.decorators.http import require_safe

from . import (
    agents, archive_files, assistant_drafts, bank_payments, bid_assignments, bid_delivery, client_records, clients, closure, commands, corrections,
    delivery, documents,
    finance_operations, go_live_replies, handoffs, hypercare,
    intake, intake_sources, invoice_recovery, meeting_records, minutes, notifications, payroll_sources, planning, policy_reviews,
    project_operations, received_bids,
    reminders, reviews,
    role_work, roles, setup, support_replies, work, work_access, workspaces,
)
from .http import ID, TEXT, UUID, array, error, missing, obj


PREFIX = '/api/v1/'
ROUTES = (
    ('me', workspaces.me),
    ('projects/<uuid:case_id>/document-reviews/<int:version_id>', documents.preview, documents.decide),
    ('projects/<uuid:case_id>/document-reviews/<int:version_id>/publication', documents.report_controls, documents.report_command),
    ('projects/<uuid:case_id>/department-handoffs', handoffs.project),
    ('work/<int:work_id>/coordination/<int:check_id>/retry', handoffs.retry),
    ('projects/<uuid:case_id>/templates/replacements', documents.replace_template),
    ('projects/<uuid:case_id>/templates', documents.catalogue, documents.first_template),
    ('lines', intake.lines),
    ('lines/projects', intake.projects),
    ('projects/<uuid:case_id>/intake-sources', intake_sources.options),
    ('projects/<uuid:case_id>/minutes/intake', intake.upload_minutes),
    ('processes', intake.processes),
    ('received-bids/organisations', received_bids.organisations),
    ('received-bids', received_bids.record),
    ('received-bids/assignments', bid_assignments.pending),
    ('received-bids/<uuid:case_id>/assignment', bid_assignments.detail, bid_assignments.assign),
    ('work', work.queue, intake.start),
    ('work/<int:work_id>', work.detail),
    ('work/<int:work_id>/access-request', work_access.status, work_access.request_access),
    ('work/<int:work_id>/invoice-milestone-proof', invoice_recovery.milestone_proof, invoice_recovery.attach_proof),
    ('work/<int:work_id>/invoice-milestone-proof/<int:task_id>/claim', invoice_recovery.claim_proof),
    ('work/<int:work_id>/invoice-draft-stop', invoice_recovery.draft_stop, invoice_recovery.stop_draft),
    ('work/<int:work_id>/department-handoff', handoffs.detail),
    ('work/<int:work_id>/department-handoff/source-review', handoffs.review),
    ('work/<int:work_id>/department-handoff/finance-acknowledgement', handoffs.acknowledge),
    ('work/<int:work_id>/history', work.history),
    ('work/<int:work_id>/background', work.background),
    ('work/<int:work_id>/actions', work.action),
    ('work/<int:work_id>/reviews', reviews.review),
    ('work/<int:work_id>/corrections', corrections.correct),
    ('work/<int:work_id>/planning-exit', delivery.planning_exit, delivery.decide_planning_exit),
    ('work/<int:work_id>/planning-owner-requests', planning.owner_requests, planning.observe),
    ('work/<int:work_id>/planning-exit/workaround', delivery.link_workaround),
    ('work/<int:work_id>/release-register', delivery.release_register, delivery.release_action),
    ('work/<int:work_id>/closure-report', closure.replace_report),
    ('work/<int:work_id>/go-live-signoff', delivery.go_live, delivery.record_go_live),
    ('work/<int:work_id>/go-live-replies', go_live_replies.detail, go_live_replies.command),
    ('work/<int:work_id>/go-live-replies/successor', go_live_replies.prepare_successor),
    ('work/<int:work_id>/go-live-milestone', go_live_replies.milestone),
    ('work/<int:work_id>/support-receipt', delivery.support_receipt, delivery.acknowledge_support),
    ('work/<int:work_id>/support-replies', support_replies.options, support_replies.record_reply),
    ('work/<int:work_id>/aggregate-receipt', reviews.acknowledge_aggregate),
    ('work/<int:work_id>/payroll-operations', payroll_sources.work_options, payroll_sources.operate),
    ('work/<int:work_id>/minutes', minutes.detail),
    ('work/<int:work_id>/minutes/action-options', minutes.action_options),
    ('work/<int:work_id>/archive-files', archive_files.inventory, archive_files.reserve),
    ('work/<int:work_id>/archive-files/<int:job_id>/recovery', archive_files.recover),
    ('work/<int:work_id>/archive-files/rules', archive_files.draft_rules),
    ('work/<int:work_id>/stability', hypercare.detail, hypercare.observe),
    ('work/<int:work_id>/stability/criteria', hypercare.draft_criteria),
    ('work/<int:work_id>/minutes/delivery', minutes.operate),
    ('work/<int:work_id>/minutes/confirmation', commands.confirm_minutes),
    ('work/<int:work_id>/minutes/review-request', commands.request_minutes_review),
    ('work/<int:work_id>/bid-pack', commands.bid_pack, commands.save_bid_pack),
    ('work/<int:work_id>/bid-pack/review-request', commands.request_bid_review),
    ('work/<int:work_id>/bid-pack/portal-receipt', bid_delivery.portal, bid_delivery.record_portal),
    ('work/<int:work_id>/bid-outcomes/<int:outcome_id>/followup', bid_delivery.followup, bid_delivery.followup_command),
    ('work/<int:work_id>/rfp-outcome', commands.bid_outcome),
    ('tasks/<int:task_id>', work.task),
    ('tasks/<int:task_id>/claim', work.claim),
    ('tasks/<int:task_id>/decision', work.decision),
    ('tasks/<int:task_id>/comments', corrections.invoice_comment),
    ('overview', workspaces.overview),
    ('payments', finance_operations.payments),
    ('month-end', finance_operations.company_close),
    ('projects', workspaces.projects),
    ('projects/<uuid:case_id>', workspaces.project),
    ('projects/<uuid:case_id>/money', workspaces.money),
    ('projects/<uuid:case_id>/month-end', workspaces.close),
    ('projects/<uuid:case_id>/month-end/receivables', finance_operations.capture_close),
    ('projects/<uuid:case_id>/invoices/<int:issue_id>/reminder', reminders.detail, reminders.draft),
    ('projects/<uuid:case_id>/invoices/<int:issue_id>/reminder/actions', reminders.command),
    ('projects/<uuid:case_id>/invoices/<int:issue_id>/payments', bank_payments.options, bank_payments.report),
    ('projects/<uuid:case_id>/invoices/<int:issue_id>/payments/<int:receipt_id>', bank_payments.detail),
    ('projects/<uuid:case_id>/invoices/<int:issue_id>/payments/<int:receipt_id>/reported-amount', bank_payments.supply_amount),
    ('projects/<uuid:case_id>/invoices/<int:issue_id>/payments/<int:receipt_id>/verification', bank_payments.verify),
    ('projects/<uuid:case_id>/invoices/<int:issue_id>/payments/<int:receipt_id>/allocations', bank_payments.allocate),
    ('projects/<uuid:case_id>/hr', workspaces.hr),
    ('projects/<uuid:case_id>/payroll/requests', payroll_sources.requests, payroll_sources.create_request),
    ('projects/<uuid:case_id>/payroll/requests/<int:request_id>/inputs', payroll_sources.imports, payroll_sources.upload),
    ('projects/<uuid:case_id>/payroll/<slug:kind>/<int:record_id>/working-rows', payroll_sources.working_rows),
    ('projects/<uuid:case_id>/meetings', meeting_records.collection, meeting_records.record),
    ('projects/<uuid:case_id>/meetings/options', meeting_records.options),
    ('projects/<uuid:case_id>/meetings/<int:meeting_id>', meeting_records.detail),
    ('projects/<uuid:case_id>/meetings/<int:meeting_id>/actions', meeting_records.link_action),
    ('projects/<uuid:case_id>/actions/create', meeting_records.create_action),
    ('projects/<uuid:case_id>/actions/<int:item_id>', project_operations.action, project_operations.update_action),
    ('projects/<uuid:case_id>/change-milestone-link', project_operations.stage_options, project_operations.link_stage),
    ('projects/<uuid:case_id>/milestones/completions', project_operations.milestone_options, project_operations.record_milestone),
    ('projects/<uuid:case_id>/planning', planning.detail, planning.command),
    ('projects/<uuid:case_id>/planning/department-inputs', planning.record_input),
    ('projects/<uuid:case_id>/planning/effort-review', planning.review_effort),
    ('projects/<uuid:case_id>/delivery/<int:dossier_id>/closure-checklist', closure.checklist),
    ('projects/<uuid:case_id>/<slug:tab>', workspaces.project_tab),
    ('clients', clients.directory),
    ('clients/groups/<str:group>', clients.group),
    ('clients/<uuid:case_id>', workspaces.client),
    ('clients/<uuid:case_id>/contacts', workspaces.save_contact),
    ('clients/<uuid:case_id>/contacts/history', clients.contact_history),
    ('clients/<uuid:case_id>/contacts/options', clients.contact_options),
    ('clients/<uuid:case_id>/project-people', client_records.named_people, client_records.save_person),
    ('clients/<uuid:case_id>/billing-identities', client_records.billing_identities, client_records.save_identity),
    ('clients/<uuid:case_id>/workspace-link', client_records.workspace_links, client_records.propose_link),
    ('clients/<uuid:case_id>/workspace-link/<int:evidence_id>/confirmation', client_records.confirm_link),
    ('setup/<uuid:case_id>/delegations', workspaces.delegations),
    ('setup/<uuid:case_id>/delegations/options', setup.delegation_options),
    ('setup/<uuid:case_id>/delegations/drafts', setup.draft_delegation),
    ('setup/<uuid:case_id>/rules', setup.rules),
    ('setup/<uuid:case_id>/decision-appointments', policy_reviews.appointments, policy_reviews.draft_appointments),
    ('setup/<uuid:case_id>/policy-configurations', policy_reviews.versions),
    ('setup/<uuid:case_id>/policy-configurations/<int:configuration_id>/review', policy_reviews.review),
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
    '429': 'The request reached its current rate or submission limit.',
    '500': 'An unexpected application error occurred.',
    '503': 'A dependency or bounded read is unavailable. Check current state before retrying.',
}
READ_ERRORS = ('400', '401', '403', '404', '405', '409', '422', '500', '503')
WRITE_ERRORS = (*READ_ERRORS, '413', '415', '429')


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
        'openapi': '3.1.0', 'info': {'title': 'PSL Operations Factory live API', 'version': '1.4.0',
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
