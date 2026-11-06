"""Closed accepted metadata. Historical reads never restore current acceptance."""
from django.core.exceptions import ValidationError
from apps.documents.contracts import digest
from apps.identity.services import require
from apps.finance import readiness_acceptance as source

class AcceptedReadinessOperatorAdapter:
 def packet(self,c,pk):
  b=source.Packet.objects.select_related('package__case','assessment__contract__case','actor').filter(case=c,pk=pk).first()
  if b is None:raise ValidationError('Exact case accepted private readiness packet required')
  return b
 def access(self,a,b):
  require(a,b.case,'validation.export');source.package_access(a,b.package)
 def capture(self,a,c,pk):
  b=self.packet(c,pk);self.access(a,b);value=source.export(a,c.pk,pk)
  return {'packet':pk,'packet_sha256':b.sha256,'metadata':value,'metadata_sha256':digest(value),'accepted_at_capture':True,'current_authority_restored':False}
 def historical(self,a,c,row):
  if not isinstance(row,dict) or set(row)!={'packet','packet_sha256','metadata','metadata_sha256','accepted_at_capture','current_authority_restored'}:raise ValidationError('Closed accepted metadata row required')
  v=row['metadata']
  if not isinstance(v,dict) or set(v)!={'packet','sha256','package','process_ids','level','acceptance_review','acceptor','pins','evidence','scope','payload_bodies_included','native_quickbooks_verified','operational_acceptance','whole_product_accepted','deployment_authorized'}:raise ValidationError('Closed accepted metadata fields required')
  b=self.packet(c,row['packet']);self.access(a,b)
  review=b.package.reviews.filter(pk=v['acceptance_review'],kind='acceptance',verdict='approve').first()
  if set(row)!={'packet','packet_sha256','metadata','metadata_sha256','accepted_at_capture','current_authority_restored'} or row['packet_sha256']!=b.sha256 or row['metadata_sha256']!=digest(v) or not row['accepted_at_capture'] or row['current_authority_restored'] is not False or v['packet']!=b.pk or v['sha256']!=b.sha256 or v['package']!=b.package_id or v['evidence']!=b.snapshot['evidence'] or v['process_ids']!=b.package.payload['process_ids'] or v['level']!=b.package.payload['level'] or not review or v['acceptor']!=review.actor_id or review.snapshot.get('private_readiness')!=v['pins'] or v['scope']!='selected AF13 evidence only' or any(v[k] is not False for k in ['payload_bodies_included','native_quickbooks_verified','operational_acceptance','whole_product_accepted','deployment_authorized']):raise ValidationError('Sealed accepted private metadata lineage changed')
  # A closed field set prevents a body from being added to a nominal metadata row.
  if set(v)!={'packet','sha256','package','process_ids','level','acceptance_review','acceptor','pins','evidence','scope','payload_bodies_included','native_quickbooks_verified','operational_acceptance','whole_product_accepted','deployment_authorized'}:raise ValidationError('Closed accepted metadata fields required')
  return b
