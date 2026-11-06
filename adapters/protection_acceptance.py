"""Closed native restore or explicit versioned file capability proof; no source bodies."""
from django.core.exceptions import ValidationError,PermissionDenied
from apps.identity.services import require
from apps.workflows import readiness as r,private_protection_readiness as native
from apps.documents.contracts import digest

class ProtectionAcceptanceAdapter:
 def access(self,actor,assessment):
  if actor is None:raise PermissionDenied('Actual private protection principal required')
  r.readable(actor,assessment.contract.case,True);require(actor,assessment.contract.case,'validation.read')
  from apps.workflows import private_file_readiness as file
  b=native.binding(assessment.contract) or file.binding(assessment.contract)
  if not b:raise ValidationError('Exact native private protection readiness source required')
  (native if b.job.kind=='restore' else file).access(actor,b);return b
 def read(self,actor,assessment):
  b=self.access(actor,assessment)
  if b.job.kind in ['export','backup']:return self.file_read(actor,assessment,b)
  native.check(actor,assessment.contract);review=r.review_current(assessment);rows=[];receipt=None
  for kind in ['health','receipt']:
   o=r.IntegrationObservation.objects.filter(contract=assessment.contract,payload__kind=kind).order_by('-pk').first()
   if not o or not o.job_id or o.sha256!=digest(o.payload):raise ValidationError('Exact native protection observation/hash required')
   if kind=='receipt':receipt=o.payload['receipt_provenance']['state']
   rows.append({'kind':kind,'observation':o.pk,'sha256':o.sha256,'probe':o.job_id})
  return {'assessment':assessment.pk,'contract':assessment.contract_id,'contract_sha256':assessment.contract.sha256,'readiness_policy':review.authority['policy'],'transport_review':review.pk,'transport_reviewer':review.actor_id,'binding':b.pk,'binding_sha256':b.sha256,'restore_job':b.job_id,'plan':b.job.plan_id,'manifest_sha256':b.snapshot['manifest_sha256'],'observations':rows,'receipt_state':receipt,'classification':'native_private_restore_capability_metadata','payload_bodies_included':False,'current_authority_restored':False,'full_database_restore':False,'business_acceptance':False,'operational_acceptance':False,'deployment_authorized':False}

 def file_read(self,actor,assessment,b):
  from apps.workflows import private_file_readiness as file
  file.check(actor,assessment.contract);review=r.review_current(assessment);rows=[];receipt=None
  for kind in ['health','receipt']:
   o=r.IntegrationObservation.objects.filter(contract=assessment.contract,payload__kind=kind).order_by('-pk').first()
   if not o or not o.job_id or o.sha256!=digest(o.payload):raise ValidationError('Exact native file observation/hash required')
   if kind=='receipt':receipt=o.payload['file_receipt_provenance']['state']
   rows.append({'kind':kind,'observation':o.pk,'sha256':o.sha256,'probe':o.job_id})
  return {'schema_ref':'schema:psl/private-file-acceptance-evidence/v1','assessment':assessment.pk,'contract':assessment.contract_id,'contract_sha256':assessment.contract.sha256,'readiness_policy':review.authority['policy'],'transport_review':review.pk,'transport_reviewer':review.actor_id,'binding':b.pk,'binding_sha256':b.sha256,'file_job':b.job_id,'job_kind':b.job.kind,'plan':b.job.plan_id,'plan_sha256':b.snapshot['plan_sha256'],'intent_sha256':b.snapshot['intent_sha256'],'manifest_sha256':b.snapshot['manifest_sha256'],'storage_identity':b.snapshot['storage_identity'],'source_packets':b.snapshot['packets'],'observations':rows,'receipt_state':receipt,'classification':'native_private_file_capability_metadata','payload_bodies_included':False,'current_authority_restored':False,'full_database_backup':False,'full_database_export':False,'business_acceptance':False,'operational_acceptance':False,'deployment_authorized':False}
