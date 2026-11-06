"""Closed native receipt observations; no dispatch, arbitrary tools or supplied actuals."""
from django.core.exceptions import ValidationError
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.db import connection,transaction,DatabaseError
from apps.identity.services import require
from apps.documents.contracts import digest
from apps.workflows.operator_inventory import family_access,source_query,job_access

FORMAT='psl.native-validation/v2'
FORMATS=('psl.native-validation/v1',FORMAT)
FAMILIES=('handoff','publication','invoice','engineering','partner','approval','supportresponse','supportchannel','ledgerdata','financefollowup')
SOURCE_TIME={'publication':'publication','engineering':'request','partner':'report','supportresponse':'decision'}


def reserved_at(job,family):
    """Some leased job rows use their immutable reservation subject's creation time."""
    return getattr(job,SOURCE_TIME[family]).created_at if family in SOURCE_TIME else job.created_at


def source(actor,case,family,pk,lock=False):
    if actor is None or not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():raise PermissionDenied('Current native source principal required')
    require(actor,case,'case.read')
    if family not in FAMILIES or type(pk) is not int or pk<1:raise ValidationError('Exact registered native family and job required')
    family_access(actor,case,family) # Check current domain authority before source existence.
    query=source_query(case,family).filter(pk=pk)
    try:
        with transaction.atomic():
            if lock and connection.in_atomic_block:query=query.select_for_update(of=('self',),nowait=True)
            j=query.first()
    except DatabaseError:raise ValidationError('Native source work is being reconciled; refresh the evaluation') from None
    if not j:raise ValidationError('Exact same-case native job required')
    job_access(actor,case,family,j)
    return j


def observe(actor,case,family,pk):
    from apps.workflows.readiness import lookup_source
    j=source(actor,case,family,pk,lock=True)
    receipt=lookup_source(family,j) # Existing source-owned identity/payload/receipt verification only.
    if receipt and family=='invoice' and getattr(receipt,'job_id',j.pk)!=j.pk:
        receipt=None # A canonical receipt belonging to another reservation is not this job's execution.
    proof=None
    if receipt:
        if hasattr(receipt,'_meta'):
            proof={'id':receipt.pk,'sha256':getattr(receipt,'sha256',None)}
        elif isinstance(receipt,(dict,list,str,int)):proof=receipt
        else:raise ValidationError('Native receipt adapter returned an unsupported identity')
    from .native_subjects import observed
    actual={'subject_sha256':observed(case,family,j),'family':family,'operation':getattr(j,'kind',family),'state':j.status,'receipt_present':bool(receipt)}
    head={'job':j.pk,'fence':j.fence,'attempts':j.attempts,'state':j.status,
        'source_reserved_at':reserved_at(j,family).isoformat(),
        'source_sha256':digest(getattr(j,'intent',getattr(j,'payload',{}))),
        'receipt_sha256':digest(proof) if proof is not None else None}
    return actual,head,j


def build():
    from django.conf import settings
    from config.build_identity import identity
    actual=identity(settings.BASE_DIR)
    if settings.PROCESS_BUILD_IDENTITY!=actual:raise ValidationError('Restart the reviewed deployment after source changes before native evaluation')
    return actual
