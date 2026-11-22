from urllib.parse import urlencode

from django.shortcuts import get_object_or_404
from django.urls import reverse

from adapters.commercial_intake import FIELDS as COMMERCIAL_SOURCES
from apps.agents import assistant, assistant_drafts
from apps.agents.assistant_models import AssistantTurn
from apps.agents.assistant_views import owned_conversations
from apps.identity.services import require
from apps.pmo.rfp import root
from apps.workflows import factory_planning, factory_rfp, factory_views
from apps.workflows.factory_progress_views import enroll

from .http import BOOLEAN, ID, REVISION, TEXT, UUID, Problem, endpoint, nullable, obj
from .intake import INTAKE_GRANTS, RFP_PAYLOAD
from .work import WORK_RESULT, result


REFERENCE = {**TEXT, 'maxLength': 100}
NID = nullable(ID)
PAYLOADS = {
    'planning/v1': obj({'reference': REFERENCE, 'packet': ID}),
    'pmo-finance/v1': obj({'reference': REFERENCE, **dict.fromkeys(assistant_drafts.FIELDS['pmo-finance/v1'], NID),
                           'mode': {'type': 'string', 'enum': ['completion', 'existing-preparation/v1']},
                           'due_date': nullable({'type': 'string', 'format': 'date'})}),
    'commercial/v1': obj({'reference': REFERENCE, **dict.fromkeys(COMMERCIAL_SOURCES, NID), 'predecessor': NID}),
    'rfp-response/v1': obj({'reference': REFERENCE, 'rfp_intake': NID, 'native_inputs': RFP_PAYLOAD}),
}
PROJECTION = {'oneOf': [
    obj({'line': {'type': 'string', 'const': line}, 'case_id': UUID, 'case_revision': REVISION,
         'draft_version': nullable(REVISION), 'draft': nullable(payload), 'started_work_id': NID, 'django_url': TEXT})
    for line, payload in PAYLOADS.items()
]}
SUBMISSION = {'oneOf': [
    obj({'line': {'type': 'string', 'const': line}, 'case_revision': REVISION,
         'draft_version': nullable(REVISION), 'draft': payload, 'background': BOOLEAN}, optional=('background',))
    for line, payload in PAYLOADS.items()
]}


def authorised_turn(actor, turn_id):
    turn = get_object_or_404(AssistantTurn.objects.filter(
        conversation__in=owned_conversations(actor), next_work__in=PAYLOADS, status='answered',
    ), pk=turn_id)
    turn = assistant.work_intent(actor, turn_id, turn.next_work)
    for grant in INTAKE_GRANTS[turn.next_work]:
        require(actor, turn.conversation.case, grant)
    return turn


def draft_data(turn, draft):
    case = turn.conversation.case
    return {'line': turn.next_work, 'case_id': case.pk, 'case_revision': case.revision,
            'draft_version': draft.number if draft else None, 'draft': draft.payload if draft else None,
            'started_work_id': turn.started_work_id, 'django_url': reverse('factory_create') + '?' + urlencode({
                'definition': turn.next_work, 'case': case.pk, 'assistant_turn': turn.pk,
            })}


def draft_values(actor, turn, body):
    case = turn.conversation.case
    if body['line'] != turn.next_work:
        raise Problem(422, 'invalid_input', 'Use the line proposed in your current conversation.')
    submitted = {**body['draft'], 'case': case.pk, 'key': str(turn.pk), 'assistant_turn': turn.pk,
                 'draft_version': body['draft_version'], 'revision': body['case_revision']}
    if turn.next_work == 'rfp-response/v1':
        if root(case).current_intake_id != submitted['rfp_intake']:
            raise Problem(409, 'stale_version', 'Select the current received bid source.')
        submitted['reference'] = submitted['reference'].strip()
        if not submitted['reference']:
            raise Problem(422, 'invalid_input', 'Enter a work reference.')
        return {**submitted, 'case': case}
    classes = {'planning/v1': factory_views.PlanningStartForm, 'pmo-finance/v1': factory_views.StartForm,
               'commercial/v1': factory_views.CommercialStartForm}
    form = classes[turn.next_work](actor, submitted, case.pk)
    if not form.is_valid():
        raise Problem(422, 'invalid_input', 'Review the draft and select its current project sources.',
                      fields=[{'name': name, 'message': errors[0]} for name, errors in form.errors.items()])
    return form.cleaned_data


@endpoint(response=PROJECTION, summary='Read the saved draft and confirmed work from a current Assistant turn')
def read(request, turn_id):
    turn = authorised_turn(request.user, turn_id)
    return draft_data(turn, assistant_drafts.latest(turn))


@endpoint(method='POST', request=SUBMISSION, response=PROJECTION,
          summary='Save the current typed Assistant draft without starting work')
def save(request, turn_id, *, body):
    turn = authorised_turn(request.user, turn_id)
    values = draft_values(request.user, turn, body)
    saved = assistant_drafts.save(request.user, turn.next_work, values)
    return draft_data(turn, saved)


@endpoint(method='POST', request=SUBMISSION, response=WORK_RESULT,
          summary='Start native work with the exact reviewed Assistant draft version')
def start(request, turn_id, *, body):
    turn = authorised_turn(request.user, turn_id)
    actor = request.user
    values = draft_values(actor, turn, body)

    def start_native():
        if turn.next_work == 'pmo-finance/v1':
            return factory_views.start_invoice(actor, values)
        if turn.next_work == 'commercial/v1':
            return factory_views.start_commercial(actor, values)
        if turn.next_work == 'planning/v1':
            return factory_planning.start(actor, values['case'].pk, values['key'], values['packet'].pk,
                                          values['reference'], values['revision'])
        return factory_rfp.start(actor, values['case'].pk, values['key'], values['native_inputs'],
                                 values['reference'], values['revision'])

    work = assistant_drafts.start(actor, turn.next_work, values, start_native)
    enroll(request, work, body.get('background', True))
    return result(work)
