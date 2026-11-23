"""The same private bid intake and current organisation delegation as Start work."""
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse

from apps.core.views import accessible_case
from apps.pmo import rfp_fresh_intake, rfp_intake_context, rfp_intake_upload
from apps.pmo.models import RFPIntake
from apps.workflows.factory_fresh_bid_views import ReceivedBidForm
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, Problem, array, choice, endpoint, nullable, obj


METHOD = choice(*(value for value, _ in rfp_intake_context.METHODS))
FACTS = obj({'prospect_name': nullable(TEXT), 'submission_method': nullable(METHOD),
             'submission_target': nullable(TEXT), 'source_version': REVISION})


@endpoint(response=obj({'id': ID, 'case_id': UUID, 'reference': TEXT, 'number': REVISION, 'current': BOOLEAN,
                        'received_at': DATETIME, 'deadline_status': choice('unknown', 'stated', 'not_stated'),
                        'deadline_at': nullable(DATETIME), 'customer_instructions': nullable(FACTS), 'note': nullable(TEXT),
                        'original': obj({'filename': TEXT, 'bytes': ID, 'download_url': TEXT})}),
          summary='Read one exact private received bid receipt and its authorised original file link')
def receipt(request, case_id, receipt_id):
    actor = request.user
    case = accessible_case(actor, case_id)
    rfp_intake_upload.require_read(actor, case)
    intake = get_object_or_404(RFPIntake.objects.select_related('rfp', 'actor').defer('actor__password'),
                               rfp__case=case, pk=receipt_id)
    attachment = rfp_intake_upload.attachment_for(actor, case, intake)
    if attachment is None:
        raise Http404('Bid document unavailable.')
    visible = rfp_intake_context.visible(actor, case, intake)
    instructions = None
    if visible:
        facts = visible['facts']
        instructions = {'prospect_name': facts.prospect_name, 'submission_method': facts.submission_method,
                        'submission_target': facts.submission_target, 'source_version': visible['source_version']}
    return {'id': intake.pk, 'case_id': case.pk, 'reference': intake.rfp.reference, 'number': intake.number,
            'current': intake.pk == intake.rfp.current_intake_id, 'received_at': intake.received_at,
            'deadline_status': intake.deadline_status, 'deadline_at': intake.deadline_at,
            'note': intake.note if intake.note and intake.note != rfp_fresh_intake.RECEIPT_NOTE else None,
            'customer_instructions': instructions, 'original': {'filename': attachment.name, 'bytes': attachment.size,
                'download_url': reverse('rfp_intake_attachment', args=[case.pk, intake.pk])}}


@endpoint(response=obj({'items': array(obj({'id': ID, 'organisation': TEXT}))}),
          summary='List organisations where you can record a received bid')
def organisations(request):
    return {'items': [{'id': pk, 'organisation': tenant} for pk, tenant in
                      rfp_fresh_intake.available(request.user).values_list('pk', 'tenant')]}


@endpoint(method='POST', multipart=True, request=obj({
    'authority': ID, 'start_key': UUID, 'reference': {**TEXT, 'maxLength': 160},
    'note': {'type': 'string', 'maxLength': 4000},
    'received_at': DATETIME, 'deadline_status': choice('unknown', 'stated', 'not_stated'),
    'deadline_at': {'anyOf': [DATETIME, {'type': 'string', 'const': ''}],
                    'description': 'Required for a stated deadline. Otherwise omit it or send the native form’s empty value.'},
    'prospect_name': {**TEXT, 'maxLength': 160}, 'submission_method': METHOD,
    'submission_target': TEXT,
    'context_attested': {'anyOf': [BOOLEAN, {'type': 'string', 'const': 'on'}]},
    'document': {'type': 'string', 'format': 'binary', 'description': 'Original private Word or PDF file, up to 5 MiB.'},
    'definition': {'type': 'string', 'const': rfp_fresh_intake.LINE, 'deprecated': True,
                   'description': 'The optional hidden identifier sent by the existing Django form.'},
}, optional=('deadline_at', 'prospect_name', 'submission_method', 'submission_target', 'context_attested', 'definition', 'note')),
    response=obj({'receipt_id': ID, 'case_id': UUID, 'django_url': TEXT}), summary='Record the bid with its original private file')
def record(request):
    scopes = list(rfp_fresh_intake.available(request.user).only('pk','tenant'))
    if not scopes:
        raise PermissionDenied
    if request.content_type != 'multipart/form-data':
        raise Problem(415, 'unsupported_media_type', 'Send the bid document as a multipart upload.')
    form = ReceivedBidForm(scopes, request.POST, request.FILES)
    if not form.is_valid():
        fields = [{'name': key, 'message': str(message)} for key, errors in form.errors.items() for message in errors]
        raise Problem(422, 'invalid_input', 'Check the bid details.', fields=fields)
    receipt = form.record(request.user)
    return {'receipt_id': receipt.pk, 'case_id': receipt.rfp.case_id,
            'django_url': f"{reverse('rfp', args=[receipt.rfp.case_id])}?received={receipt.pk}"}
