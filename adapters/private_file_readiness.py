"""Native SQL export and sealed backup receipt capabilities; never returns source bodies."""
import os
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from apps.documents.contracts import digest
from apps.workflows.operator_models import RecoveryJob,RecoveryArtifact
from apps.workflows.operator_inventory import job_access
from apps.workflows import private_readiness_operations as private
from adapters import operator_protection as storage

class PrivateFileReadinessAdapter:
 def job(self,c,pk):
  j=RecoveryJob.objects.select_related('plan__case').filter(pk=pk,plan__case=c,kind__in=['export','backup'],plan__payload__has_key=private.FIELD).exclude(plan__payload__has_key=private.protection.FIELD).first()
  if not j:raise ValidationError('Exact private metadata export or file backup job required')
  return j
 def access(self,a,j):
  self.job(j.plan.case,j.pk)
  job_access(a,j.plan.case,'protection',j);private.historical(a,j.plan.case,j.intent['manifest'])
 def describe(self,a,j):
  self.access(a,j)
  return {'job':j.pk,'job_kind':j.kind,'plan':j.plan_id,'case':str(j.plan.case_id),'plan_sha256':j.plan.sha256,'manifest_sha256':digest(j.intent['manifest']),'intent_sha256':digest(j.intent),'packets':private.ids(j.plan),'storage_identity':j.intent['storage_identity'],'current_authority_restored':False}
 def health(self,j):
  if storage.storage_identity()!=j.intent['storage_identity']:raise ConnectionError('Reserved metadata storage identity changed')
  if j.kind=='export':return {'storage_probe':'not_applicable_sql_export','storage_write_proven':False}
  try:
   root=storage.storage_root()
   if not root.is_dir() or root.is_symlink():raise ConnectionError('Sealed metadata storage unavailable')
   with os.scandir(root) as entries:next(entries,None)
  except OSError:raise ConnectionError('Sealed metadata storage read capability unavailable') from None
  return {'storage_probe':'read_only_directory_inventory','storage_write_proven':False}
 def current(self,a,j):
  self.access(a,j)
  from apps.workflows.protection import current_plan
  current_plan(j.plan);private.current(a,j.plan,j.intent['manifest']);self.health(j)
 def receipts(self,j):
  try:artifact=RecoveryArtifact.objects.filter(job=j).first()
  except DatabaseError:raise ConnectionError('Native export artifact lookup unavailable') from None
  if artifact and (artifact.manifest!=j.intent['manifest'] or artifact.sha256!=digest(j.intent['manifest'])):raise ValidationError('Export artifact differs from immutable intent')
  if artifact:
   r=artifact.receipt
   flag='native_local_metadata_read' if j.kind=='export' else 'native_file_copy'
   if r.get('kind')!=j.kind or r.get('manifest_sha256')!=artifact.sha256 or r.get(flag) is not True:raise ValidationError('Exact native artifact receipt required')
  try:found=bool(artifact) if j.kind=='export' else bool(storage.file_receipt(j))
  except OSError:raise ConnectionError('Sealed file receipt lookup unavailable') from None
  return {'state':'found' if found else 'not_found','job_kind':j.kind,'operation_key_sha256':digest(j.operation_key),'manifest_sha256':digest(j.intent['manifest']),'storage_identity':j.intent['storage_identity'],'artifact':artifact.pk if artifact else None,'file_verified':j.kind=='backup' and found,'payload_bodies_included':False,'current_authority_restored':False,'full_database_backup':False,'full_database_export':False}
