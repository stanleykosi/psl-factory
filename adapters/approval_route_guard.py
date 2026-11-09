"""P02 routing preview: exact native reads, never a reservation or owner approval."""
from apps.pmo import approvals, approval_routing
from apps.pmo.models import ApprovalRequest, ApprovalRouteJob, ApprovalRouteReceipt
from apps.policy.approval_validators import ROUTES, CONTRACTS


def readable(actor, case):
    approvals.readable(actor, case)


def choices(actor, case):
    readable(actor, case)
    return ApprovalRequest.objects.filter(case=case).order_by('pk')


def guard(actor, case, approval_request_id, approval_purpose):
    request_id, purpose = approval_request_id, approval_purpose
    request, intent, existing, generation = approval_routing.guard_reserve(actor, case, request_id, purpose)
    # Never return owner names, subject/source content, or the dispatch intent.
    context = {ROUTES: intent['policies'][0], CONTRACTS: intent['policies'][1],
        'request_id': request.pk, 'request_version': request.version,
        'contract_review_id': intent['contract_review'], 'recipient_id': intent['recipient'],
        'authority': intent['authority'], 'purpose': purpose, 'generation': generation,
        'approval_granted': False, 'effects_scheduled': False,
        'scope': 'native_internal_approval_routing_only'}
    return request, context, existing


def head(actor, case, request_id):
    readable(actor, case)
    request = ApprovalRequest.objects.filter(case=case, pk=request_id).first()
    if not request:
        return None
    latest = ApprovalRequest.objects.filter(case=case, reference=request.reference).order_by('-version').first()
    job = ApprovalRouteJob.objects.filter(request=request).order_by('-generation').first()
    receipt = ApprovalRouteReceipt.objects.filter(job__request=request).order_by('-created_at').first()
    return {'request': request.pk, 'version': request.version, 'current_request': latest.pk,
        'candidate': request.candidate_id, 'requirements': request.candidate.requirements_id,
        'job': [job.pk, job.status, job.fence, job.attempts] if job else None,
        'receipt': receipt.pk if receipt else None,
        'reminder_receipts': ApprovalRouteReceipt.objects.filter(job__request=request, job__purpose='reminder').count(),
        'approval_granted': False, 'effects_scheduled': False}
