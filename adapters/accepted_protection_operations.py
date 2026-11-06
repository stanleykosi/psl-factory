"""Closed AF13 protection acceptance, distinct from Finance readiness packets."""
from django.core.exceptions import ValidationError
from apps.documents import protection_acceptance as source
from apps.documents.contracts import digest
from apps.identity.services import require

ROW_FIELDS={'packet','packet_sha256','metadata','metadata_sha256','accepted_at_capture','current_authority_restored'}
FLAGS={'full_database_backup','full_database_export','payload_bodies_included','current_authority_restored','full_database_restore','native_quickbooks_verified','operational_acceptance','whole_product_accepted','deployment_authorized'}
FIELDS=FLAGS|{'packet','sha256','package','process_ids','level','acceptance_review','acceptor','pins','evidence','scope'}

class AcceptedProtectionOperatorAdapter:
 def packet(self,c,pk):
  b=source.Packet.objects.select_related('package__case','assessment__contract__case','actor').filter(case=c,pk=pk).first()
  if b is None:raise ValidationError('Exact case AF13 protection packet required')
  return b
 def access(self,a,b):
  require(a,b.case,'validation.export');source.package_access(a,b.package)
 def capture(self,a,c,pk):
  b=self.packet(c,pk);self.access(a,b);v=source.export(a,c.pk,pk)
  return {'packet':b.pk,'packet_sha256':b.sha256,'metadata':v,'metadata_sha256':digest(v),'accepted_at_capture':True,'current_authority_restored':False}
 def historical(self,a,c,row):
  if not isinstance(row,dict) or set(row)!=ROW_FIELDS:raise ValidationError('Closed accepted protection row required')
  v=row['metadata']
  if not isinstance(v,dict) or set(v)!=FIELDS:raise ValidationError('Closed accepted protection fields required')
  b=self.packet(c,row['packet']);self.access(a,b)
  r=b.package.reviews.filter(pk=v['acceptance_review'],kind='acceptance',verdict='approve').first()
  if row['packet_sha256']!=b.sha256 or row['metadata_sha256']!=digest(v) or row['accepted_at_capture'] is not True or row['current_authority_restored'] is not False or v['packet']!=b.pk or v['sha256']!=b.sha256 or v['package']!=b.package_id or v['evidence']!=b.snapshot['evidence'] or v['process_ids']!=b.package.payload['process_ids'] or v['level']!=b.package.payload['level'] or not r or v['acceptor']!=r.actor_id or r.snapshot.get('private_protection')!=v['pins'] or v['scope']!='selected AF13 evidence only' or any(v[k] is not False for k in FLAGS):raise ValidationError('Sealed accepted protection lineage changed')
  return b
