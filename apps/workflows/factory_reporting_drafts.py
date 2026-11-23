"""Private human working copies. Native weekly report submission is a separate command."""

from django.core.exceptions import ValidationError

from apps.core.services import event, lock_case
from apps.documents.contracts import validate
from apps.identity.services import require
from apps.pmo.clocks import aware
from . import factory, factory_reporting as reporting
from .models import FactoryWork, WeeklyReportDraftVersion


THEMES = ('status', 'risks', 'timeline', 'next_steps')
DRAFT_VALUES = {
    'type': 'object',
    'properties': {
        'selection': reporting.INPUT,
        'parts': {
            'type': 'object',
            'properties': {key: {'type': 'object', 'properties': {
                'text': {'type': 'string', 'maxLength': 10000},
                'evidence_ids': {'type': 'array', 'maxItems': 18, 'uniqueItems': True,
                                 'items': {'type': 'integer', 'minimum': 1}},
            }, 'required': ['text', 'evidence_ids'], 'additionalProperties': False} for key in THEMES},
            'required': list(THEMES),
            'additionalProperties': False,
        },
        'reference': {'type': 'string', 'maxLength': 160},
        'key': {'type': 'string', 'maxLength': 100},
        'background': {'type': 'boolean'},
        'reason': {'type': 'string', 'maxLength': 2000},
    },
    'required': ['selection', 'parts'],
    'additionalProperties': False,
}


def return_review_id(work):
    version = reporting.document(work)
    if version and version.document.current_id == version.pk:
        latest = version.reviews.order_by('-pk').values_list('pk', 'verdict').first()
        if latest and latest[1] in ('return', 'reject'):
            return latest[0]
    return None


def current(actor, case, work=None, return_id=None):
    factory.access(actor, case, 'factory.manage' if work else 'factory.start', reporting.DEFINITION)
    require(actor, case, 'evidence.add')
    if work and (work.case_id != case.pk or work.definition != reporting.DEFINITION or not return_id):
        return None
    draft = WeeklyReportDraftVersion.objects.filter(case=case, author=actor, work=work).order_by('-pk').first()
    if draft and not draft.submitted_work_id and draft.return_review_id == return_id:
        if not work or draft.source_head_id == work.source_head_id:
            return draft
    return None


def check_version(draft, expected):
    if (expected or 0) != (draft.pk if draft else 0):
        raise ValidationError('The saved draft changed. Reopen the latest draft before continuing.')


def lock_intake(actor, case_id, case_revision, expected):
    case = lock_case(actor, case_id, 'factory.start', case_revision)
    draft = current(actor, case)
    check_version(draft, expected)
    return case, draft


def lock_correction(actor, work_id, work_revision, case_revision, expected):
    work = FactoryWork.objects.select_for_update().get(
        pk=work_id, definition=reporting.DEFINITION,
    )
    case = lock_case(actor, work.case_id, 'factory.manage', case_revision)
    work.case = case
    reporting.source(work, actor, current=False)
    return_id = return_review_id(work)
    draft = current(actor, case, work, return_id)
    reporting.require_correctable(work, work_revision)
    check_version(draft, expected)
    return case, work, return_id, draft


def record(actor, case, values, draft, *, work=None, return_id=None):
    if work and not return_id:
        raise ValidationError('Open the current returned report before saving a correction draft.')
    validate(DRAFT_VALUES, values)
    details = {'reason'} if work else {'key', 'reference', 'background'}
    if values.keys() != {'selection', 'parts'} | details:
        raise ValidationError('The draft details do not match this reporting step.')
    if work:
        for name in ('start_at', 'end_at'):
            selected = values['selection'][name]
            original = work.request[name]
            if selected and aware(selected, 'Draft period') != aware(original, 'Report period'):
                raise ValidationError('Keep the original reporting period for this correction.')
            values['selection'][name] = original
    if draft and draft.values == values:
        return draft
    saved = WeeklyReportDraftVersion.objects.create(
        case=case, author=actor, work=work, source_head_id=work.source_head_id if work else None,
        return_review_id=return_id, values=values,
    )
    event(actor, case, 'factory.weekly_draft_saved', draft=saved.pk, work=saved.work_id)
    return saved


def mark_submitted(draft, work):
    if draft:
        submitted = WeeklyReportDraftVersion.objects.create(
            case_id=draft.case_id, author_id=draft.author_id, work_id=draft.work_id,
            source_head_id=draft.source_head_id, return_review_id=draft.return_review_id,
            submitted_work=work, values={'submitted_from': draft.pk},
        )
        event(draft.author, work.case, 'factory.weekly_draft_submitted',
              draft=draft.pk, submission=submitted.pk, work=work.pk)


def form_initial(draft):
    initial = dict(draft.values['selection'])
    for key, part in draft.values['parts'].items():
        initial[key] = part['text']
        initial[f'{key}_citations'] = part['evidence_ids']
    return initial
