from django.core.exceptions import ValidationError
from apps.documents.contracts import digest
from adapters.approvals import SuppliedApprovalReadAdapter
class SuppliedMigrationEvidenceAdapter(SuppliedApprovalReadAdapter):
 """Strict report input. Never executes migration/restore or authenticates a remote report."""
 pass
class LocalEvidenceInventoryAdapter:
 """Actual bounded ORM read of selected immutable evidence metadata; no data writes or body reads."""
 name='psl-selected-evidence-inventory/v1'
 def read(self,actor,plan):
  from apps.identity.services import require
  require(actor,plan.case,'migration.inventory')
  if plan.payload['source_system']!='psl-evidence' or plan.payload['source_ref']!=str(plan.case_id) or plan.payload['source_version']!='evidence-manifest-v1':raise ValidationError('This adapter reads only the exact local PSL case evidence manifest')
  rows=list(plan.case.evidence.filter(pk__in=plan.payload['evidence_ids']).order_by('pk').values('id','kind','version','sha256'))
  if len(rows)!=len(plan.payload['evidence_ids']):raise ValidationError('Inventory must contain every selected case evidence ID')
  return {'adapter':self.name,'coverage':'selected immutable evidence metadata only; not the whole database','records':rows,'record_count':len(rows),'manifest_sha256':digest(rows),'source_ref':str(plan.case_id),'native_inventory_read':True,'migration_executed':False,'restore_executed':False}
class LocalMigrationReadinessAdapter:
 def read(self,actor,case_id,assessment_id):
  from apps.documents.migration_readiness import report
  return report(actor,case_id,assessment_id)
