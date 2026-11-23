from io import BytesIO
from uuid import uuid4

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_safe

from adapters import case_uploads, commercial_rework as rework_contract
from apps.agents.models import AgentJob, CaseUpload
from apps.agents.upload_views import upload_file
from apps.core.services import lock_case
from apps.core.evidence_access import public_evidence
from apps.core.views import accessible_case
from apps.documents.models import PublicationReceipt
from apps.identity.services import active_case_grants, require
from apps.policy.services import active_component, reference_values
from . import commercial_client_response as domain, commercial_rework as rework, signatures
from .commercial_forms import SignaturePacketForm
from .models import CommercialCase


class ResponseForm(forms.Form):
    operation_key = forms.UUIDField(widget=forms.HiddenInput)
    predecessor = forms.IntegerField(required=False, widget=forms.HiddenInput)
    receipt = forms.ModelChoiceField(queryset=PublicationReceipt.objects.none(), label='Version the client received')
    client_name = forms.CharField(max_length=160, label='Who responded')
    party_ref = forms.ChoiceField(required=False, label='Owner-confirmed signer, if already known')
    responded_at = forms.DateTimeField(label='When they responded', widget=forms.DateTimeInput(
        format='%Y-%m-%dT%H:%M:%S', attrs={'type': 'datetime-local', 'step': '1'}))
    outcome = forms.ChoiceField(label='What they did', choices=[('signed', 'Signed'),
        ('changes_requested', 'Asked for changes'), ('declined', 'Declined')])
    proofs = forms.ModelMultipleChoiceField(queryset=CaseUpload.objects.none(), label='Private proof files',
        widget=forms.CheckboxSelectMultiple)
    genuine = forms.BooleanField(label='I checked that this response genuinely came from the named client.')
    note = forms.CharField(max_length=4000, label='Response note or reason for correcting the earlier record',
                          widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, actor, case, revision, **kwargs):
        super().__init__(*args, auto_id='client-response-%s', **kwargs)
        receipts = PublicationReceipt.objects.filter(publication__version__commercialdocumentbinding__revision=revision,
            publication__version__audience='client') if revision else PublicationReceipt.objects.none()
        self.fields['receipt'].queryset = receipts.filter(pk__in=receipts.order_by('-pk').values('pk')[:50]).select_related('publication__version__document').order_by('-pk')
        self.fields['receipt'].label_from_instance = lambda row: str(row.publication.version) + ' · Delivered ' + timezone.localtime(row.created_at).strftime('%d %b %Y, %H:%M:%S')
        uploads = CaseUpload.objects.filter(case=case, actor=actor)
        self.fields['proofs'].queryset = uploads.filter(pk__in=uploads.order_by('-pk').values('pk')[:50]).order_by('-pk')
        self.fields['proofs'].label_from_instance = lambda row: row.name
        try:
            rules = reference_values(active_component('D11.client_signature_contract', case))[0]
            parties = [(p['party_ref'], p['display_name']) for p in rules['parties'] if 'sow' in p['documents']]
        except ValidationError:
            parties = []
        self.fields['party_ref'].choices = [('', 'Eligibility not confirmed yet'), *parties]


class RevisionForm(forms.Form):
    operation_key = forms.UUIDField(widget=forms.HiddenInput)
    predecessor = forms.IntegerField(required=False, widget=forms.HiddenInput)
    job = forms.ChoiceField(label='Reviewed planning draft')
    scope = forms.CharField(label='Revised scope for human review', max_length=20000, widget=forms.Textarea)
    note = forms.CharField(label='What you checked and changed', max_length=4000, widget=forms.Textarea(attrs={'rows': 2}))
    confirmed = forms.BooleanField(label='I checked this wording against the client request and selected project sources.')

    def __init__(self, *args, case, approved_jobs, **kwargs):
        super().__init__(*args, auto_id='commercial-revision-%s', **kwargs)
        self.fields['job'].choices = [('', 'Select a reviewed draft'), *[
            (job.pk, job.upload.name) for job, _ in approved_jobs]]
        for kind in rework_contract.SOURCE_KINDS:
            available = public_evidence(case.evidence.filter(kind=kind))
            retained = self.initial.get(kind)
            scope = Q(pk__in=available.order_by('-version').values('pk')[:25])
            if retained:
                scope |= Q(pk=retained)
            field = forms.ModelChoiceField(queryset=available.filter(scope).only('pk', 'version').order_by('-version'),
                                           required=False, label=kind.replace('_', ' ').capitalize(),
                                           empty_label='Unknown or not yet confirmed')
            field.label_from_instance = lambda row: f'Version {row.version}'
            self.fields[kind] = field


def revision_context(actor, case, metadata, proof_files, post=None):
    pending, approved = [], []
    for job in AgentJob.objects.filter(upload__in=proof_files, actor=actor, role='A04').select_related('upload'):
        if job.status == 'reviewed':
            try:
                job, _, advice = rework.reviewed_job(actor, case, metadata, job.pk)
            except (PermissionDenied, ValidationError):
                continue
            approved.append((job, advice))
        else:
            pending.append(job)
    head = rework.latest(case)
    saved, prepared = None, None
    if head:
        try:
            value, source, _, _ = rework.read(actor, case, head)
            if source.pk == metadata.pk:
                saved = value
                prepared = rework.prepared(case, head)
        except (PermissionDenied, ValidationError):
            pass
    initial = {'operation_key': uuid4(), 'predecessor': head.pk if head else None}
    if saved:
        initial.update(job=saved['job'], scope=saved['scope'], note=saved['note'])
        initial.update({kind: pin['id'] if pin else None for kind, pin in saved['sources'].items()})
    elif len(approved) == 1:
        initial['job'] = approved[0][0].pk
    form = RevisionForm(post, case=case, approved_jobs=approved, initial=initial) if approved and not prepared else None
    return {'approved': approved, 'pending': pending, 'form': form, 'head': head,
            'saved': saved, 'prepared': prepared}


def signature_form(case, response, data=None):
    previous = signatures.latest(case)
    form = SignaturePacketForm(data, case=case, initial={'operation_key': str(uuid4()),
        'predecessor': previous.pk if previous else None, 'sow_signature': response.evidence_id,
        'commercial_revision': response.revision_id})
    form.auto_id = 'document-signatures-%s'
    for name in ['operation_key', 'predecessor', 'commercial_revision']:
        form.fields[name].widget = forms.HiddenInput()
    form.fields['sow_signature'].disabled = True
    form.fields['sow_signature'].label = 'Recorded statement-of-work signature proof'
    form.fields['prd'].label = 'Product requirements document'
    form.fields['note'].label = 'What you checked'
    # Source choices load bounded authorised metadata, never every historical body.
    for name, kind, retained in [('prd', 'prd', previous.sources['prd']['id'] if previous else None),
                                 ('prd_signature', 'signature', previous.signatures.get('prd', {}).get('evidence_id') if previous else None),
                                 ('sow_signature', 'signature', response.evidence_id)]:
        available = public_evidence(case.evidence.filter(kind=kind))
        limit = 25 if kind == 'prd' else 50
        selected = Q(pk__in=available.order_by('-pk').values('pk')[:limit])
        if retained:
            selected |= Q(pk=retained)
        if name == 'sow_signature':
            selected = Q(pk=response.evidence_id)
        form.fields[name].queryset = available.filter(selected).only('pk', 'version', 'kind', 'source', 'created_at').order_by('-pk')
        form.fields[name].label_from_instance = lambda row: 'Version ' + str(row.version) + ' · Recorded ' + timezone.localtime(row.created_at).strftime('%d %b %Y, %H:%M:%S')
    try:
        rules = reference_values(active_component('D11.client_signature_contract', case))[0]
    except ValidationError:
        rules = None
    for kind, title in [('sow', 'Statement of work'), ('prd', 'Product requirements')]:
        form.fields[kind + '_signature'].label = title + ' signature evidence'
        form.fields[kind + '_locator'].label = title + ' signature location in the proof'
        form.fields[kind + '_verified'].label = 'I personally checked the ' + title.lower() + ' signature.'
        parties = [(p['party_ref'], p['display_name']) for p in rules['parties'] if kind in p['documents']] if rules else []
        methods = [(method, method) for method in rules['methods']] if rules else []
        form.fields[kind + '_party'] = forms.ChoiceField(required=False, label=title + ' signer',
            choices=[('', 'Owner has not confirmed / not selected'), *parties])
        form.fields[kind + '_method'] = forms.ChoiceField(required=False, label=title + ' proof method',
            choices=[('', 'Owner has not confirmed / not selected'), *methods])
    return form


@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def workbench(request, case_id):
    case = accessible_case(request.user, case_id)
    case = lock_case(request.user, case.pk, 'commercial.read')
    domain.readable(request.user, case)
    dossier = CommercialCase.objects.select_related('current').filter(case=case).first()
    revision = dossier.current if dossier else None
    metadata = domain.latest(case)
    value, response, proof_files = None, None, []
    unavailable, can_record = False, True
    try:
        domain.witness(request.user, case)
    except (PermissionDenied, ValidationError):
        can_record = False
    if metadata:
        try:
            value, response = domain.read(request.user, case, metadata)
            proof_files = domain.proof_rows(request.user, case, metadata)
        except (PermissionDenied, ValidationError):
            unavailable = True
    permissions = active_case_grants(request.user, [case.pk], actions=['agent.extract', 'baseline.sign', 'commercial.prepare'])
    can_rework = bool(value and value['outcome'] == 'changes_requested' and can_record
                      and (case.pk, 'commercial.prepare') in permissions
                      and (case.pk, 'agent.extract') in permissions
                      and metadata.created_by_id == request.user.pk and case.synthetic)
    revision_desk = revision_context(request.user, case, metadata, proof_files) if can_rework else None
    form = ResponseForm(actor=request.user, case=case, revision=revision, initial={
        'operation_key': uuid4(), 'predecessor': metadata.pk if metadata else None,
        'responded_at': timezone.localtime().replace(microsecond=0)}) if can_record else None
    error, signing = None, signature_form(case, response) if (can_record and response and response.kind == 'signed'
        and (case.pk, 'baseline.sign') in permissions) else None
    if request.method == 'POST':
        try:
            expected = forms.IntegerField(min_value=1).clean(request.POST.get('revision'))
            action = request.POST.get('action')
            if action == 'upload':
                domain.witness(request.user, case)
                if case.revision != expected:
                    raise ValidationError('This project changed. Reload before attaching proof.')
                upload_file(request.user, case, request.FILES.get('file'))
            elif action == 'record':
                domain.witness(request.user, case)
                form = ResponseForm(request.POST, actor=request.user, case=case, revision=revision)
                if not form.is_valid():
                    raise ValidationError(next(iter(form.errors.values()))[0])
                if not revision:
                    raise ValidationError('Prepare and deliver the actual statement of work first.')
                data = form.cleaned_data
                domain.record(request.user, case.pk, revision.pk, data['receipt'].pk, data['client_name'], data['responded_at'],
                    data['outcome'], data['genuine'], [row.pk for row in data['proofs']], data['note'],
                    data['operation_key'], expected, data['predecessor'], data['party_ref'] or None)
            elif action == 'agent':
                domain.ask_agent(request.user, case, metadata)
            elif action == 'review_changes' and can_rework:
                rework.ask_agent(request.user, case.pk, metadata.pk, expected)
            elif action == 'save_revision' and can_rework:
                revision_desk = revision_context(request.user, case, metadata, proof_files, request.POST)
                draft_form = revision_desk['form']
                if not draft_form or not draft_form.is_valid():
                    raise ValidationError('Choose a reviewed draft, add the revised wording and confirm what you checked.')
                fields = draft_form.cleaned_data
                inputs = {kind: fields[kind].pk if fields[kind] else None for kind in rework_contract.SOURCE_KINDS}
                rework.capture(request.user, case.pk, metadata.pk, fields['job'], inputs, fields['scope'],
                               fields['note'], fields['confirmed'], fields['operation_key'], expected, fields['predecessor'])
            elif action == 'prepare_revision' and can_rework:
                draft = forms.IntegerField(min_value=1).clean(request.POST.get('draft'))
                rework.prepare_revision(request.user, case.pk, draft, expected)
            elif action == 'signatures' and response and response.kind == 'signed':
                domain.witness(request.user, case)
                require(request.user, case, 'baseline.sign')
                signing = signature_form(case, response, request.POST)
                if not signing.is_valid():
                    raise ValidationError(next(iter(signing.errors.values()))[0])
                data = signing.cleaned_data
                signatures.capture_packet(request.user, case.pk, data['prd'].pk, data['signatures'], data['note'],
                    data['operation_key'], expected, response.revision_id, data['predecessor'])
            elif action == 'adopt' and response and response.kind == 'signed':
                from .commercial import adopt_signed
                require(request.user, case, 'baseline.sign')
                domain.current_for_signature(request.user, case, response.evidence)
                adopt_signed(request.user, case.pk, response.revision_id, response.pk, expected)
            elif action == 'reaffirm' and response and response.kind == 'signed':
                domain.witness(request.user, case)
                require(request.user, case, 'baseline.sign')
                packet_id = forms.IntegerField(min_value=1).clean(request.POST.get('packet'))
                signatures.reaffirm_baseline(request.user, case.pk, packet_id, expected)
            else:
                raise ValidationError('Choose an available client response action.')
            return redirect('commercial_client_response', case_id=case.pk)
        except ValidationError as exc:
            error = exc.messages[0]
            if error == 'Capture a current separate SOW and PRD signature packet':
                error = 'Check both the statement of work and product requirements signatures before confirming the project baseline.'
            case.refresh_from_db()
        except OSError:
            error = 'Private proof could not be read. Keep the source and try again when storage is available.'
    packet = signatures.latest(case)
    adoption = getattr(response, 'baselineadoption', None) if response else None
    finance_intake = getattr(adoption, 'signedbaselineintake', None) if adoption else None
    baseline_current = False
    if adoption:
        try:
            signatures.assert_current_signed_baseline(case)
            baseline_current = True
        except (PermissionDenied, ValidationError):
            pass  # Historical adoption stays visible; it cannot claim current authority.
    result = render(request, 'pmo/commercial_client_response.html', {'case': case, 'revision': revision,
        'form': form, 'error': error, 'unavailable': unavailable, 'record': value, 'response': response,
        'outcome_label': dict(ResponseForm.base_fields['outcome'].choices).get(value['outcome']) if value else None,
        'actual_at': domain.aware(value['responded_at']) if value else None,
        'metadata': metadata, 'proof_files': proof_files, 'signing': signing, 'can_record': can_record,
        'can_adopt': can_record and not adoption and (case.pk, 'baseline.sign') in permissions,
        'adoption': adoption, 'finance_intake': finance_intake, 'packet': packet, 'baseline_current': baseline_current,
        'signature_status': signatures.packet_status(packet) if packet else None,
        'own_test_proof': bool(metadata and metadata.created_by_id == request.user.pk and case.synthetic
                               and (case.pk, 'agent.extract') in permissions),
        'timezone_name': timezone.localtime().tzname(), 'revision_desk': revision_desk,
        'response_is_current_version': bool(response and revision and response.revision_id == revision.pk)})
    result['Cache-Control'] = 'no-store'
    return result


@login_required
@require_safe
@transaction.atomic
def proof(request, case_id, metadata_id, upload_id):
    case = accessible_case(request.user, case_id)
    case = lock_case(request.user, case.pk, 'commercial.read')
    metadata = get_object_or_404(case.evidence.defer('body'), pk=metadata_id)
    rows = domain.proof_rows(request.user, case, metadata)
    upload = next((row for row in rows if row.pk == upload_id), None)
    if upload is None:
        raise PermissionDenied('This file is not proof of the selected client response.')
    result = FileResponse(BytesIO(case_uploads.read(upload)), as_attachment=True, filename=upload.name)
    result['Cache-Control'] = 'no-store'
    return result
