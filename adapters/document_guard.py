"""Native publication guard metadata; no payload, release, retry or effect tools."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from apps.identity.services import require
from apps.documents.models import Version,Publication,PublicationJob


def readable(actor,case,version_id):
    if not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():raise PermissionDenied('Current document observer required')
    for action in ['case.read','document.read']:require(actor,case,action)
    row=Version.objects.select_related('document__case','template').filter(document__case=case,pk=version_id).first()
    if row:
        from apps.finance.accepted_documents import binding,access
        bound=binding(row)
        if bound:access(actor,bound)
        from apps.finance.documents import binding_for
        if binding_for(row):require(actor,case,'finance.read')
    return row


def choices(actor,case):
    for action in ['case.read','document.read']:require(actor,case,action)
    ids=[]
    for row in Version.objects.filter(document__case=case).exclude(template__definition__document_type='accepted_finance_metadata').only('pk'):
        try:readable(actor,case,row.pk)
        except PermissionDenied:continue
        ids.append(row.pk)
    return Version.objects.filter(document__case=case,pk__in=ids)


def head(actor,case,version_id):
    from adapters.publications import InternalPublicationAdapter
    from apps.policy.impact import digest
    row=readable(actor,case,version_id)
    if not row:return None,{}
    review=row.reviews.order_by('-pk').first();publication=Publication.objects.filter(version=row).first()
    job=PublicationJob.objects.filter(publication=publication).first() if publication else None
    state='not_reserved'
    if publication:
        try:state='verified_internal_receipt' if InternalPublicationAdapter().lookup(publication) else 'no_verified_receipt'
        except ValidationError:state='receipt_conflict_requires_reconciliation'
    return {'version':row.pk,'document':row.document_id,'current':row.document.current_id,'payload_sha256':row.payload_sha256,
        'review':review.pk if review else None,'review_verdict':review.verdict if review else None,
        'publication':publication.pk if publication else None,
        'job':[job.pk,job.status,job.fence,job.attempts] if job else None,'receipt_state':state,
        'receipt_identity_sha256':digest(list(publication.publicationreceipt_set.order_by('pk').values_list('pk','payload_sha256'))) if publication else None,
        'scope':'native_internal_publication_only'},review.authority if review else {}
