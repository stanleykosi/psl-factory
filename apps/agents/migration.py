from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.services import add_evidence,event,bump
from apps.documents import migration_readiness as d
from apps.documents.migration_models import MigrationPlan,MigrationAssessment
from apps.policy.services import resolve
from apps.policy.migration_validators import COMPONENT
from .models import AgentRun
@transaction.atomic
def investigate(a,case_id,expected=None):
 c=d.locked(a,case_id,'agent.migration',expected);findings=[]
 for p in MigrationPlan.objects.filter(case=c).select_related('case','package__case').order_by('-pk')[:25]:
  questions=[]
  try:d.current_plan(p)
  except ValidationError:questions.append('Superseded plan; reconcile exact source/target/build before reusing evidence')
  for key in ['expected_record_count','expected_manifest_sha256']:
   if p.payload[key] is None:questions.append('Obtain explicit '+key+'; unknown is not zero')
  r=MigrationAssessment.objects.filter(plan=p).order_by('-pk').first()
  if r:
   try:d.current_assessment(r);questions.extend(r.result['findings'])
   except (ValidationError,PermissionDenied):questions.append('Assessment inputs or authority changed; reassess through the typed service')
  else:questions.append('Read the selected inventory and assess required evidence against current D11 rules')
  questions.append('Obtain actual native workflow/migration/restore execution evidence; supplied reports and inventory reads confer no deployment authority')
  findings.append({'plan':p.pk,'reference':p.reference,'version':p.version,'questions':questions[:15]})
 e=add_evidence(a,c.pk,'agent_migration','Bounded migration plan metadata/readiness investigation; no source body read or migration/restore execution','local:deterministic-migration-v1')
 r=AgentRun.objects.create(case=c,actor=a,evidence=e,process_id='P15',provider='deterministic-migration-v1',result={'findings':findings,'policy_status':resolve(COMPONENT,c).status,'coverage':'At most 25 plan versions in the granted case','source_body_read':False,'migration_executed':False,'restore_executed':False,'operational_acceptance':False})
 event(a,c,'agent.migration',run=r.pk);bump(c);return r
