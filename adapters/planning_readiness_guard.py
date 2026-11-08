"""ID-only planning preparation preview, not owner approval or native verification."""
from django.core.exceptions import PermissionDenied
from apps.core.models import Audit, Evidence
from apps.documents.contracts import digest
from apps.identity.services import require
from apps.pmo import planning, approvals
from apps.pmo.models import ApprovalRequest


def readable(observer, case, args):
    planning.readable(observer, case)
    approvals.readable(observer, case)
    # Access before projection, independent of freshness failures in another
    # request. Do not stop checking later source grants on an earlier stale item.
    packet = Evidence.objects.filter(case=case, pk=args['planning_packet_id'], kind=planning.KINDS['packet']).first()
    if not packet:
        raise PermissionDenied('Permitted planning packet required')
    marker = Audit.objects.filter(case=case, action='planning.requests_opened', data__packet_id=packet.pk).order_by('-pk').first()
    if marker:
        value = marker.data
        ids = value.get('requests')
        if not isinstance(ids, dict) or set(ids) != set(planning.SUBJECTS) or any(type(i) is not int for i in ids.values()):
            raise PermissionDenied('Permitted source scope required')
        for key, pk in ids.items():
            request = ApprovalRequest.objects.filter(case=case, pk=pk, candidate_id=value.get('candidate_id'), kind=planning.SUBJECTS[key]).first()
            if not request:
                raise PermissionDenied('Permitted source scope required')
            receipt = request.source_receipts.order_by('-pk').first()
            if receipt:
                require(observer, case, 'approval.source.read:'+receipt.system)
    return packet


def guard(actor, case, planning_packet_id):
    readable(actor, case, {'planning_packet_id':planning_packet_id})
    packet, value, old = planning.guard_prepare(actor, case, planning_packet_id)
    return packet, {'packet_id':packet.pk, 'packet_sha256':packet.sha256,
        'readiness_inputs_sha256':digest(value) if value is not None else digest(planning.read(case,old,'ready','prepare')),
        'existing_readiness_id':old.pk if old else None, 'business_approval':False,
        'native_verified':False, 'scope':'planning_prepare_readonly'}, None


def head(observer, case, args):
    packet=readable(observer, case, args)
    return {'packet_id':packet.pk,'packet_sha256':packet.sha256}


def choices(observer,case):
    planning.readable(observer,case);approvals.readable(observer,case)
    ids=[]
    for pk in Evidence.objects.filter(case=case,kind=planning.KINDS['packet']).order_by('-pk').values_list('pk',flat=True)[:200]:
        try:readable(observer,case,{'planning_packet_id':pk})
        except PermissionDenied:continue
        ids.append(pk)
    return Evidence.objects.filter(case=case,pk__in=ids)
