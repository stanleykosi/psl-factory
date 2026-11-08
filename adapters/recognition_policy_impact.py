"""Closed F33 historical-record metadata. No private intent or business effects."""
from django.core.exceptions import PermissionDenied, ValidationError
from apps.policy.services import PolicyHold

def project(row):
    from apps.finance.recognition import record_current
    from apps.finance.recognition_models import ProgressPacket
    current=True
    try:record_current(row)
    except (PermissionDenied,ValidationError,PolicyHold):current=False
    return {'id':row.pk,'kind':'finance.recognition_records','metadata_only':True,
        'domain_route':'recognition','record_kind':row.kind,'packet':row.packet_id,
        'packet_sha256':row.packet.sha256,
        'packet_head':ProgressPacket.objects.filter(case=row.packet.case,reference=row.packet.reference).order_by('-version').values_list('pk',flat=True).first(),
        'record_head':row.packet.records.filter(kind=row.kind).order_by('-pk').values_list('pk',flat=True).first(),
        'native_current':current,'state':'historical_record_requires_reassessment',
        'business_approval':False,'accounting_effects_performed':False}
