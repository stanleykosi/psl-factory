"""Read-only native publication descriptors and receipt provenance; no outward payload copies."""
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from apps.documents.models import PublicationJob,PublicationReceipt
from apps.documents.contracts import digest
from apps.finance import accepted_documents as publication

class FinancePublicationReadinessAdapter:
 def job(self,case,pk):
  j=PublicationJob.objects.select_related('publication__version__document__case','publication__version__template').filter(pk=pk,publication__version__document__case=case).first()
  if not j or not publication.binding(j.publication.version):raise ValidationError('Exact native Finance metadata publication job required')
  return j
 def access(self,actor,job):publication.access(actor,publication.binding(job.publication.version))
 def describe(self,actor,job):
  self.access(actor,job);p=job.publication;b=publication.binding(p.version)
  return {'job':job.pk,'publication':p.pk,'case':str(p.version.document.case_id),'version':p.version_id,'native_binding':b.pk,'native_binding_sha256':b.sha256,'payload_sha256':p.version.payload_sha256,'review':p.review_id,'publisher':p.actor_id,'policies':p.policies,'recipients':p.recipient_ids,'retention_days':p.retention_days}
 def receipts(self,job):
  from adapters.publications import InternalPublicationAdapter
  try:
   found=InternalPublicationAdapter().lookup(job.publication)
   rows=list(PublicationReceipt.objects.filter(publication=job.publication).order_by('recipient_id').values('id','recipient_id','payload_sha256'))
  except DatabaseError:raise ConnectionError('Scoped native publication receipt lookup unavailable') from None
  return {'state':'found' if found else 'not_found','operation_key_sha256':digest(job.publication.operation_key),'receipts':rows,'payload_bodies_included':False,'external_delivery_verified':False}
