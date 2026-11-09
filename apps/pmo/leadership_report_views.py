"""Typed P40/P42 manual preparation. Recurrence remains the native clock service."""
import json
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import render
from apps.core.views import accessible_case
from apps.core.services import lock_case, add_evidence
from apps.core.evidence_access import public_evidence, forecast_private_query
from apps.identity.services import require
from apps.identity.models import Grant
from apps.documents.models import Template
from .forms import OffsetTimestamp
from . import leadership_reporting as reports


class LeadershipReportForm(forms.Form):
    start_at = OffsetTimestamp(label='Period start (with UTC offset)')
    end_at = OffsetTimestamp(label='Elapsed period end (exclusive, with UTC offset)')
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, actor, case, kind, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind
        self.fields['audience'] = forms.ChoiceField(choices=[(a, a.title()) for a in
            (['internal'] if kind == 'internal_tuesday' else ['internal', 'management'])])
        self.fields['template'] = forms.ModelChoiceField(queryset=Template.objects.filter(case=case,
            definition__document_type='status_report', definition__internal_review_required=kind=='monthly_executive'))
        models = {'meetings': reports.Meeting, 'actions': reports.ActionItem, 'milestones': reports.Milestone,
                  'issues': reports.Issue, 'changes': reports.ChangeRequest, 'escalations': reports.EscalationRequest}
        allowed = set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True))
        citation_ids = set()
        for domain, model in models.items():
            query = model.objects.filter(**({'profile__state__issue__case': case} if domain == 'escalations' else {'case': case}))
            if reports.DOMAINS[domain] not in allowed: query = query.none()
            lookup = 'current__evidence' if domain in ['meetings', 'actions', 'issues', 'changes'] else 'evidence'
            safe = public_evidence(case.evidence.all())
            if domain == 'changes': safe = safe | case.evidence.filter(source='psl:p56-confirmed-request/v1').exclude(forecast_private_query())
            query = query.filter(**{lookup+'__in': safe})
            self.fields['source_'+domain] = forms.ModelMultipleChoiceField(queryset=query, required=False,
                label='Selected '+domain, help_text='Only these records are covered; selection grants no source authority.')
            citation_ids.update(query.values_list(lookup+'_id', flat=True))
        for theme in reports.THEMES[kind]:
            self.fields[theme] = forms.CharField(max_length=10000, widget=forms.Textarea(attrs={'rows': 3}),
                label=theme.replace('_', ' ').title(), help_text='State sourced facts or explain missing coverage. No automatic health or financial performance calculation.')
            self.fields[theme+'_coverage'] = forms.ChoiceField(choices=[(v, v.replace('_', ' ').title()) for v in ['supported', 'partial', 'unknown', 'not_applicable']])
            self.fields[theme+'_citations'] = forms.ModelMultipleChoiceField(queryset=case.evidence.filter(pk__in=citation_ids), label='Evidence for '+theme.replace('_', ' '))
        self.fields['revision'].initial = case.revision

    def selections(self):
        return {key: sorted(row.pk for row in self.cleaned_data['source_'+key]) for key in reports.DOMAINS}

    def narrative(self):
        d = self.cleaned_data
        return {'protocol': reports.MODE, 'kind': self.kind, 'sections': {
            key: {'text': d[key], 'coverage': d[key+'_coverage'],
                  'evidence_ids': sorted(e.pk for e in d[key+'_citations'])} for key in reports.THEMES[self.kind]}}


@login_required
def prepare(request, case_id, kind):
    case = accessible_case(request.user, case_id)
    require(request.user, case, 'report.read'); require(request.user, case, 'report.draft')
    if kind not in reports.THEMES: raise ValidationError('Choose a registered leadership report kind')
    form = LeadershipReportForm(request.user, case, kind, request.POST if request.method == 'POST' else None)
    binding = None; investigation = None
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                d = form.cleaned_data
                case = lock_case(request.user, case.pk, 'report.draft', d['revision'])
                body = json.dumps(form.narrative(), sort_keys=True)
                e = case.evidence.filter(kind=reports.CONTENT, body=body, created_by=request.user, source='Human-supplied leadership narrative').order_by('-pk').first()
                if not e: e = add_evidence(request.user, case.pk, reports.CONTENT, body, 'Human-supplied leadership narrative')
                case.refresh_from_db()
                investigation = reports.investigate(request.user, case, kind, d['start_at'], d['end_at'], d['audience'], form.selections(), e.pk)
                binding = reports.prepare(request.user, case.pk, kind, d['start_at'], d['end_at'], d['template'].pk,
                    d['audience'], form.selections(), e.pk, case.revision)
        except ValidationError as exc: form.add_error(None, exc)
    return render(request, 'pmo/leadership_report.html', {'case': case, 'form': form, 'kind': kind,
                  'binding': binding, 'investigation': investigation})
