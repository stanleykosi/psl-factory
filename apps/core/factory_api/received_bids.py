"""The same private bid intake and current organisation delegation as Start work."""
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from apps.pmo import rfp_fresh_intake, rfp_intake_context
from apps.workflows.factory_fresh_bid_views import ReceivedBidForm
from .http import BOOLEAN, DATETIME, ID, TEXT, UUID, Problem, array, choice, endpoint, obj


@endpoint(response=obj({'items': array(obj({'id': ID, 'organisation': TEXT}))}),
          summary='List organisations where you can record a received bid')
def organisations(request):
    return {'items': [{'id': pk, 'organisation': tenant} for pk, tenant in
                      rfp_fresh_intake.available(request.user).values_list('pk', 'tenant')]}


@endpoint(method='POST', multipart=True, request=obj({'authority': ID, 'start_key': UUID, 'reference': TEXT,
    'received_at': DATETIME, 'deadline_status': choice('unknown','stated','not_stated'), 'deadline_at': DATETIME,
    'prospect_name': TEXT, 'submission_method': choice(*(v for v, _ in rfp_intake_context.METHODS)),
    'submission_target': TEXT, 'context_attested': BOOLEAN, 'document': {'type':'string','format':'binary'}},
    optional=('deadline_at','prospect_name','submission_method','submission_target','context_attested')),
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
