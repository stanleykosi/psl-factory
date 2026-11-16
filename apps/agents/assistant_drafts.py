from django.core.exceptions import ValidationError
from django.db import transaction
from adapters.commercial_intake import FIELDS as COMMERCIAL_SOURCES

from .assistant import cited_record, work_intent


FIELDS = {
    'planning/v1': ('packet',),
    'pmo-finance/v1': ('handoff', 'coverage', 'preparation', 'invoice'),
    'commercial/v1': tuple(COMMERCIAL_SOURCES),
}


def payload_from_form(definition, values):
    payload = {'reference': values['reference']}
    if definition == 'rfp-response/v1':
        return {**payload, 'rfp_intake': values['rfp_intake'], 'native_inputs': values['native_inputs']}
    for name in FIELDS[definition]:
        payload[name] = values[name].pk if values[name] else None
    if definition == 'commercial/v1':
        payload['predecessor'] = values['predecessor']
    if definition == 'pmo-finance/v1':
        payload['mode'] = values['mode']
        payload['due_date'] = values['due_date'].isoformat() if values['due_date'] else None
        # The native invoice form ignores fields outside the chosen mode.
        unused = ('preparation', 'invoice', 'due_date') if values['mode'] == 'completion' else ('handoff', 'coverage')
        for name in unused:
            payload[name] = None
    return payload


def latest(turn):
    return turn.draft_versions.order_by('-number').first()


def intent(actor, definition, values):
    turn = work_intent(actor, values['assistant_turn'], definition, values['case'].pk, lock=True)
    payload = payload_from_form(definition, values)
    source = 'rfp_intake' if definition == 'rfp-response/v1' else FIELDS[definition][0]
    cited = cited_record(turn, source)
    if cited is not None and payload[source] != cited:
        raise ValidationError('To use a different source, start that work from the line chooser.')
    if definition == 'commercial/v1' and not turn.started_work_id:
        from apps.pmo.commercial_intake import validate_sources

        validate_sources(actor, turn.conversation.case, {key: payload[key] for key in COMMERCIAL_SOURCES})
    if definition == 'rfp-response/v1' and not turn.started_work_id:
        from apps.workflows.factory_rfp import validate_payload

        validate_payload(turn.conversation.case, payload['native_inputs'])
    return turn, payload, latest(turn)


def record(turn, current, payload, values, actor):
    return turn.draft_versions.create(number=(current.number + 1 if current else 1), payload=payload,
                                      case_revision=values['revision'], saved_by=actor)


@transaction.atomic
def save(actor, definition, values):
    if not values['assistant_turn']:
        raise ValidationError('Open a draft from your Assistant conversation.')
    turn, payload, current = intent(actor, definition, values)
    if turn.started_work_id:
        raise ValidationError('Work has already started from this draft. Use the work item for corrections.')
    if values['revision'] != turn.conversation.case.revision:
        raise ValidationError('The workspace changed. Reopen the draft before saving.')
    if current and current.payload == payload and current.case_revision == values['revision']:
        return current
    if (values['draft_version'] or 0) != (current.number if current else 0):
        raise ValidationError('A newer draft is available. Reload before editing it.')
    return record(turn, current, payload, values, actor)


@transaction.atomic
def start(actor, definition, values, start_native):
    turn, payload, current = intent(actor, definition, values)
    if turn.started_work_id:
        if turn.started_draft_id and turn.started_draft.payload != payload:
            raise ValidationError('This draft already started different work. Review the original work item.')
        return turn.started_work
    if current:
        if (values['draft_version'] != current.number or current.payload != payload
                or current.case_revision != values['revision']):
            raise ValidationError('Save your current draft and review that version before starting.')
    else:
        if values['draft_version']:
            raise ValidationError('Open the current draft and start from there.')
        current = record(turn, None, payload, values, actor)
    values['key'] = str(turn.pk)
    work = start_native()
    if definition == 'planning/v1' and any(work.request[key] != payload[key] for key in ('packet', 'reference')):
        raise ValidationError('Planning work already exists with different intake details. Review it in My work.')
    turn.started_work = work
    turn.started_draft = current
    turn.save(update_fields=['started_work', 'started_draft'])
    return work
