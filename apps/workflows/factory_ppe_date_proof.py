"""Private PDF evidence for one immutable asset date fact."""

import hashlib
import logging
import re
import secrets

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction

from adapters import case_uploads
from apps.core.evidence_access import PPE_ASSET_DATES_SOURCE
from apps.core.models import Audit, Evidence
from apps.core.services import event
from apps.finance import ppe, ppe_dates
from apps.identity.services import require

from . import factory, factory_ppe
from .factory_ppe_opening import OpeningProof, pdf_bytes


ATTACHED = 'factory.ppe_date_proof_attached'
LOGGER = logging.getLogger(__name__)


def record(actor, case_id, register_id, asset_id, delivery_date, in_service_date, fraction_basis, evidence_id,
           expected, uploaded):
    if uploaded is None:
        return ppe.record_dates(actor, case_id, register_id, asset_id, delivery_date, in_service_date, fraction_basis,
                                evidence_id, expected)
    staged_key = None
    try:
        with transaction.atomic(durable=True):
            case = ppe.locked(actor, case_id, 'ppe.capture', expected)
            require(actor, case, 'evidence.add')
            name, data = pdf_bytes(uploaded)
            support = ppe_dates.support(case, evidence_id)
            successor = ppe.record_dates(actor, case.pk, register_id, asset_id, delivery_date, in_service_date,
                                         fraction_basis, support.pk, case.revision)
            dates = next(asset['dates'] for asset in successor.payload['assets'] if asset['asset_id'] == asset_id)
            fact = Evidence.objects.only('id', 'sha256').get(case=case, pk=dates['evidence_id'],
                kind=ppe_dates.FACT_KIND, source=PPE_ASSET_DATES_SOURCE, created_by=actor)
            key = 'ppe-date-' + secrets.token_hex(32)
            event(actor, case, ATTACHED, register=successor.pk, fact=fact.pk, fact_sha256=fact.sha256,
                  support=support.pk, support_sha256=support.sha256, storage_key=key,
                  name=name, size=len(data), sha256=hashlib.sha256(data).hexdigest())
            staged_key = key
            case_uploads.put(key, data)
        return successor
    except Exception as exc:
        if staged_key:
            try:
                if not Audit.objects.filter(case_id=case_id, action=ATTACHED, data__storage_key=staged_key).exists():
                    case_uploads.discard_unbound(staged_key)
            except (DatabaseError, OSError, ValidationError):
                LOGGER.warning('Private asset date proof in workspace %s needs storage reconciliation', case_id)
        if isinstance(exc, OSError):
            raise ValidationError('Private storage is unavailable. Try again later.') from exc
        raise


def attachments_for(actor, work, register):
    factory.access(actor, work.case, 'factory.read', factory_ppe.DEFINITION)
    require(actor, work.case, 'ppe.report')
    if register.case_id != work.case_id or register.reference != work.request['register_reference']:
        return {}
    dated = {asset['dates']['evidence_id']: asset for asset in register.payload['assets'] if asset.get('dates')}
    if not dated:
        return {}
    receipts = list(Audit.objects.filter(case=work.case, action=ATTACHED, data__fact__in=list(dated))
                    .only('actor_id', 'data').order_by('pk')[:len(dated) + 1])
    if not receipts or len({receipt.data['fact'] for receipt in receipts}) != len(receipts):
        return {}
    selected, _ = factory_ppe.source(work, actor)
    if selected.pk != register.pk:
        return {}
    assets = [dated[receipt.data['fact']] for receipt in receipts]
    ppe_dates.checked_sources(work.case, assets, check_values=True)
    support_ids = {asset['dates']['support_evidence_id'] for asset in assets}
    metadata = {pk: (author, sha) for pk, author, sha in Evidence.objects.filter(case=work.case,
        pk__in=set(dated) | support_ids).values_list('pk', 'created_by_id', 'sha256')}
    attachments = {}
    for receipt in receipts:
        data = receipt.data
        fact = data['fact']
        support = dated[fact]['dates']['support_evidence_id']
        if (metadata.get(fact) != (receipt.actor_id, data['fact_sha256']) or data['support'] != support
                or support not in metadata or metadata[support][1] != data['support_sha256']):
            continue
        name, key, size, sha = (data.get(field) for field in ('name', 'storage_key', 'size', 'sha256'))
        if (isinstance(name, str) and name.lower().endswith('.pdf') and len(name) <= 160
                and isinstance(key, str) and re.fullmatch(r'ppe-date-[0-9a-f]{64}', key)
                and type(size) is int and 0 < size <= case_uploads.LIMIT
                and isinstance(sha, str) and re.fullmatch(r'[0-9a-f]{64}', sha)):
            attachments[fact] = OpeningProof(name, key, size, sha)
    return attachments
