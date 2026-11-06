"""D03 source clarification and opt-in BaaS invoice evidence; never an inferred signature gate."""
from django.db import transaction,connection
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.services import lock_case,event,bump
from apps.identity.models import Grant
from apps.identity.services import require
from apps.pmo.services import subject
from apps.documents.contracts import digest,validate
from apps.policy.services import active_component,reference_values,decision_authority
from apps.policy.d03_validators import STATEMENT,CONTROLS,REQUIREMENTS,IMPLEMENTATIONS
from adapters.forecast import obj,KEY
from adapters.hrfinance import timestamp
from adapters.billing_evidence import SuppliedBillingEvidenceAdapter
from .models import BillingCoverage,Invoice,BillingEvidenceSource,BillingEvidenceReview,BillingReleaseProfile,BillingControlReceipt,BillingReleaseAssessment,BillingReleaseBinding
from .billing import coverage_current
ID={'type':'integer','minimum':1};HASH={'type':'string','pattern':'^[a-f0-9]{64}$'}
NULL={'type':'null'}
DECLARATIONS=obj({effect:{'anyOf':[REQUIREMENTS,NULL]} for effect in ['issue','deliver']})
SOURCE=obj({'implementation':{'anyOf':[{'enum':IMPLEMENTATIONS},NULL]},'effect_requirements':{'anyOf':[DECLARATIONS,NULL]},'kind':{'enum':['statement','flow_contract']},'system':KEY,'external_ref':KEY,'source_version':KEY,'source_kind':{'enum':['written_owner_confirmation','reviewed_source_segment','supplied_flow_contract']},'locator':{'type':'string','minLength':1,'maxLength':500},'quote':{'type':'string','minLength':1,'maxLength':4000},'reported_at':{'type':'string'},'flow_ref':{'anyOf':[KEY,{'type':'null'}]},'flow_version':{'anyOf':[KEY,{'type':'null'}]},'environment_ref':{'anyOf':[KEY,{'type':'null'}]}})
CONTROL=obj({'invoice_id':ID,'invoice_sha256':HASH,'preparation_key':HASH,'effect':{'enum':['issue','deliver']},'control_key':KEY,'system':KEY,'external_ref':KEY,'source_version':KEY,'flow_ref':KEY,'flow_version':KEY,'environment_ref':KEY,'observed_at':{'type':'string'},'outcome':{'enum':['passed','failed','unknown','unavailable']},'evidence_class':{'enum':['supplied_reference','synthetic_reference']}})

def readable(a,c):
 if not get_user_model().objects.filter(pk=a.pk,is_active=True).exists():raise PermissionDenied('Active authenticated principal required')
 require(a,c,'case.read');require(a,c,'finance.read');require(a,c,'d03.read')
def locked(a,case_id,action,expected=None):
 c=lock_case(a,case_id,action,expected);list(Grant.objects.select_for_update().filter(case=c).order_by('pk'));readable(a,c);return c
def finance(a,c,action):
 readable(a,c);require(a,c,action);require(a,c,'d03.source.read');return decision_authority(a,c,'Finance')
def advisory(key):
 with connection.cursor() as cur:cur.execute('SELECT pg_advisory_xact_lock(%s)',[int(digest(key)[:15],16)])
def exact_source(c,pk):
 s=BillingEvidenceSource.objects.select_related('case','actor').filter(case=c,pk=pk).first()
 if not s:raise ValidationError('Exact case billing-evidence source required')
 return s
def source_current(s):
 if BillingEvidenceSource.objects.filter(case=s.case,reference=s.reference,version__gt=s.version).exists():raise ValidationError('Source version superseded; retain and reconcile old wording/contracts')
 if s.sha256!=digest(s.payload):raise ValidationError('Source hash mismatch')
@transaction.atomic
def capture_source(a,case_id,reference,payload,evidence_id,expected=None,predecessor=None):
 c=locked(a,case_id,'d03.capture',expected);validate(KEY,reference);validate(SOURCE,payload);e=subject(c,evidence_id,'d03_source')
 if payload['quote'] not in e.body:raise ValidationError('Exact quoted source evidence required; do not reconstruct omitted recordings')
 if timestamp(payload['reported_at'])>timezone.now():raise ValidationError('Actual source cannot be future dated')
 if payload['kind']=='flow_contract' and any(payload[k] is None for k in ['flow_ref','flow_version','environment_ref']):raise ValidationError('Exact flow/environment versions required')
 if payload['kind']=='statement' and (payload['implementation'] is not None or payload['effect_requirements'] is not None):raise ValidationError('Statement interpretation cannot declare dispatch prerequisites')
 advisory({'tenant':c.tenant,**{k:payload[k] for k in ['system','external_ref','source_version']}})
 old=BillingEvidenceSource.objects.filter(tenant=c.tenant,system=payload['system'],external_ref=payload['external_ref'],source_version=payload['source_version']).first()
 if old:
  if old.case_id!=c.pk or old.reference!=reference or old.sha256!=digest(payload):raise ValidationError('Source identity already claimed or conflicting; investigate without another instance')
  return old
 previous=BillingEvidenceSource.objects.filter(case=c,reference=reference).order_by('-version').first()
 if previous and (previous.pk!=predecessor or previous.kind!=payload['kind']) or not previous and predecessor:raise ValidationError('Explicit current same-kind source predecessor required')
 s=BillingEvidenceSource.objects.create(case=c,reference=reference,version=previous.version+1 if previous else 1,kind=payload['kind'],tenant=c.tenant,system=payload['system'],external_ref=payload['external_ref'],source_version=payload['source_version'],payload=payload,sha256=digest(payload),evidence=e,actor=a)
 event(a,c,'d03.source_captured',source=s.pk,verified=False);bump(c);return s

@transaction.atomic
def review_source(a,case_id,source_id,verdict,meaning,operation_key,evidence_id,expected=None):
 c=locked(a,case_id,'d03.review',expected);s=exact_source(c,source_id);validate(KEY,operation_key);auth=finance(a,c,'d03.review')
 if verdict not in ['confirm','dispute','withdraw'] or meaning not in (['flow_contract'] if s.kind=='flow_contract' else ['prices','signature','other','unresolved']):raise ValidationError('Typed source interpretation and confirmation required; this is not invoice release approval')
 e=subject(c,evidence_id,'d03_review');old=BillingEvidenceReview.objects.filter(source=s,operation_key=operation_key).first()
 if old:
  if (old.actor_id,old.verdict,old.meaning,old.evidence_id)!=(a.pk,verdict,meaning,e.pk):raise ValidationError('Review key conflicts with previous intent')
  return old
 if verdict=='confirm':source_current(s)
 r=BillingEvidenceReview.objects.create(source=s,verdict=verdict,meaning=meaning,operation_key=operation_key,authority=auth,evidence=e,actor=a)
 event(a,c,'d03.source_reviewed',review=r.pk,invoice_approved=False,signature_gate_created=False);bump(c);return r
def confirmed(s):
 source_current(s);r=BillingEvidenceReview.objects.filter(source=s).select_related('actor').order_by('-pk').first()
 if not r or r.verdict!='confirm':raise ValidationError('Current actual Finance source confirmation required')
 if r.authority!=finance(r.actor,s.case,'d03.review'):raise ValidationError('Source-confirmation authority changed')
 return r

@transaction.atomic
def enroll(a,case_id,coverage_id,evidence_id,expected=None):
 c=locked(a,case_id,'d03.enroll',expected);finance(a,c,'d03.enroll');cov=BillingCoverage.objects.filter(case=c,pk=coverage_id).first()
 if not cov or not coverage_current(cov):raise ValidationError('Exact current billing coverage required')
 old=BillingReleaseProfile.objects.filter(coverage=cov).first()
 if old:return old
 p=BillingReleaseProfile.objects.create(coverage=cov,evidence=subject(c,evidence_id,'d03_enrollment'),actor=a);event(a,c,'d03.coverage_enrolled',profile=p.pk,no_inferred_signature_gate=True);bump(c);return p
def profile_for(i):
 if i.preparation.kind!='usage':return None
 cov=i.preparation.coverage
 rows=BillingReleaseProfile.objects.filter(coverage__case=i.case,coverage__customer=cov.customer,coverage__service=cov.service,coverage__contract=cov.contract).order_by('-pk')
 if not rows.exists():return None
 p=rows.filter(coverage=cov).first()
 if not p:raise ValidationError('This enrolled business coverage has changed; explicitly enroll its current version')
 return p
def rule_context(i,effect):
 if effect not in ['issue','deliver']:raise ValidationError('Select invoice issuance or delivery evidence')
 p=profile_for(i)
 if not p:raise ValidationError('Explicit exact BaaS coverage enrollment required for D03 evidence work')
 from .invoices import current
 current(i);st=active_component(STATEMENT,i.case);ct=active_component(CONTROLS,i.case)
 statement=reference_values(st)[0];rules=[v for v in reference_values(ct) if v['coverage_id']==i.preparation.coverage_id and v['effect']==effect]
 if len(rules)!=1:raise ValidationError('Configure one exact current coverage/effect release evidence contract')
 rule=rules[0]
 return {'profile':p.pk,'statement_policy':st.pk,'controls_policy':ct.pk,'statement_review':statement['review_id'],'contract_review':rule['review_id'],'invoice_sha256':i.sha256,'preparation_key':i.preparation.operation_key},rule

@transaction.atomic
def observe_control(a,case_id,invoice_id,evidence_id,expected=None):
 c=locked(a,case_id,'d03.observe',expected);i=Invoice.objects.filter(case=c,pk=invoice_id).first()
 if not i:raise ValidationError('Exact case invoice required')
 e=subject(c,evidence_id);v=SuppliedBillingEvidenceAdapter().read(e,CONTROL,e.kind);pins,rule=rule_context(i,v['effect']);req=next((x for x in rule['requirements'] if x['key']==v['control_key']),None)
 if not req or e.kind!=req['evidence_kind']:raise ValidationError('Exact configured control key and evidence kind required')
 if v['invoice_id']!=i.pk or v['invoice_sha256']!=i.sha256 or v['preparation_key']!=i.preparation.operation_key or any(v[k]!=rule[k] for k in ['flow_ref','flow_version','environment_ref']):raise ValidationError('Control receipt must correlate exact invoice/preparation/flow/environment version')
 source=exact_source(c,rule['source_id'])
 if v['system']!=source.system:raise ValidationError('Observation system differs from the confirmed contract source')
 age=(timezone.now()-timestamp(v['observed_at'])).total_seconds()
 if not 0<=age<=rule['max_age_seconds']:raise ValidationError('Current bounded source observation required')
 if v['evidence_class']=='synthetic_reference' and not c.synthetic:raise ValidationError('Synthetic control receipts cannot prove operational evidence')
 auth=finance(a,c,'d03.observe') # Source text cannot grant authority, including a claimed passed result.
 advisory({'tenant':c.tenant,**{k:v[k] for k in ['system','external_ref','source_version']}})
 old=BillingControlReceipt.objects.filter(tenant=c.tenant,system=v['system'],external_ref=v['external_ref'],source_version=v['source_version']).first()
 if old:
  if old.invoice_id!=i.pk or old.sha256!=digest(v):raise ValidationError('Control receipt identity already claimed or conflicting')
  return old
 pins['observer_authority']=auth
 r=BillingControlReceipt.objects.create(invoice=i,effect=v['effect'],control_key=v['control_key'],tenant=c.tenant,system=v['system'],external_ref=v['external_ref'],source_version=v['source_version'],payload=v,sha256=digest(v),snapshot=pins,evidence=e,actor=a)
 event(a,c,'d03.control_observed',receipt=r.pk,native_flow_verified=False);bump(c);return r
def snapshot(i,effect):
 pins,rule=rule_context(i,effect);rows=[];findings=[]
 for required in rule['requirements']:
  r=BillingControlReceipt.objects.filter(invoice=i,effect=effect,control_key=required['key']).select_related('actor').order_by('-pk').first();rows.append([required['key'],r.pk if r else None])
  if not r:findings.append('Missing control evidence: '+required['key']);continue
  expected=dict(pins,observer_authority=finance(r.actor,i.case,'d03.observe'))
  if r.snapshot!=expected:findings.append('Control authority or policy changed: '+required['key'])
  if r.payload['outcome']!='passed':findings.append('Control failed, unknown or unavailable: '+required['key'])
  if not 0<=(timezone.now()-timestamp(r.payload['observed_at'])).total_seconds()<=rule['max_age_seconds']:findings.append('Control evidence expired: '+required['key'])
 pins['controls']=rows
 return pins,rule,findings
@transaction.atomic
def assess(a,case_id,invoice_id,effect,expected=None):
 c=locked(a,case_id,'d03.assess',expected);i=Invoice.objects.filter(case=c,pk=invoice_id).first()
 if not i:raise ValidationError('Exact case invoice required')
 pins,rule,findings=snapshot(i,effect)
 r=BillingReleaseAssessment.objects.create(invoice=i,effect=effect,snapshot=pins,result={'evidence_ready':not findings,'findings':findings,'implementation':rule['implementation'],'native_flow_verified':False,'signature_gate_inferred':False,'invoice_approved':False,'posted':False,'sent':False,'debt_waived':False,'deployment_authorized':False},actor=a)
 event(a,c,'d03.evidence_assessed',assessment=r.pk);bump(c);return r
def current_assessment(r):
 readable(r.actor,r.invoice.case);require(r.actor,r.invoice.case,'d03.assess')
 if BillingReleaseAssessment.objects.filter(invoice=r.invoice,effect=r.effect,pk__gt=r.pk).exists():raise ValidationError('Newer release evidence assessment is current')
 pins,rule,findings=snapshot(r.invoice,r.effect)
 if pins!=r.snapshot or findings!=r.result['findings']:raise ValidationError('Statement/control/source/authority changed; reassess exact release evidence')
 if not r.result['evidence_ready']:raise ValidationError(r.result['findings'])
 return rule
@transaction.atomic
def bind(a,case_id,assessment_id,expected=None):
 c=locked(a,case_id,'d03.bind',expected);r=BillingReleaseAssessment.objects.select_related('invoice__case').filter(invoice__case=c,pk=assessment_id).first()
 if not r:raise ValidationError('Exact case assessment required')
 current_assessment(r);auth=finance(a,c,'d03.bind');old=BillingReleaseBinding.objects.filter(assessment=r).first()
 pins={'assessment_sha256':digest(r.snapshot),'binder_authority':auth}
 if old:
  if old.snapshot!=pins:raise ValidationError('Binding authority changed; create a new assessment/binding')
  return old
 b=BillingReleaseBinding.objects.create(assessment=r,snapshot=pins,actor=a);event(a,c,'d03.evidence_bound',binding=b.pk,invoice_approved=False);bump(c);return b
def release_context(i,effect):
 if not profile_for(i):return None # No new universal gate; only explicitly enrolled usage obligations depend on D03.
 b=BillingReleaseBinding.objects.filter(assessment__invoice=i,assessment__effect=effect).select_related('assessment__invoice__case','actor').order_by('-pk').first()
 if not b:raise ValidationError('Current bound D03 release evidence required for this enrolled usage coverage')
 rule=current_assessment(b.assessment);auth=finance(b.actor,i.case,'d03.bind')
 if b.snapshot!={'assessment_sha256':digest(b.assessment.snapshot),'binder_authority':auth}:raise ValidationError('Release binding authority changed')
 if rule['implementation']!='internal_invoice_register_v1':raise ValidationError('Reviewed native incumbent flow adapter remains unavailable; source references are not a dispatch implementation')
 return {'binding':b.pk,'assessment':b.assessment_id,'snapshot_sha256':digest(b.assessment.snapshot)}
@transaction.atomic
def report(a,case_id,assessment_id):
 c=locked(a,case_id,'d03.read');r=BillingReleaseAssessment.objects.select_related('invoice__case').filter(invoice__case=c,pk=assessment_id).first()
 if not r:raise ValidationError('Exact case assessment required')
 holds=[]
 try:current_assessment(r)
 except (ValidationError,PermissionDenied) as exc:holds.append(str(exc))
 return {'assessment':r.pk,'invoice':r.invoice_id,'effect':r.effect,'recorded_result':r.result,'holds':holds,'current_evidence_ready':not holds,'native_flow_verified':False,'invoice_approved':False,'posted':False,'sent':False,'debt_waived':False,'deployment_authorized':False}
