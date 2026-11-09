"""Selected original packet policy validity, never baseline or signing authority."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from apps.identity.services import require
from apps.pmo.models import CommercialSignaturePacket
from apps.policy.signature_validators import COMPONENT

KEY='pmo.signature_packets'
AUTHORITY='D05.role_principal_assignments'

def readable(actor,case):
    if actor is None or not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():
        raise PermissionDenied('Current commercial metadata observer required')
    require(actor,case,'case.read');require(actor,case,'commercial.read')

def query(actor,config):
    readable(actor,config.case)
    rows=CommercialSignaturePacket.objects.filter(case=config.case)
    if config.component==COMPONENT:return rows.filter(policy_id=config.pk).order_by('pk')
    if config.component==AUTHORITY:return rows.filter(authority_id=config.pk).order_by('pk')
    return rows.none()

def authorize_row(actor,case,row):
    readable(actor,case)
    if row.case_id!=case.pk:raise PermissionDenied('Select this case signature packet metadata')

def project(row):
    from apps.pmo.signatures import validate_packet_policy
    from apps.documents.contracts import digest
    from apps.policy.services import PolicyHold
    try:validate_packet_policy(row);valid=True
    except (PermissionDenied,ValidationError,PolicyHold):valid=False
    fingerprint=digest({'sources':row.sources,'signatures':row.signatures,'revision':row.revision_id,
        'policy':row.policy_id,'authority':row.authority_id,'actor':row.actor_id})
    return {'id':row.pk,'kind':KEY,'metadata_only':True,'domain_route':'commercial',
        'revision':row.revision_id,'policy':row.policy_id,'authority':row.authority_id,
        'packet_sha256':fingerprint,'packet_policy_valid_now':valid,
        'state':'historical_packet_policy_observation','signature_authenticity_verified':False,
        'signing_authorized':False,'effects_performed':False}
