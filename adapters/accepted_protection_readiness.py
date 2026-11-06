"""Explicit AF13 inventory; actual SQL, sealed bytes and isolated restore receipts."""
from django.core.exceptions import ValidationError
from apps.documents.contracts import digest
from apps.workflows.operator_models import RecoveryJob
from apps.workflows import private_readiness_operations as private
from adapters.private_file_readiness import PrivateFileReadinessAdapter as File
from adapters.private_protection_readiness import PrivateProtectionReadinessAdapter as Restore
from adapters import operator_protection as storage

SCHEMA='schema:psl/accepted-protection-native-source/v1'

class AcceptedProtectionReadinessAdapter:
 def job(self,c,pk):
  if type(pk) is not int or pk<1:raise ValidationError('Typed positive AF13 source job identity required')
  j=RecoveryJob.objects.select_related('plan__case').filter(pk=pk,plan__case=c,kind__in=['export','backup','restore'],plan__payload__has_key=private.protection.FIELD).first()
  if not j:raise ValidationError('Exact AF13 protection metadata operator job required')
  return j
 def access(self,a,j):
  self.job(j.plan.case,j.pk)
  from apps.workflows.operator_inventory import job_access
  job_access(a,j.plan.case,'protection',j);private.historical(a,j.plan.case,j.intent['manifest'])
 def describe(self,a,j):
  self.access(a,j);m=j.intent['manifest']
  def inventory(key):return [{k:row[k] for k in ['packet','packet_sha256','metadata_sha256']} for row in m.get(key,[])]
  return {'schema_ref':SCHEMA,'job':j.pk,'job_kind':j.kind,'plan':j.plan_id,'case':str(j.plan.case_id),'plan_sha256':j.plan.sha256,'intent_sha256':digest(j.intent),'manifest_sha256':digest(m),'protection_inventory':inventory('accepted_private_protection'),'finance_inventory':inventory('accepted_private_readiness'),'storage_identity':j.intent['storage_identity'],'target_identity':j.intent['target_identity'],'current_authority_restored':False}
 def health(self,j):
  if storage.storage_identity()!=j.intent['storage_identity']:raise ConnectionError('Reserved storage identity changed')
  if j.kind=='restore':
   if storage.target_identity()!=j.intent['target_identity']:raise ConnectionError('Reserved isolated target changed')
   return {'storage_probe':'isolated_metadata_sql_select','storage_write_proven':False}
  return File().health(j)
 def current(self,a,j):
  self.access(a,j)
  from apps.workflows.protection import current_plan
  current_plan(j.plan);private.current(a,j.plan,j.intent['manifest']);self.health(j)
  if j.kind=='restore':
   from apps.workflows.operator_models import RecoveryArtifact
   source=RecoveryArtifact.objects.select_related('job').filter(pk=j.intent['input_artifact'],job__plan=j.plan,job__kind='backup').first()
   if not source or source.manifest!=j.intent['manifest'] or not storage.file_receipt(source.job):raise ValidationError('Exact sealed restore input bytes required')
 def receipts(self,j):
  v=Restore().receipts(j) if j.kind=='restore' else File().receipts(j)
  return {'schema_ref':'schema:psl/accepted-protection-native-receipt/v1','job_kind':j.kind,'receipt':v}
