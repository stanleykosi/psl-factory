"""Weekly client report authoring with exact sources and independent delivery readback."""

import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.core.evidence_access import forecast_private_query
from apps.core.read_budget import ReadBudget, limit_queries
from apps.core.services import add_evidence
from apps.documents.models import Template
from apps.documents.template_access import visible_templates
from apps.identity.services import require
from apps.workflows.models import FactoryAttempt
from apps.pmo.reporting import client_citation_ids, client_content, client_section_findings
from apps.workflows import factory_reporting as reporting, factory_reporting_drafts as drafts

from .commands import require_line
from .delivery import PROOF, proof_rows
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, Problem, array, choice, endpoint, nullable, obj
from .intake import KEY, REF, START_RESULT, progress_result, start_projects
from .intake_sources import positive_id
from .reviews import VERDICT, VERSIONS
from .work import WORK_RESULT, result


PARTS = drafts.DRAFT_VALUES['properties']['parts']
DRAFT = obj({'id': ID, 'values': drafts.DRAFT_VALUES})
WINDOW = {'start_at': DATETIME, 'end_at': DATETIME}
SELECTION = obj({**WINDOW, 'template_id': nullable(ID), 'content_id': nullable(ID)})
SERIAL_DRAFT = obj({'draft_id': ID, 'case_revision': REVISION})
START_FIELDS = {'case_revision': REVISION, 'draft_id': nullable(ID), 'selection': reporting.INPUT,
                'parts': PARTS, 'key': KEY, 'reference': REF, 'background': BOOLEAN}
CORRECTION_FIELDS = {**VERSIONS, 'draft_id': nullable(ID), 'selection': reporting.INPUT, 'parts': PARTS,
                     'reason': {**TEXT, 'maxLength': 2000}}
TEMPLATE = obj({'id': ID, 'name': TEXT, 'version': REVISION})
RECIPIENT = obj({'name': TEXT, 'status': TEXT, 'receipt_id': nullable(ID), 'recorded_at': nullable(DATETIME)})
REVIEW_NOTE = obj({'section': choice(*sorted(reporting.SECTIONS)), 'text': TEXT, 'recorded_at': DATETIME})
REPORT_PREVIEW = obj({'id': ID, 'title': TEXT, 'number': REVISION, 'sections': array(
    obj({'key': choice(*sorted(reporting.SECTIONS)), 'text': {'type': 'string'}}))})
RECORD_GROUPS = ('meetings', 'actions', 'milestones', 'issues', 'changes')
SOURCE_RECORD = obj({'id': ID, 'label': TEXT, 'at': nullable(DATETIME), 'evidence_id': nullable(ID)})
INVENTORY = obj(dict.fromkeys(RECORD_GROUPS, obj({
    'count': {'type': 'integer', 'minimum': 0}, 'items': array(SOURCE_RECORD, limit=25),
})))


def draft_payload(row):
    return {'id': row.pk, 'values': row.values} if row else None


def complete(actor, case, selection, parts):
    inputs = dict(selection)
    if not inputs['template_id']:
        raise ValidationError('Choose a source-owned weekly client report template.')
    snapshot = reporting.inventory(actor, case, inputs)
    if inputs['content_id']:
        if any(part['text'] or part['evidence_ids'] for part in parts.values()):
            raise ValidationError('Choose an existing narrative or enter a new cited narrative.')
        client_content(case, snapshot, inputs['content_id'])
        return inputs
    allowed = client_citation_ids(case, snapshot)
    sections = {}
    for key, part in parts.items():
        text = part['text'].strip()
        ids = sorted(part['evidence_ids'])
        findings = client_section_findings(text, ids, allowed)
        if findings:
            raise Problem(422, 'invalid_input', 'Check the cited records and text for each section.',
                          fields=[{'name': f'parts.{key}.{name}', 'message': msg} for name, msg in findings.items()])
        sections[key] = {'text': text, 'evidence_ids': ids}
    payload = json.dumps({'protocol': 'pmo-weekly-client-content/v1', 'sections': sections}, sort_keys=True)
    source = 'Human-supplied weekly client narrative'
    evidence = case.evidence.filter(kind='agent_private_report_content', body=payload, created_by=actor,
                                    source=source).order_by('-pk').first()
    if evidence is None:
        evidence = add_evidence(actor, case.pk, 'agent_private_report_content', payload, source)
    inputs['content_id'] = evidence.pk
    return inputs


def sources(actor, case, window, before):
    with limit_queries(600):
        picked = Template.objects.filter(case=case, definition__document_type='status_report')
        candidate_ids = list(picked.order_by('-pk').values_list('pk', flat=True)[:25])
        templates = []
        try:
            require(actor, case, 'document.read')
        except PermissionDenied:
            pass
        else:
            visible = visible_templates(actor, case, candidate_ids=candidate_ids, budget=ReadBudget())
            for template in visible.order_by('-pk'):
                definition = template.definition
                if reporting.SECTIONS.issubset(definition['required_fields']) and set(definition['audience_fields'].get('client', [])) == reporting.SECTIONS:
                    templates.append({'id': template.pk, 'name': template.name, 'version': template.version})
        narratives = case.evidence.filter(kind='agent_private_report_content').exclude(forecast_private_query()).only(
            'id', 'version', 'kind').order_by('-pk')[:25]
        proofs, next_before, inventory = [], None, None
        if window:
            snapshot = reporting.inventory(actor, case, {**window, 'template_id': None, 'content_id': None})
            pins = client_citation_ids(case, snapshot)
            selected = case.evidence.filter(pk__in=pins)
            inventory = {}
            for key in RECORD_GROUPS:
                records = []
                for item in snapshot[key][:25]:
                    if key == 'milestones':
                        label, at, evidence_id = item.name, item.completed_at, item.evidence_id
                    else:
                        label, current = item.reference, item.current
                        at = (current.occurred_at if key == 'meetings' else getattr(current, 'created_at', None))
                        evidence_id = getattr(current, 'evidence_id', None)
                    records.append({'id': item.pk, 'label': label, 'at': at, 'evidence_id': evidence_id if evidence_id in pins else None})
                inventory[key] = {'count': len(snapshot[key]), 'items': records}
            if before:
                selected = selected.filter(pk__lt=before)
            ordered = list(selected.only('id', 'version', 'kind').order_by('-pk')[:51])
            proofs = proof_rows(ordered[:50])
            next_before = ordered[49].pk if len(ordered) > 50 else None
        return {'templates': templates, 'narratives': proof_rows(narratives), 'evidence': proofs,
                'next_before': next_before, 'inventory': inventory}


@endpoint(response=obj({'case_revision': REVISION, 'draft': nullable(DRAFT), 'templates': array(TEMPLATE, limit=25),
    'narratives': array(PROOF, limit=25), 'evidence': array(PROOF, limit=50), 'next_before': nullable(ID),
    'inventory': nullable(INVENTORY)}),
    query={**WINDOW, 'before': ID},
    summary='Read the private weekly draft and exact source choices for an elapsed period')
def intake_options(request, case_id):
    actor = request.user
    case = get_object_or_404(start_projects(actor, reporting.DEFINITION), pk=case_id)
    draft = drafts.current(actor, case)
    window = {key: request.GET[key] for key in WINDOW if key in request.GET}
    if window and len(window) != len(WINDOW):
        raise ValidationError('Choose both boundaries of the elapsed reporting period.')
    return {'case_revision': case.revision, 'draft': draft_payload(draft), **sources(actor, case, window, positive_id(request, 'before'))}


@endpoint(method='POST', request=obj({'action': choice('save_draft', 'start'), **START_FIELDS}),
          response={'oneOf': [SERIAL_DRAFT, START_RESULT]}, status=201,
          summary='Save a private weekly draft or submit cited content for native review and delivery')
@transaction.atomic
def intake_command(request, case_id, *, body):
    actor = request.user
    case = get_object_or_404(start_projects(actor, reporting.DEFINITION), pk=case_id)
    case, draft = drafts.lock_intake(actor, case.pk, body['case_revision'], body['draft_id'])
    selection, parts = body['selection'], body['parts']
    if draft and draft.values['key'] != body['key']:
        raise ValidationError('Continue the current draft with its original request key.')
    if body['action'] == 'save_draft':
        values = dict(selection=selection, parts=parts, **{key: body[key] for key in ('key', 'reference', 'background')})
        saved = drafts.record(actor, case, values, draft)
        return {'draft_id': saved.pk, 'case_revision': case.revision}
    inputs = complete(actor, case, selection, parts)
    case.refresh_from_db(fields=['revision'])
    work = reporting.start(actor, case.pk, body['key'], inputs, body['reference'], case.revision)
    drafts.mark_submitted(draft, work)
    return progress_result(actor, work, body['background'])


def review_context(actor, work, panel, return_id):
    version = panel['document']
    if not version:
        return None, None, []
    require(actor, work.case, 'document.read')
    returned = panel['return_review']
    can_inspect = (actor.pk == version.created_by_id or panel['can_correct'] or panel['review_verdicts']
                   or returned is not None and actor.pk == returned.actor_id)
    if not can_inspect:
        return None, None, []
    preview = {'id': version.pk, 'title': version.document.title, 'number': version.number,
               'sections': [{'key': part['heading'], 'text': part['text']}
                            for part in version.payload['sections'] if part['heading'] in reporting.SECTIONS]}
    return_note = returned.note if returned and returned.pk == return_id else None
    observation = FactoryAttempt.objects.filter(
        activity__work=work, activity__kind='ACT04', phase='observed', result__head=work.source_head_id,
        result__investigation__selected_inventory_current=True,
    ).order_by('-pk').first()
    if not observation or panel.get('readiness_changed'):
        return preview, return_note, []
    investigation = observation.result['investigation']
    if investigation.get('manifest') != panel['data']['manifest']:
        return preview, return_note, []
    notes = []
    if investigation.get('coverage'):
        notes.append(('executive_summary', investigation['coverage']))
    counts = investigation.get('counts', {})
    if type(counts.get('milestones_in_period')) is int:
        notes.append(('timeline', f"{counts['milestones_in_period']} milestone completions are in the selected evidence."))
    gaps = investigation.get('commitment_gaps', [])
    if gaps:
        notes.append(('next_steps', f'{len(gaps)} recorded commitments are missing an owner or deadline.'))
    unsupported = investigation.get('unsupported_claims', [])
    if unsupported:
        notes.append(('risks', 'Check these unsupported claims before approval. ' + '; '.join(unsupported)))
    return preview, return_note, [{'section': key, 'text': text, 'recorded_at': observation.created_at} for key, text in notes]


@endpoint(response=obj({**VERSIONS, 'selection': SELECTION, 'editable_parts': nullable(PARTS), 'draft': nullable(DRAFT),
    'return_review_id': nullable(ID), 'can_correct': BOOLEAN, 'document_version_id': nullable(ID),
    'return_note': nullable({'type': 'string'}), 'preview': nullable(REPORT_PREVIEW), 'review_notes': array(REVIEW_NOTE),
    'review_verdicts': array(VERDICT), 'recipients': array(RECIPIENT), 'next_action': TEXT,
    'evidence': array(PROOF, limit=50)}), summary='Read sources, returned drafts, review and exact weekly report receipts')
def detail(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, reporting.DEFINITION)
    with limit_queries(900):
        panel = reporting.projection(actor, work)
        inputs = panel['data']['inputs']
        return_id = drafts.return_review_id(work)
        draft, sections, proofs = None, None, []
        can_correct = panel['can_correct']
        if can_correct:
            try:
                snapshot = reporting.inventory(actor, work.case, {**inputs, 'content_id': None})
                selected = work.case.evidence.filter(pk__in=client_citation_ids(work.case, snapshot)).only('id', 'kind', 'version')
                proofs = proof_rows(selected.order_by('-pk')[:50])
                if inputs['content_id']:
                    _, sections = client_content(work.case, snapshot, inputs['content_id'])
            except (PermissionDenied, ValidationError):
                pass
            draft = drafts.current(actor, work.case, work, return_id)
        try:
            preview, return_note, notes = review_context(actor, work, panel, return_id)
        except PermissionDenied:
            preview, return_note, notes = None, None, []
    return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'selection': inputs,
            'editable_parts': sections, 'draft': draft_payload(draft), 'return_review_id': return_id,
            'can_correct': can_correct, 'document_version_id': panel['document'].pk if panel['document'] else None,
            'preview': preview, 'return_note': return_note, 'review_notes': notes,
            'review_verdicts': panel['review_verdicts'], 'next_action': panel['next_action'], 'evidence': proofs,
            'recipients': [{'name': item['recipient'], 'status': item['status'], 'recorded_at': item['at'],
                            'receipt_id': item['receipt'].pk if item['receipt'] else None} for item in panel['delivery']]}


@endpoint(method='POST', request=obj({'action': choice('save_draft', 'correct'), **CORRECTION_FIELDS}),
          response={'oneOf': [SERIAL_DRAFT, WORK_RESULT]}, status=201,
          summary='Save a private correction draft or replace the report narrative for fresh review')
@transaction.atomic
def correction(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, reporting.DEFINITION)
    revision = body['expected_revision']
    case, work, returned, draft = drafts.lock_correction(actor, work.pk, revision, body['case_revision'], body['draft_id'])
    selection, parts = body['selection'], body['parts']
    if body['action'] == 'save_draft':
        saved = drafts.record(actor, case, {'selection': selection, 'parts': parts, 'reason': body['reason']}, draft,
                              work=work, return_id=returned)
        return {'draft_id': saved.pk, 'case_revision': case.revision}
    inputs = complete(actor, case, selection, parts)
    case.refresh_from_db(fields=['revision'])
    corrected = reporting.correct(actor, work.pk, revision, case.revision, inputs, body['reason'])
    drafts.mark_submitted(draft, corrected)
    return result(corrected)
