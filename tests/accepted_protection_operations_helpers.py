from apps.workflows import protection as d,operator_delivery as w,accepted_protection_operations as domain,private_readiness_operations as private
from apps.workflows.operator_inventory import bundle
from apps.documents.contracts import digest
from .operator_helpers import evidence,policy

def fixture(prefix='accepted-protection',foreign=False,kind='backup',configured=True):
 if kind=='restore':
  from .protection_acceptance_helpers import fixture as native,owners,configure,reviews
 else:
  from .file_acceptance_helpers import fixture as native,owners,configure,reviews
 f=native(prefix,foreign=foreign);owners(f);configure(f);reviews(f)
 source=f['restore'] if kind=='restore' else f['file_backup']
 w.operate(f['actor'],f['case'].pk,source.pk,'cancel','Keep original not-found evidence; use a distinct export plan')
 f['source_plan']=f['plan'];f['rules']={domain.FIELD:[f['protection_packet'].pk],'private_disclosure':'accepted_metadata_only'}
 if configured:f['ops_policy']=policy(f,domain.COMPONENT,f['rules'])
 return f

def plan(f,reference='accepted-protection',mixed=False):
 selected=[f['protection_packet'].pk];old=[f['packet'].pk] if mixed else []
 m=bundle(f['actor'],f['case'],200,old,selected);v=dict(f['source_plan'].payload,**{domain.FIELD:selected},expected_manifest_sha256=digest(m),expected_record_count=len(m['evidence'])+len(m['jobs'])+private.count(m))
 if not mixed:v.pop(private.FIELD,None)
 f['plan']=d.capture_plan(f['actor'],f['case'].pk,reference,v,evidence(f,'ops_plan').pk);return f['plan']
