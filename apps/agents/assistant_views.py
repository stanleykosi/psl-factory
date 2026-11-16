from urllib.parse import urlencode
from uuid import uuid4

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.presentation import workspace_name
from apps.documents.contracts import digest

from . import assistant
from .assistant_models import AssistantConversation


def owned_conversations(actor):
    scope = Q(pk__in=[])
    for persona in assistant.PERSONAS:
        scope |= Q(persona=persona, case_id__in=assistant.cases_for(actor, persona).values('pk'))
    return AssistantConversation.objects.filter(actor=actor).filter(scope).select_related('case')


class ConversationForm(forms.Form):
    workspace = forms.ModelChoiceField(queryset=None)
    key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, cases, data=None):
        super().__init__(data, initial={'key': uuid4()})
        self.fields['workspace'].queryset = cases
        self.fields['workspace'].label_from_instance = workspace_name


class QuestionForm(forms.Form):
    question = forms.CharField(label='Your message', max_length=4000, widget=forms.Textarea(attrs={'rows': 3}))
    focus = forms.MultipleChoiceField(label='Project records', required=False, widget=forms.CheckboxSelectMultiple,
                                       help_text='Choose up to five records or leave blank to check recent department records.')
    key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, sources, data=None):
        super().__init__(data, initial={'key': uuid4()})
        self.fields['focus'].choices = [(digest(s), s['label']) for s in sources]


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def start(request, persona):
    if persona not in assistant.PERSONAS:
        from django.http import Http404

        raise Http404
    cases = assistant.cases_for(request.user, persona)
    ids = list(cases.order_by('title', 'pk').values_list('pk', flat=True)[:50])
    form = ConversationForm(cases.filter(pk__in=ids).order_by('title', 'pk'), request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        values = form.cleaned_data
        conversation, _ = AssistantConversation.objects.get_or_create(pk=values['key'], defaults={
            'actor': request.user, 'case': values['workspace'], 'persona': persona,
        })
        assistant.check(request.user, conversation)
        if conversation.persona != persona or conversation.case_id != values['workspace'].pk:
            form.add_error(None, 'This request has already been used. Open a new conversation.')
        else:
            return redirect('assistant_thread', conversation_id=conversation.pk)
    return render(request, 'design/assistant_start.html', {
        'persona': assistant.PERSONAS[persona], 'form': form, 'can_start': bool(ids),
    })


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def thread(request, conversation_id):
    conversation = get_object_or_404(owned_conversations(request.user), pk=conversation_id)
    sources, next_work = assistant.tool_context(conversation)
    form = QuestionForm(sources, request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            values = form.cleaned_data
            assistant.reserve(request.user, conversation.pk, values['key'], values['question'], values['focus'])
            return redirect('assistant_thread', conversation_id=conversation.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    turns = list(reversed(conversation.turns.order_by('-created_at', '-pk')[:30]))
    started_ids = [turn.started_work_id for turn in turns if turn.started_work_id]
    visible_work = set()
    if started_ids:
        from apps.workflows.factory_views import visible

        visible_work = set(visible(request.user).filter(pk__in=started_ids).values_list('pk', flat=True))
    for turn in turns:
        turn.stale = False
        if turn.context_hash:
            try:
                current = assistant.source_focus(sources, turn.selected_sources or turn.focus)
                turn.stale = turn.context_hash != digest(current)
            except ValidationError:
                turn.stale = True
        if turn.started_work_id in visible_work:
            turn.started_url = reverse('factory_detail', args=[turn.started_work_id])
        if turn.next_work.startswith('assistant:'):
            target = turn.next_work.split(':', 1)[1]
            if turn.next_work in next_work and not turn.stale:
                turn.transfer_name = assistant.PERSONAS[target][0]
                if turn.transferred_to_id:
                    turn.transfer_url = reverse('assistant_thread', args=[turn.transferred_to_id])
                else:
                    turn.transfer_action = reverse('assistant_transfer', args=[turn.pk, target])
        elif not turn.started_work_id and turn.status == 'answered' and not turn.stale and turn.next_work in next_work:
            turn.next_url = reverse('factory_create') + '?' + urlencode({
                'definition': turn.next_work, 'case': conversation.case_id, 'assistant_turn': turn.pk,
            })
    return render(request, 'design/assistant_thread.html', {
        'case': conversation.case, 'conversation': conversation, 'persona': assistant.PERSONAS[conversation.persona],
        'turns': turns, 'form': form,
        'earlier': owned_conversations(request.user).exclude(pk=conversation.pk).order_by('-updated_at', '-pk')[:12],
        'waiting': any(turn.status in {'queued', 'running'} for turn in turns),
    })


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
