from urllib.parse import urlencode
from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.agents.rfp_answer_models import RFPAnswerReview, RFPAnswerSuggestion
from apps.identity.services import visible_cases
from apps.workflows.factory_rfp import DEFINITION, inputs
from apps.workflows.models import FactoryWork

from . import rfp_answers


class AnswerForm(forms.Form):
    suggestion = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    predecessor = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    verdict = forms.ChoiceField(choices=[('accept', 'Accept Tola’s answer'), ('edit', 'Edit and accept'),
                                       ('replace', 'Write my own')])
    answer = forms.CharField(required=False, label='Your answer', max_length=4000,
                             widget=forms.Textarea(attrs={'rows': 6}))
    disposition = forms.ChoiceField(label='Coverage', choices=[('addressed', 'Addressed'),
        ('clarification', 'Needs clarification'), ('out_of_scope', 'Outside scope')])
    note = forms.CharField(required=False, label='Internal reason', max_length=2000,
        help_text='This reason stays in the review history.', widget=forms.Textarea(attrs={'rows': 2}))

    def clean(self):
        values = super().clean()
        if values.get('verdict') in {'edit', 'replace'} and not values.get('answer'):
            self.add_error('answer', 'Write the answer to save for this requirement.')
        return values


def item_url(work_id, key=None, mode=None):
    values = {}
    if key:
        values['requirement'] = key
    if mode:
        values['mode'] = mode
    url = reverse('factory_rfp_answers', args=[work_id])
    return url + '?' + urlencode(values) if values else url


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def workbench(request, work_id):
    work = get_object_or_404(FactoryWork.objects.select_related('case', 'source_head__created_by'),
        pk=work_id, definition=DEFINITION, case__in=visible_cases(request.user))
    rfp_answers.authorize(request.user, work)
    selected_key = request.POST.get('requirement') or request.GET.get('requirement')
    form = None
    if request.method == 'POST':
        try:
            expected = int(request.POST.get('revision', '0'))
            case_revision = int(request.POST.get('case_revision', '0'))
            action = request.POST.get('action')
            if action == 'suggest':
                rfp_answers.request(request.user, work.pk, selected_key, request.POST.get('operation_key'),
                    expected, case_revision)
                messages.success(request, 'Tola is drafting this answer. Your current response stays available.')
                return redirect(item_url(work.pk, selected_key))
            if action == 'review':
                form = AnswerForm(request.POST)
                if not form.is_valid():
                    raise ValidationError('Check the highlighted answer fields.')
                saved = rfp_answers.review(request.user, work.pk, expected, case_revision, [form.cleaned_data])
            elif action == 'bulk_accept':
                selected = request.POST.getlist('selected')
                if len(selected) > 100 or len(set(selected)) != len(selected):
                    raise ValidationError('Choose each suggested answer once.')
                decisions = []
                for selection in selected:
                    suggestion_id, predecessor = map(int, selection.split(':'))
                    suggestion = get_object_or_404(RFPAnswerSuggestion, pk=suggestion_id, work=work)
                    decisions.append({'suggestion': suggestion_id, 'predecessor': predecessor, 'verdict': 'accept',
                        'answer': '', 'disposition': suggestion.row['disposition'], 'note': ''})
                saved = rfp_answers.review(request.user, work.pk, expected, case_revision, decisions)
            elif action == 'undo':
                rfp_answers.undo(request.user, work.pk, int(request.POST.get('review', '0')), expected, case_revision)
                messages.success(request, 'The previous answer is restored. Review history is retained.')
                return redirect(item_url(work.pk, selected_key))
            else:
                raise ValidationError('Choose an available answer action.')
            messages.success(request, 'Answer saved under your name. The bid still needs its response and commercial reviews.')
            work.refresh_from_db()
            pending_keys = set(RFPAnswerSuggestion.objects.filter(work=work, turn__status='answered',
                reviews__isnull=True).values_list('key', flat=True))
            next_key = next((row['key'] for row in inputs(work)['matrix']
                             if row['key'] != selected_key and row['key'] in pending_keys), None)
            return redirect(item_url(work.pk, next_key or saved[-1].suggestion.key))
        except (ValidationError, ValueError, TypeError) as exc:
            message = ' '.join(exc.messages) if isinstance(exc, ValidationError) else 'Reload the current answer form.'
            if form is not None:
                form.add_error(None, message)
            else:
                messages.error(request, message)
    work.refresh_from_db()
    work.case.refresh_from_db()
    rows = inputs(work)['matrix']
    suggestions = list(RFPAnswerSuggestion.objects.filter(work=work, key__in=[row['key'] for row in rows],
        turn__conversation__actor=request.user).select_related('turn__conversation__actor').order_by('key', '-pk').distinct('key'))
    latest = {suggestion.key: suggestion for suggestion in suggestions}
    reviews = {review.suggestion_id: review for review in RFPAnswerReview.objects.filter(suggestion__in=suggestions)
        .select_related('actor').order_by('suggestion_id', '-pk').distinct('suggestion_id')}
    try:
        current_anchors = rfp_answers.anchors(request.user, work)
    except (PermissionDenied, ValidationError):
        current_anchors = None
    readable_sources = {}
    for row in rows:
        if row['evidence_id'] not in readable_sources:
            try:
                rfp_answers.source_for(request.user, work, row)
                readable_sources[row['evidence_id']] = True
            except (PermissionDenied, ValidationError):
                readable_sources[row['evidence_id']] = False
    query = request.GET.get('q', '').strip()[:120]
    status_filter = request.GET.get('status', '')
    items = []
    writable = True
    try:
        rfp_answers.writable(request.user, work)
    except (PermissionDenied, ValidationError):
        writable = False
    for row in rows:
        suggestion = latest.get(row['key'])
        item = {'row': row, 'suggestion': suggestion, 'status': 'Current answer', 'code': 'current',
                'url': item_url(work.pk, row['key']), 'operation_key': uuid4()}
        if suggestion:
            previous = reviews.get(suggestion.pk)
            item.update(review=previous, predecessor=previous.pk if previous else 0)
            try:
                if (current_anchors != suggestion.context or not readable_sources[row['evidence_id']]
                        or suggestion.row['evidence_id'] != row['evidence_id']):
                    raise ValidationError('The original source needs review.')
                if previous and previous.verdict != 'undo':
                    item.update(status={'accept': 'Accepted', 'edit': 'Accepted with edits', 'replace': 'Own answer'}.get(previous.verdict, 'Reviewed'),
                        code='accepted', can_undo=writable and row == previous.row)
                elif row == suggestion.row:
                    item.update(status={'queued': 'Queued', 'running': 'Tola is drafting', 'held': 'Needs a fresh check',
                                        'answered': 'Suggested by Tola'}[suggestion.turn.status],
                                code='suggested' if suggestion.turn.status == 'answered' else 'working')
                    item['can_review'] = writable and suggestion.turn.status == 'answered' and bool(suggestion.turn.sources)
                else:
                    item.update(status='Requirement changed', code='stale')
                item['original_answer'] = suggestion.turn.answer
            except (PermissionDenied, ValidationError):
                item.update(status='Source needs authorised review', code='stale', suggestion=None, review=None)
        if current_anchors is None or not readable_sources[row['evidence_id']]:
            item['row'] = dict(row, response='The requirement source needs authorised review.')
        items.append(item)
    selected = next((item for item in items if item['row']['key'] == selected_key), None)
    if selected is None:
        selected = next((item for item in items if item.get('can_review')), items[0] if items else None)
    if selected and selected.get('can_review') and form is None:
        mode = request.GET.get('mode', 'accept')
        if mode not in {'accept', 'edit', 'replace'}:
            mode = 'accept'
        form = AnswerForm(initial={'suggestion': selected['suggestion'].pk, 'predecessor': selected['predecessor'],
            'verdict': mode, 'disposition': selected['row']['disposition'],
            'answer': '' if mode == 'replace' else selected['original_answer']})
    shown = [item for item in items if (not query or query.casefold() in (item['row']['key'] + ' ' + item['row']['response']).casefold())
             and (not status_filter or item['code'] == status_filter)]
    return render(request, 'factory/rfp_answers.html', {'case': work.case, 'work': work, 'items': shown,
        'selected': selected, 'form': form, 'can_write': writable, 'query': query, 'status_filter': status_filter,
        'total': len(items), 'waiting': any(item['code'] == 'working' and item.get('suggestion') and
            item['suggestion'].turn.status in {'queued', 'running'} for item in items)})
