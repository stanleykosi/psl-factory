"""Record a received bid and its newly delegated workspace as one operation."""

import hashlib
import json
from dataclasses import asdict
from datetime import timezone as datetime_timezone
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from apps.core.models import Audit
from apps.core.services import add_evidence, event, lock_case
from apps.documents.contracts import digest
from apps.identity import intake as identity
from apps.identity.intake_models import CaseIntake, TenantAuthority

from . import rfp, rfp_intake_context, rfp_intake_upload as upload
from .clocks import aware
from .models import RFPIntake


LINE = 'received-bid'
ACTION = 'rfp.fresh_intake_recorded'
GRANTS = frozenset({'case.read', 'rfp.read', 'document.read', 'rfp.intake', 'evidence.add'})
DEADLINE_SOURCE = 'psl:rfp-upload-deadline-observation'
RECEIPT_NOTE = 'The received bid was recorded with its original private document.'


def available(actor):
    """Find current eligible organizations in one query for the Start work menu."""
    if not actor.is_authenticated or not actor.is_active:
        return TenantAuthority.objects.none()
    latest = TenantAuthority.objects.filter(user=actor, tenant=OuterRef('tenant')).order_by('-version').values('pk')[:1]
    return TenantAuthority.objects.filter(user=actor, user__is_active=True, pk=Subquery(latest),
        enabled=True, expires_at__gt=timezone.now(), value__create_cases=True, value__kinds__contains=['project'],
        value__initial_actions__contains=sorted(GRANTS)).order_by('tenant')


def replay(actor, provisioned, payload_hash, fingerprint, size, classification):
    case = lock_case(actor, provisioned.case_id, 'rfp.intake')
    upload.authorize_write(actor, case)
    if provisioned.actor_id != actor.pk or case.synthetic != (classification == 'synthetic'):
        raise PermissionDenied('Current exact workspace access is required.')
    receipt = Audit.objects.filter(case=case, actor=actor, action=ACTION,
        data__case_intake=provisioned.pk, data__sha256=payload_hash).first()
    if receipt is None:
        raise ValidationError('This start request already has different details. Start a new request for a different bid.')
    original = RFPIntake.objects.select_related('rfp', 'actor').defer('actor__password').filter(
        pk=receipt.data['intake'], actor=actor, number=1, rfp__case=case, rfp__tenant=case.tenant).first()
    attachment = upload.attachment_for(actor, case, original) if original else None
    if attachment is None or (attachment.sha256, attachment.size) != (fingerprint, size):
        raise ValidationError('The original bid receipt needs review before continuing.')
    return original


def record(actor, authority_id, start_key, reference, received_at, deadline_status, deadline_at, file,
           *, source_context=None, context_attested=False):
    if type(authority_id) is not int or not isinstance(start_key, UUID) or not isinstance(reference, str):
        raise ValidationError('Choose the organization and enter a bid reference.')
    reference = reference.strip()
    if not reference or len(reference) > 160 or not reference.isprintable():
        raise ValidationError('Enter a bid reference of at most 160 characters.')
    try:
        with upload.durable_upload() as store:
            identity.lock_users([actor.pk])
            selected = TenantAuthority.objects.filter(user=actor, pk=authority_id).only('tenant').first()
            if selected is None:
                raise PermissionDenied('Current organization authority is required.')
            current = identity.current(actor, selected.tenant, 'create_cases')
            if current.pk != authority_id or 'project' not in current.value['kinds'] or not GRANTS <= set(current.value['initial_actions']):
                raise PermissionDenied('Current authority to record a bid in a new workspace is required.')

            received = aware(received_at, 'Received time').astimezone(datetime_timezone.utc)
            rfp.past(received)
            if deadline_status not in ('unknown', 'stated', 'not_stated') or (deadline_status == 'stated') != (deadline_at is not None):
                raise ValidationError('Enter the deadline only when it is stated in the document.')
            deadline = aware(deadline_at, 'Deadline').astimezone(datetime_timezone.utc) if deadline_at is not None else None
            context = rfp_intake_context.validate(source_context, context_attested)
            data = upload.read_file(file)
            fingerprint = hashlib.sha256(data).hexdigest()
            payload_hash = digest({'reference': reference, 'received': received.isoformat(),
                'deadline_status': deadline_status, 'deadline': deadline.isoformat() if deadline else None,
                'context': asdict(context), 'file_sha256': fingerprint, 'file_size': len(data)})
            start_reference = 'received-bid:' + digest([actor.pk, start_key.hex])
            old = CaseIntake.objects.filter(tenant=current.tenant, reference=start_reference).first()
            if old is not None:
                return replay(actor, old, payload_hash, fingerprint, len(data), current.value['classification'])

            upload.validate_file(file.name, data)
            case = identity.create_case(actor, current.tenant, start_reference, 'Bid ' + reference, 'project')
            upload.authorize_write(actor, case)
            deadline_proof = None
            if deadline:
                # The recorder supplies the observed time while admitting this exact document.
                deadline_proof = add_evidence(actor, case.pk, 'rfp_deadline', json.dumps({
                    'schema': 'psl.rfp-upload-deadline-observation/v1', 'deadline': deadline.isoformat(),
                    'attachment_sha256': fingerprint,
                }, sort_keys=True), DEADLINE_SOURCE, case.revision)
                case.refresh_from_db(fields=['revision'])
            facts = (reference, received, deadline_status, deadline,
                     deadline_proof.pk if deadline_proof else None, RECEIPT_NOTE)
            intake = upload.persist(actor, case, facts, file.name, data, fingerprint, store,
                                    context=context, context_attested=context_attested)
            event(actor, case, ACTION, case_intake=case.caseintake.pk, intake=intake.pk, sha256=payload_hash)
            return intake
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.__cause__, 'diag', None), 'constraint_name', '')
        if constraint in {'tenant_intake_reference', 'rfp_tenant_reference'}:
            raise ValidationError('This bid reference is already recorded for the organization.') from exc
        raise
