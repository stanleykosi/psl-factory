"""Owner-controlled, read-only access to an original bid from a PMO workspace."""
import re
from uuid import UUID

from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Case as SortCase, Exists, IntegerField, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Lower, StrIndex
from django.urls import reverse

from apps.core.evidence_access import public_evidence
from apps.core.models import Case, Evidence
from apps.core.workbench import granted
from apps.identity.factory_access import department_cases, role_managed
from .models import BidConversationNote, BidSharingDecision, RFPCase, RFPOutcome, RFPSubmission
from .rfp_message_models import RFPFollowupReceipt
from .rfp_outcomes import assert_public_submission_sources, historical_submission


def workspaces(actor):
    if role_managed(actor):
        return department_cases(actor, 'pmo-lead')
    return granted(actor, ['case.read', 'rfp.read']).filter(kind='project')


def available(actor, workspace, *, department=False):
    if not actor.is_active or not workspaces(actor).filter(pk=workspace.pk).exists():
        raise PermissionDenied
    latest = BidSharingDecision.objects.filter(bid=OuterRef('pk')).order_by('-pk')
    source_scope = Q(case=workspace)
    if department:
        source_scope |= Q(case__in=department_cases(actor, 'pmo-lead', heads_only=True))
    return RFPCase.objects.filter(case__tenant=workspace.tenant, case__synthetic=workspace.synthetic,
        case__kind='project', tenant=workspace.tenant, current_intake__isnull=False).annotate(
            is_public=Subquery(latest.values('public')[:1]), sharing_version=Subquery(latest.values('pk')[:1])
        ).filter(source_scope | Q(is_public=True)).select_related('case', 'current_intake')


def owns(actor, bid):
    if not bid.current_intake_id:
        return False
    return bid.current_intake.assignments.order_by('-pk').values_list('pm_id', flat=True).first() == actor.pk


def locked_owner(actor, workspace, bid_id):
    # Native intake and assignment commands serialize on this same project.
    case = Case.objects.select_for_update().filter(pk=workspace.pk, pk__in=workspaces(actor)).first()
    if case is None:
        raise PermissionDenied
    bid = RFPCase.objects.select_related('current_intake').filter(pk=bid_id, case=case).first()
    if not bid or not owns(actor, bid):
        raise PermissionDenied('Only the current bid owner can do that.')
    return bid


@transaction.atomic
def set_visibility(actor, workspace, bid_id, choice, expected):
    bid = locked_owner(actor, workspace, bid_id)
    if choice not in ('public', 'private'):
        raise ValidationError('Choose Private or Public.')
    current = bid.sharing_decisions.order_by('-pk').first()
    public = choice == 'public'
    if current and current.public == public:
        return current
    if expected != (current.pk if current else 0):
        raise ValidationError('Sharing changed. Reload the bid and check the current setting.')
    return BidSharingDecision.objects.create(bid=bid, actor=actor, public=public)


@transaction.atomic
def record_note(actor, workspace, bid_id, body, operation):
    bid = locked_owner(actor, workspace, bid_id)
    body = body.strip()
    if not 0 < len(body) <= 4000:
        raise ValidationError('Enter a conversation note of up to 4,000 characters.')
    try:
        operation = UUID(str(operation))
    except (TypeError, ValueError):
        raise ValidationError('Reload the bid before saving the note.') from None
    note, _ = BidConversationNote.objects.get_or_create(operation=operation, defaults={
        'bid': bid, 'actor': actor, 'body': body})
    if (note.bid_id, note.actor_id, note.body) != (bid.pk, actor.pk, body):
        raise ValidationError('Reload the bid before saving another note.')
    return note


def record_entries(bid):
    """Only intake, client-facing submissions and the recorded client conversation."""
    intake = bid.current_intake
    rows = []
    def add(label, body, date):
        if body:
            rows.append({'label': label, 'body': body, 'date': date})

    evidence = public_evidence(Evidence.objects.filter(case_id=bid.case_id, pk=intake.evidence_id,
                                                       kind='rfp_intake')).values_list('body', flat=True).first()
    add('Received bid', intake.note, intake.received_at)
    add('Original request', evidence, intake.received_at)
    for submission in RFPSubmission.objects.filter(response__rfp=bid).select_related('response').order_by('pk'):
        try:
            assert_public_submission_sources(bid.case, submission)
            response = historical_submission(bid.case, submission)
        except (PermissionDenied, ValidationError):
            continue
        for row in response.matrix:
            add(f'Submitted response {response.number} · {row["key"]}', row['response'], submission.submitted_at)
    for result in RFPOutcome.objects.filter(submission__response__rfp=bid).order_by('pk'):
        add('Client outcome · ' + result.result, result.note, result.observed_at)
    for receipt in RFPFollowupReceipt.objects.filter(delivered=True,
            dispatch__outcome__submission__response__rfp=bid).select_related('dispatch'):
        add('Follow-up sent to client', receipt.dispatch.payload['body'], receipt.created_at)
    for note in bid.conversation_notes.order_by('pk'):
        add('Client conversation', note.body, note.created_at)
    return sorted(rows, key=lambda row: row['date'])


def visible_attachment(actor, bid):
    from .rfp_intake_upload import attachment_for, bound_attachment

    if bid.is_public or owns(actor, bid) or department_cases(actor, 'pmo-lead').filter(pk=bid.case_id).exists():
        return bound_attachment(bid.case, bid.current_intake, check_uploader=False)
    try:
        return attachment_for(actor, bid.case, bid.current_intake)
    except (PermissionDenied, ValidationError):
        return None


def original_document_text(actor, bid):
    from adapters import case_uploads, upload_text

    file = visible_attachment(actor, bid)
    if not file:
        return ''
    key = f'bid-original-text:{file.pk}:{file.sha256}'
    text = cache.get(key)
    if text is None:
        try:
            text = upload_text.extract(file.name, case_uploads.read(file))
        except (OSError, ValidationError):
            return ''
        cache.set(key, text, timeout=300)
    return text


def chat_sources(conversation, question=''):
    if conversation.persona != 'tola':
        return []
    actor, workspace = conversation.actor, conversation.case
    try:
        bids = available(actor, workspace, department=getattr(conversation, 'scope', 'project') == 'department')
    except PermissionDenied:
        return []
    common = {'about', 'after', 'answer', 'another', 'before', 'client', 'could', 'does', 'from',
              'give', 'have', 'into', 'original', 'please', 'project', 'proposal', 'said', 'should',
              'that', 'their', 'them', 'there', 'these', 'this', 'what', 'when', 'where', 'which',
              'with', 'would'}
    words = [w for w in re.findall(r'\w{4,}', question.casefold()) if w not in common][:8]
    matches = Q(pk__in=[])
    for word in words:
        matches |= Q(body__icontains=word)
    bids = bids.annotate(match=StrIndex(Lower(Value(question)), Lower('reference')),
        mentioned=Exists(BidConversationNote.objects.filter(matches, bid=OuterRef('pk'))),
        own=SortCase(When(case=workspace, then=Value(1)), default=Value(0), output_field=IntegerField()))
    sources = []
    for bid in bids.order_by('-match', '-mentioned', '-own', '-pk')[:5]:
        entries = record_entries(bid)
        document = original_document_text(actor, bid)
        if document:
            entries.insert(0, {'label': 'Original bid document', 'body': document})
        ranked = sorted(reversed(entries), key=lambda row: -sum(w in row['body'].casefold() for w in words))
        parts = []
        for row in ranked[:10]:
            body = row['body']
            offsets = [body.casefold().find(w) for w in words if w in body.casefold()]
            start = max(0, min(offsets) - 250) if offsets else 0
            parts.append(f"{row['label']}: {body[start:start + 1400]}")
        fact = '\n'.join(parts)
        sources.append({'label': 'Original bid · ' + bid.reference, 'fact': fact or bid.reference,
            'url': reverse('bid_record', args=[workspace.pk if bid.is_public else bid.case_id, bid.pk]),
            'record': {'field': 'bid_record', 'pk': bid.pk, 'sharing': bid.sharing_version}})
    return sources
