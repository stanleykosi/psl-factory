"""Exact private restore descriptors; health/receipt evidence carries no manifest bodies."""
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from apps.documents.contracts import digest
from apps.workflows.operator_models import RecoveryJob
from apps.workflows.operator_inventory import job_access
from apps.workflows import private_readiness_operations as private
from adapters.operator_protection import restore_receipt

class PrivateProtectionReadinessAdapter:
 def job(self,case,pk):
  j=RecoveryJob.objects.select_related('plan__case').filter(pk=pk,plan__case=case,kind='restore',plan__payload__has_key=private.FIELD).exclude(plan__payload__has_key=private.protection.FIELD).first()
  if not j:raise ValidationError('Exact private isolated metadata restore job required')
  return j
 def access(self,actor,job):
  self.job(job.plan.case,job.pk)
  job_access(actor,job.plan.case,'protection',job)
  private.historical(actor,job.plan.case,job.intent['manifest'])
 def describe(self,actor,job):
  self.access(actor,job)
  return {'job':job.pk,'plan':job.plan_id,'case':str(job.plan.case_id),'plan_sha256':job.plan.sha256,'manifest_sha256':digest(job.intent['manifest']),'intent_sha256':digest(job.intent),'packets':private.ids(job.plan),'target_identity':job.intent['target_identity'],'current_authority_restored':False}
 def current(self,actor,job):
  self.access(actor,job)
  from apps.workflows.protection import current_plan
  current_plan(job.plan);private.current(actor,job.plan,job.intent['manifest'])
 def receipts(self,job):
  try:found=restore_receipt(job)
  except DatabaseError:raise ConnectionError('Scoped private protection receipt lookup unavailable') from None
  return {'state':'found' if found else 'not_found','operation_key_sha256':digest(job.operation_key),'manifest_sha256':digest(job.intent['manifest']),'payload_bodies_included':False,'current_authority_restored':False,'full_database_restore':False}
