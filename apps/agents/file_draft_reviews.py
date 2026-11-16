"""Review a pinned file draft while retaining its original source excerpts."""
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.core.services import add_evidence, lock_case
from apps.documents.contracts import digest
from apps.documents.services import review_document

from .models import AgentJob, FileDraftReview
from .upload_jobs import authorize


class ReviewForm(forms.Form):
    draft = forms.CharField(min_length=64, max_length=64, widget=forms.HiddenInput)
    summary = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows': 4}))
    gaps = forms.CharField(max_length=12012, required=False, label='Open questions, one per line',
                          widget=forms.Textarea(attrs={'rows': 4}))
    note = forms.CharField(max_length=1000, label='Review note')

    def clean_gaps(self):
        gaps = [line.strip() for line in self.cleaned_data['gaps'].splitlines() if line.strip()]
        if len(gaps) > 12 or any(len(line) > 1000 for line in gaps):
            raise ValidationError('Use up to 12 questions with up to 1,000 characters each.')
        return gaps


def draft_digest(job):
    return digest({key: job.result.get(key) for key in ('summary', 'quotes', 'gaps', 'source_sha256', 'model')})


def evidence_body(summary, quotes, gaps):
    return '\n'.join([summary, '', 'Source excerpts:', *quotes, '', 'Open questions:', *gaps])


def review_form(job, data=None):
    # Always refresh the server pin when rendering a form after an error.
    values = data or {}
    return ReviewForm(initial={'draft': draft_digest(job), 'summary': values.get('summary', job.result['summary']),
                               'gaps': values.get('gaps', '\n'.join(job.result['gaps'])), 'note': values.get('note', '')})


@transaction.atomic
def retain(actor, case, job_id, data):
    case = lock_case(actor, case.pk, 'document.review')
    job = get_object_or_404(AgentJob.objects.select_for_update(), upload__case=case,
                            actor=actor, pk=job_id, status='draft')
    authorize(actor, job.upload)
    token = draft_digest(job)
    if job.result.get('source_sha256') != job.upload.sha256:
        raise ValidationError('The draft does not match the uploaded source.')
    # Older clients may still accept the original model text by submitting only a note.
    if 'summary' not in data and 'gaps' not in data and 'draft' not in data:
        note = ReviewForm.base_fields['note'].clean(data.get('note', ''))
        values = {'note': note, 'summary': job.result['summary'], 'gaps': job.result['gaps']}
    else:
        form = ReviewForm(data)
        if not form.is_valid():
            raise ValidationError(next(iter(form.errors.values()))[0])
        values = form.cleaned_data
        if values['draft'] != token:
            raise ValidationError('This draft changed. Reload before reviewing it.')
    evidence = add_evidence(actor, case.pk, 'agent_review_note',
                            evidence_body(values['summary'], job.result['quotes'], values['gaps']),
                            f'agent-draft:{job.pk}:sha256:{job.upload.sha256}')
    case.refresh_from_db()
    review_document(actor, case.pk, evidence.pk, 'accepted', values['note'], case.revision)
    FileDraftReview.objects.create(job=job, evidence=evidence, draft_sha256=token,
                                   summary=values['summary'], gaps=values['gaps'])
    job.status = 'reviewed'
    job.result = {**job.result, 'reviewed_evidence': evidence.pk}
    job.save(update_fields=['status', 'result'])


def reviewed_output(job, evidence):
    review = getattr(job, 'file_review', None)
    if review is None:
        return job.result
    if review.evidence_id != evidence.pk or review.draft_sha256 != draft_digest(job) or evidence.body != evidence_body(
        review.summary, job.result['quotes'], review.gaps,
    ):
        raise ValidationError('The workflow evidence does not match the reviewed draft.')
    return {**job.result, 'summary': review.summary, 'gaps': review.gaps}
