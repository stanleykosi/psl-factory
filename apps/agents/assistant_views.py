from urllib.parse import urlencode
from uuid import uuid4

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.presentation import workspace_name
from apps.documents.contracts import digest
from apps.identity.factory_access import PERSONA_ROLES, department_cases, role_managed

from . import assistant
from .assistant_models import AssistantConversation, AssistantDraftVersion


DRAFT_LABELS = {
    'planning/v1': 'Project planning draft',
    'commercial/v1': 'Costing and contract draft',
    'rfp-response/v1': 'Bid response draft',
    'pmo-finance/v1': 'Invoice work draft',
}


@login_required
@require_http_methods(['GET', 'HEAD'])
@never_cache
def department_records(request, persona, case_id):
    from django.http import Http404
    from .department_context import registers

    if persona not in PERSONA_ROLES:
        raise Http404
    cases = department_cases(request.user, PERSONA_ROLES[persona]).filter(pk=case_id)
    case = get_object_or_404(cases)
    groups = registers(persona, cases, request.user)
    selected = request.GET.get('group', groups[0].key if groups else '')
    group = next((item for item in groups if item.key == selected), None)
    if selected and group is None:
        raise Http404
    entries, page = [], None
    if group:
        rows = group.entries()
        if 'id' in request.GET:
            try:
                pk = int(request.GET['id'])
            except ValueError:
                raise Http404 from None
            rows = rows.filter(pk=pk)
        page = Paginator(rows, 25).get_page(request.GET.get('page'))
        entries = [group.source(persona, row) for row in page]
    return render(request, 'design/department_records.html', {'case': case, 'agent': persona,
        'department': assistant.PERSONAS[persona][1], 'groups': groups, 'group': group, 'entries': entries, 'page': page})


def owned_conversations(actor):
    scope = Q(pk__in=[])
    for persona in assistant.PERSONAS:
        scope |= Q(scope='project', persona=persona, case_id__in=assistant.cases_for(actor, persona).values('pk'))
        scope |= Q(scope='department', persona=persona,
                   case_id__in=department_cases(actor, PERSONA_ROLES[persona], heads_only=True).values('pk'))
    return AssistantConversation.objects.filter(actor=actor).filter(scope).select_related('case')


def open_conversation(actor, persona, case, key, scope='project'):
    if persona not in assistant.PERSONAS or not assistant.cases_for(actor, persona).filter(pk=case.pk).exists():
        raise PermissionDenied
    if scope not in ('project', 'department') or (scope == 'department' and not department_cases(
            actor, PERSONA_ROLES[persona], heads_only=True).filter(pk=case.pk).exists()):
        raise PermissionDenied
    conversation, _ = AssistantConversation.objects.get_or_create(pk=key, defaults={
        'actor': actor, 'case': case, 'persona': persona, 'scope': scope,
    })
    assistant.check(actor, conversation)
    if conversation.persona != persona or conversation.case_id != case.pk or conversation.scope != scope:
        raise ValidationError('IDEMPOTENCY_CONFLICT: Open a new conversation for the selected project or agent.')
    return conversation


class ConversationForm(forms.Form):
    workspace = forms.ChoiceField(label='Records to use')
    key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, cases, heads, data=None, *, workspace=None):
        super().__init__(data, initial={'key': uuid4(), 'workspace': workspace})
        departments = [(f'all:{case.pk}', f'All department projects · {case.tenant}') for case in heads]
        self.fields['workspace'].choices = [*departments, *((str(case.pk), workspace_name(case)) for case in cases)]


class QuestionForm(forms.Form):
    question = forms.CharField(label='Your message', max_length=4000, widget=forms.Textarea(attrs={'rows': 3}))
    focus = forms.MultipleChoiceField(label='Project records', required=False, widget=forms.CheckboxSelectMultiple,
                                       help_text='Choose up to five records or leave blank to check recent department records.')
    key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, sources, data=None, *, payroll_only=False, questions=assistant.PAYROLL_REPORT_QUESTIONS):
        super().__init__(data, initial={'key': uuid4()})
        if payroll_only:
            self.fields['question'] = forms.ChoiceField(label='Ask about your staff-cost report',
                choices=[('', 'Choose a question'), *((question, question) for question in questions)])
            self.fields['focus'].label = 'Received report'
            self.fields['focus'].help_text = 'The available report is checked even when you leave this blank.'
        self.fields['focus'].choices = [(digest(s), s['label']) for s in sources]


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def start(request, persona):
    if persona not in assistant.PERSONAS:
        from django.http import Http404

        raise Http404
    cases = assistant.cases_for(request.user, persona)
    try:
        workspace = forms.UUIDField(required=False).clean(request.GET.get('workspace'))
    except ValidationError:
        workspace = None
    if workspace and not cases.filter(pk=workspace).exists():
        workspace = None
    heads = department_cases(request.user, PERSONA_ROLES[persona], heads_only=True).order_by(
        'tenant', 'synthetic', 'created_at', 'pk').distinct('tenant', 'synthetic')
    form = ConversationForm(cases.order_by('title', 'pk'), heads,
                            request.POST if request.method == 'POST' else None, workspace=workspace)
    if request.method == 'POST' and form.is_valid():
        values = form.cleaned_data
        try:
            selection = values['workspace']
            case = get_object_or_404(cases, pk=selection.removeprefix('all:'))
            conversation = open_conversation(request.user, persona, case, values['key'],
                                             'department' if selection.startswith('all:') else 'project')
        except ValidationError:
            form.add_error(None, 'This request has already been used. Open a new conversation.')
        else:
            return redirect('assistant_thread', conversation_id=conversation.pk)
    return render(request, 'design/assistant_start.html', {
        'persona': assistant.PERSONAS[persona], 'form': form, 'can_start': bool(form.fields['workspace'].choices),
    })


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def thread(request, conversation_id):
    conversation = get_object_or_404(owned_conversations(request.user), pk=conversation_id)
    payroll_only = assistant.payroll_report_only(conversation)
    sources, next_work = assistant.tool_context(conversation)
    form = QuestionForm(sources, request.POST if request.method == 'POST' else None, payroll_only=payroll_only,
                        questions=assistant.payroll_questions_for(conversation) if payroll_only else ())
    if request.method == 'POST' and form.is_valid():
        try:
            values = form.cleaned_data
            assistant.reserve(request.user, conversation.pk, values['key'], values['question'], values['focus'])
            return redirect('assistant_thread', conversation_id=conversation.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    turns = current_turns(request.user, conversation, sources, next_work, payroll_only)
    return render(request, 'design/assistant_thread.html', {
        'case': conversation.case if conversation.scope == 'project' else None, 'conversation': conversation,
        'persona': assistant.PERSONAS[conversation.persona],
        'turns': turns, 'form': form, 'payroll_only': payroll_only,
        'earlier': owned_conversations(request.user).exclude(pk=conversation.pk).order_by('-updated_at', '-pk')[:12],
        'waiting': any(turn.status in {'queued', 'running'} for turn in turns),
    })


def current_turns(actor, conversation, sources, next_work, payroll_only):
    """Apply the same current-source fence for HTML and API readback."""
    saved = AssistantDraftVersion.objects.filter(turn_id=OuterRef('pk')).order_by('-number')
    history = conversation.turns.all()
    if payroll_only:
        history = history.filter(question__in=assistant.payroll_questions_for(conversation)).filter(
            Q(sources__contains=[{'record': {'field': 'payroll_report'}}]) | Q(sources=[], next_work=''))
    turns = list(reversed(history.select_related('started_draft', 'rfp_answer').annotate(
        saved_number=Subquery(saved.values('number')[:1]),
        saved_reference=Subquery(saved.values('payload__reference')[:1]),
        saved_case_revision=Subquery(saved.values('case_revision')[:1]),
    ).order_by('-created_at', '-pk')[:30]))
    started_ids = [turn.started_work_id for turn in turns if turn.started_work_id and not payroll_only]
    visible_work = set()
    role_sources = role_managed(actor)
    if started_ids:
        from apps.workflows.factory_views import visible

        visible_work = set(visible(actor).filter(pk__in=started_ids).values_list('pk', flat=True))
    for turn in turns:
        turn.stale = False
        if turn.context_hash:
            try:
                if (role_sources or conversation.persona == 'tola' or turn.question == assistant.TOTALS_QUESTION
                        or turn.image_upload_ids or getattr(turn, 'rfp_answer', None) is not None):
                    current, _ = assistant.turn_context(turn, pending=False)
                else:
                    current = assistant.source_focus(sources, turn.selected_sources or turn.focus)
                turn.stale = turn.context_hash != digest(current)
            except (PermissionDenied, ValidationError):
                turn.stale = True
        if turn.started_work_id in visible_work:
            turn.started_url = reverse('factory_detail', args=[turn.started_work_id])
            if turn.started_draft_id and turn.started_draft.turn_id == turn.pk:
                turn.draft_label = DRAFT_LABELS.get(turn.next_work, 'Work draft')
                turn.reviewed_number = turn.started_draft.number
                turn.reviewed_reference = turn.started_draft.payload.get('reference')
        turn.insufficient = turn.status == 'answered' and not turn.sources and turn.answer == assistant.INSUFFICIENT_EVIDENCE
        if turn.next_work.startswith('assistant:'):
            target = turn.next_work.split(':', 1)[1]
            if turn.next_work in next_work and not turn.stale:
                turn.transfer_name = assistant.PERSONAS[target][0]
                if turn.transferred_to_id:
                    turn.transfer_url = reverse('assistant_thread', args=[turn.transferred_to_id])
                else:
                    turn.transfer_action = reverse('assistant_transfer', args=[turn.pk, target])
        elif (not turn.started_work_id and turn.status == 'answered' and not turn.stale
              and turn.next_work in next_work and turn.next_work in DRAFT_LABELS):
            turn.draft_label = DRAFT_LABELS[turn.next_work]
            turn.draft_needs_refresh = bool(turn.saved_number and turn.saved_case_revision != conversation.case.revision)
            turn.next_url = reverse('factory_create') + '?' + urlencode({
                'definition': turn.next_work, 'case': conversation.case_id, 'assistant_turn': turn.pk,
            })
    return turns


@login_required
@require_POST
@never_cache
def transfer(request, turn_id, persona):
    from django.contrib import messages

    try:
        conversation = assistant.transfer(request.user, turn_id, persona)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        return redirect('design_agents')
    return redirect('assistant_thread', conversation_id=conversation.pk)
