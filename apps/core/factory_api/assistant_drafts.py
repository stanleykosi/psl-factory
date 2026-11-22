from urllib.parse import urlencode

from django import forms
from django.shortcuts import get_object_or_404
from django.urls import reverse

from adapters.commercial_intake import FIELDS as COMMERCIAL_SOURCES
from apps.agents import assistant, assistant_drafts
from apps.agents.assistant_models import AssistantTurn
from apps.agents.assistant_views import owned_conversations
from apps.core.read_budget import ReadBudget, limit_queries
from apps.documents.models import Template
from apps.documents.template_access import visible_templates
from apps.identity.services import require
from apps.pmo.rfp import root
from apps.workflows import factory_planning, factory_rfp, factory_views
from apps.workflows.factory_progress_views import enroll

from .http import BOOLEAN, ID, REVISION, TEXT, UUID, Problem, array, endpoint, nullable, obj
from .intake import INTAKE_GRANTS, RFP_PAYLOAD
from .intake_sources import positive_id
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
FORMS = {'planning/v1': factory_views.PlanningStartForm, 'pmo-finance/v1': factory_views.StartForm,
         'commercial/v1': factory_views.CommercialStartForm}


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
    form = FORMS[turn.next_work](actor, submitted, case.pk)
    if not form.is_valid():
        raise Problem(422, 'invalid_input', 'Review the draft and select its current project sources.',
                      fields=[{'name': name, 'message': errors[0]} for name, errors in form.errors.items()])
    return form.cleaned_data


@endpoint(response=PROJECTION, summary='Read the saved draft and confirmed work from a current Assistant turn')
def read(request, turn_id):
    turn = authorised_turn(request.user, turn_id)
    return draft_data(turn, assistant_drafts.latest(turn))


FIELD = obj({'key': TEXT, 'label': TEXT})


@endpoint(response=obj({'line': TEXT, 'case_revision': REVISION, 'fields': array(FIELD, limit=25),
    'items': array(obj({'id': ID, 'label': TEXT}), limit=25), 'next_before': nullable(ID),
    'source_options_url': nullable(TEXT), 'current_intake_id': nullable(ID), 'predecessor_id': nullable(ID)}),
    query={'field': {**TEXT, 'maxLength': 100}, 'before': ID},
    summary='Read paged and currently authorised source choices for an exact Assistant draft')
def source_options(request, turn_id):
    actor = request.user
    turn = authorised_turn(actor, turn_id)
    case = turn.conversation.case
    line = turn.next_work
    result = {'line': line, 'case_revision': case.revision, 'fields': [], 'items': [], 'next_before': None,
              'source_options_url': None, 'current_intake_id': None, 'predecessor_id': None}
    if line == 'rfp-response/v1':
        result.update(source_options_url=f'/api/v1/projects/{case.pk}/intake-sources?line=rfp-response%2Fv1',
                      current_intake_id=root(case).current_intake_id)
        return result
    if line == 'pmo-finance/v1':
        result['source_options_url'] = f'/api/v1/projects/{case.pk}/intake-sources?line=pmo-finance%2Fv1'
        return result
    selected = request.GET.get('field')
    before = positive_id(request, 'before')
    with limit_queries(450):
        form = FORMS[line](actor, case_id=case.pk)
        result['predecessor_id'] = form.fields['predecessor'].initial if line == 'commercial/v1' else None
        fields = {key: field for key, field in form.fields.items()
                  if key != 'case' and isinstance(field, forms.ModelChoiceField)}
        result['fields'] = [{'key': key, 'label': field.label or key.replace('_', ' ').capitalize()} for key, field in fields.items()]
        if selected is None:
            return result
        if selected not in fields:
            raise Problem(422, 'invalid_filter', 'Choose a listed source for this draft.')
        field = fields[selected]
        candidates = field.queryset.order_by('-pk')
        if before is not None:
            candidates = candidates.filter(pk__lt=before)
        rows = list(candidates[:26])
        page = rows[:25]
        if candidates.model is Template:
            allowed = set(visible_templates(actor, case, candidate_ids=[row.pk for row in page], budget=ReadBudget()).values_list('pk', flat=True))
            page = [row for row in page if row.pk in allowed]
        result['items'] = [{'id': row.pk, 'label': str(field.label_from_instance(row))} for row in page]
        result['next_before'] = rows[24].pk if len(rows) > 25 else None
    return result


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
