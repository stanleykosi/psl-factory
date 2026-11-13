"""Human-confirmed use of reviewed agent evidence by native workflow services."""
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.services import add_evidence, event, lock_case
from apps.documents import validation
from apps.finance import recognition
from apps.pmo import engagement, gates, issues, meetings, planning
from apps.pmo.services import subject
from .models import AgentJob
from .upload_jobs import authorize


LABELS = {
    'A01': 'Capture a Route B project intake',
    'A02': 'Register evidence for validation',
    'A03': 'Open a project issue',
    'A04': 'Capture planning questions',
    'A05': 'Prepare Finance recognition evidence',
    'A06': 'Record a reviewed meeting summary',
    'A07': 'Record a release evidence lead',
    'A08': 'Prepare a quality validation package',
}


def form_for(job, data=None):
    fields = {'confirm': forms.BooleanField(label='I confirm these details and want to use this reviewed draft')}
    if job.role == 'A03':
        fields['title'] = forms.CharField(max_length=240, label='Issue title')
        fields['next_action'] = forms.CharField(max_length=1000)
        from django.contrib.auth import get_user_model
        fields['owner'] = forms.ModelChoiceField(get_user_model().objects.filter(
            is_active=True, grant__case=job.upload.case, grant__action='issue.own', grant__active=True,
        ).distinct())
    elif job.role == 'A05':
        fields['start'] = forms.DateField(label='Reporting period starts', widget=forms.DateInput(attrs={'type': 'date'}))
        fields['end'] = forms.DateField(label='Reporting period ends', widget=forms.DateInput(attrs={'type': 'date'}))
    elif job.role == 'A06':
        fields['occurred_at'] = forms.DateTimeField(label='When the meeting took place')
        fields['purpose'] = forms.CharField(max_length=240)
    elif job.role == 'A07':
        from apps.pmo.models import DeliveryCandidate
        fields['candidate'] = forms.ModelChoiceField(DeliveryCandidate.objects.filter(case=job.upload.case))
        fields['gate'] = forms.ChoiceField(choices=[(key, f'{key.replace("_", " ")} · {owner}')
                                                   for key, owner in gates.GATE_OWNERS.items()])
        fields['external_ref'] = forms.CharField(max_length=240, label='Source reference')
    return type('ReviewedDraftForm', (forms.Form,), fields)(data)


def discovery(actor, case, evidence, key, result):
    ids = ['P15']
    metadata = {'document_kind': 'other', 'source_version': None, 'source_date': None,
                'owner_label': None, 'classification': 'source_description', 'process_ids': ids,
                'clauses': [{'key': f'line-{i}', 'quote': quote, 'locator': 'Reviewed draft excerpt',
                             'classification': 'source_description', 'process_ids': ids}
                            for i, quote in enumerate(dict.fromkeys(result['quotes']), 1)]}
    return validation.capture_source(actor, case.pk, key, evidence.pk, metadata, case.revision)


def create_record(actor, case, job, evidence, fields):
    key = f'agent-draft-{job.pk}'
    role, result = job.role, job.result
    if role == 'A01':
        if engagement.latest(case, 'capture'):
            raise ValidationError('This case already has an intake. Review its existing intake record.')
        source = add_evidence(actor, case.pk, 'engagement_source', evidence.body, f'evidence:{evidence.pk}')
        return engagement.capture(actor, case.pk, 'B', source.pk, key, key)
    if role == 'A02':
        return discovery(actor, case, evidence, key, result)
    if role == 'A03':
        return issues.log_issue(actor, case.pk, key, fields['title'], 'Investigation', fields['owner'].pk,
                                fields['next_action'], evidence.pk, result['summary'][:1000], case.revision)
    if role == 'A04':
        prior = planning.latest(case, 'packet')
        if prior:
            payload = planning.packet(case, prior.pk)[1]['payload']
        else:
            payload = {field: None for field in planning.SOURCE_KINDS}
            payload['stakeholders'] = [{'team': team, 'contact_id': None, 'evidence_id': None}
                                       for team in planning.TEAMS]
            payload['questions'] = []
        questions = result['gaps'] or [result['summary'][:1000]]
        payload['questions'] += [{'key': f'{key}-{i}', 'detail': question, 'state': 'unresolved',
                                  'action_id': None, 'evidence_id': evidence.pk}
                                 for i, question in enumerate(questions, 1)]
        return planning.capture(actor, case.pk, payload, prior.pk if prior else None)
    if role == 'A05':
        payload = {'period_start': fields['start'].isoformat(), 'period_end': fields['end'].isoformat(),
                   'as_of': timezone.localdate().isoformat(), 'statement': result['summary'],
                   'access_context': 'Human-reviewed case draft', 'contact_context': 'Finance review pending',
                   'facts': [], 'source_ids': [], 'milestone_ids': [],
                   'gaps': list(dict.fromkeys(result['gaps'])), 'conflicts': []}
        return recognition.prepare(actor, case.pk, key, payload, evidence.pk, case.revision)
    if role == 'A06':
        return meetings.record_meeting(actor, case.pk, key, 'status', fields['occurred_at'],
                                       fields['purpose'], result['summary'], [], [], evidence.pk, case.revision)
    if role == 'A07':
        return gates.record_gate(actor, case.pk, fields['candidate'].pk, fields['gate'],
                                 fields['external_ref'], evidence.pk, case.revision)
    source = discovery(actor, case, evidence, key, result)
    case.refresh_from_db()
    payload = {'process_ids': ['P15'], 'source_ids': [source.pk], 'example_ids': [],
               'policy_components': [], 'level': 'definition', 'purpose': 'P15', 'gaps': [
                   {'key': f'gap-{i}', 'description': gap, 'process_ids': ['P15'],
                    'state': 'open', 'evidence_id': evidence.pk}
                   for i, gap in enumerate(result['gaps'], 1)
               ], 'build_ref': 'Reviewed agent draft', 'role_list': [],
               'manual_fallback': 'Owner inspects source evidence', 'rollout_plan': 'Pending owner review',
               'migration_plan': 'Pending owner review', 'support_owner_id': None}
    return validation.prepare_package(actor, case.pk, key, payload, evidence.pk, case.revision)


@transaction.atomic
def consume(actor, case, job_id, data):
    from apps.finance.ledger import scope_lock

    scope_lock(case.pk)
    case = lock_case(actor, case.pk, 'case.read')
    job = AgentJob.objects.select_for_update().filter(
        pk=job_id, actor=actor, upload__case=case, status='reviewed',
    ).first()
    if not job or job.role not in LABELS:
        raise ValidationError('Select a reviewed draft in this case.')
    authorize(actor, job.upload)
    if job.result.get('workflow_record'):
        return
    form = form_for(job, data)
    if not form.is_valid():
        raise ValidationError('Confirm the handoff and complete its required details.')
    evidence = subject(case, job.result.get('reviewed_evidence'), 'agent_review_note')
    if evidence.source != f'agent-draft:{job.pk}:sha256:{job.upload.sha256}':
        raise ValidationError('The reviewed draft source no longer matches.')
    record = create_record(actor, case, job, evidence, form.cleaned_data)
    job.result = {**job.result, 'workflow_record': record.pk}
    job.save(update_fields=['result'])
    event(actor, case, 'agent.draft_used', job=job.pk, role=job.role, record=record.pk, evidence=evidence.pk)
