"""Private file provenance for one supplied incumbent observation."""
from dataclasses import dataclass
import hashlib
import logging
import re
import secrets

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction

from adapters import case_uploads
from apps.core.models import Audit
from apps.core.services import event
from apps.finance import ledger
from apps.identity.services import require
from . import factory, factory_ledger as flow
from .factory_ppe_opening import pdf_bytes
from .models import FactoryWork


ATTACHED = 'factory.ledger_observation_proof_attached'
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Proof:
    name: str
    key: str
    size: int
    sha256: str


def proof_name(name):
    name = name.replace('\\', '/').rsplit('/', 1)[-1]
    if not name.lower().endswith(('.png', '.pdf')) or len(name)>160 or any(ord(value)<32 for value in name):
        raise ValidationError('Choose one PNG or PDF proof with a valid filename.')
    return name


def proof_bytes(file):
    if file is None or not 0<file.size<=case_uploads.LIMIT:
        raise ValidationError('Choose one PNG or PDF proof file up to 5 MiB.')
    name = proof_name(file.name)
    if name.lower().endswith('.pdf'):
        return pdf_bytes(file)
    data = file.read(case_uploads.LIMIT + 1)
    if (len(data)!=file.size or not data.startswith(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR')
            or not data.endswith(b'\x00\x00\x00\x00IEND\xae\x42\x60\x82')):
        raise ValidationError('Choose a valid PNG screenshot.')
    return name, data


def key_prefix(work, check):
    return f'ledger-observation-{work.pk}-{check.pk}-'


def record(actor, work_id, revision, case_revision, target, evidence, outcome, uploaded):
    if outcome not in {'found','not_found','unknown','multiple'}:
        raise ValidationError('Select the exact outcome described in the structured observation.')
    key = None
    try:
        with transaction.atomic(durable=True):
            work = FactoryWork.objects.select_for_update(of=('self',)).select_related('case','source_head').get(
                pk=work_id, definition=flow.DEFINITION)
            factory.access(actor,work.case,'ledger.verify',flow.DEFINITION)
            require(actor,work.case,'evidence.add')
            name, data = proof_bytes(uploaded)
            check = flow.command(actor,work.pk,revision,case_revision,'observe',target,evidence,outcome=outcome)
            key = key_prefix(work,check) + secrets.token_hex(24)
            event(actor,work.case,ATTACHED,work=work.pk,source_head=work.source_head_id,lineage=check.lineage_id,
                  check=check.pk,observation_evidence=check.evidence_id,observation_sha256=check.evidence.sha256,
                  name=name,storage_key=key,sha256=hashlib.sha256(data).hexdigest(),size=len(data))
            case_uploads.put(key,data)
        return check
    except Exception as exc:
        if key:
            try:
                if not Audit.objects.filter(action=ATTACHED,data__storage_key=key).exists():
                    case_uploads.discard_unbound(key)
            except (DatabaseError,OSError,ValidationError):
                LOGGER.warning('Private observation proof for work %s needs storage reconciliation',work_id)
        if isinstance(exc,OSError):
            raise ValidationError('Private proof storage is unavailable. Try again later.') from exc
        raise


def attachment_for(actor, work, check):
    factory.access(actor,work.case,'factory.read',flow.DEFINITION)
    pin = Audit.objects.filter(case=work.case,action=ATTACHED,actor_id=check.actor_id,data__work=work.pk,
        data__source_head=work.source_head_id,data__lineage=check.lineage_id,data__check=check.pk,
        data__observation_evidence=check.evidence_id,data__observation_sha256=check.evidence.sha256
    ).values_list('data',flat=True).first()
    if not pin:
        return None
    lineage = flow.match(work,flow.lineage(work),actor)
    if check.lineage_id!=lineage.pk:
        return None
    flow.readable(lineage.actor,work.case)
    require(lineage.actor,work.case,'ledger.capture')
    flow.readable(check.actor,work.case)
    require(check.actor,work.case,'ledger.verify')
    require(check.actor,work.case,'evidence.add')
    if actor.pk!=check.actor_id:
        ledger.authority(actor,check)
    key = pin.get('storage_key')
    size = pin.get('size')
    digest = pin.get('sha256')
    name = pin.get('name')
    if (not isinstance(key,str) or not re.fullmatch(re.escape(key_prefix(work,check))+r'[0-9a-f]{48}',key)
            or not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest)
            or type(size) is not int or not 0<size<=case_uploads.LIMIT
            or not isinstance(name,str) or proof_name(name)!=name):
        return None
    return Proof(name,key,size,digest)
