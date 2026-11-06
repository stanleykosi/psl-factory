"""Closed metadata projection of native capability proof, never a business acceptance."""
from django.core.exceptions import ValidationError,PermissionDenied
from apps.identity.services import require
from apps.workflows import readiness as r
from apps.finance import publication_readiness as native
from apps.documents.contracts import digest

class PrivateReadinessEvidenceAdapter:
 def access(self,actor,assessment):
  if actor is None:raise PermissionDenied("Actual private readiness principal required")
  r.readable(actor,assessment.contract.case,True)
  require(actor,assessment.contract.case,'validation.read')
  b=native.binding(assessment.contract)
  if not b:raise ValidationError('Native private Finance readiness source required')
  native.access(actor,b)
  return b
 def read(self,actor,assessment):
  b=self.access(actor,assessment);native.check(actor,assessment.contract)
  review=r.review_current(assessment)
  rows=[];receipt=None
  for kind in ['health','receipt']:
   o=r.IntegrationObservation.objects.filter(contract=assessment.contract,payload__kind=kind).order_by('-pk').first()
   if not o or not o.job_id or o.sha256!=digest(o.payload):raise ValidationError('Exact native observation/hash required')
   if kind=='receipt':receipt=o.payload['receipt_provenance']['state']
   rows.append({'kind':kind,'observation':o.pk,'sha256':o.sha256,'probe':o.job_id})
  return {'assessment':assessment.pk,'contract':assessment.contract_id,'contract_sha256':assessment.contract.sha256,'readiness_policy':review.authority['policy'],'transport_review':review.pk,'transport_reviewer':review.actor_id,'binding':b.pk,'binding_sha256':b.sha256,'publication_job':b.job_id,'observations':rows,'receipt_state':receipt,'classification':'native_internal_capability_metadata','payload_bodies_included':False,'business_acceptance':False,'operational_acceptance':False,'deployment_authorized':False}
