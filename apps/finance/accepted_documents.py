"""Native accepted metadata documents. No generic evidence copy or automatic publication."""
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from apps.core.services import event,bump
from apps.identity.services import require
from apps.policy.services import decision_authority
from apps.policy.ledger_validators import PUBLICATION as COMPONENT
from apps.documents.models import Template,Document,Version,ControlledReview,Publication,PublicationJob,PublicationReceipt
from apps.documents.contracts import digest
from apps.documents.controlled import baseline_manifest,publication_requirements
from adapters.accepted_finance import AcceptedFinanceMetadataAdapter
from .acceptance_models import AcceptedFinanceDocument as Binding
from . import acceptance as h,acceptance_evaluation as evaluation
TYPE='accepted_finance_metadata'

def binding(version):return Binding.objects.select_related('handoff__case','handoff__draft__source__projection','handoff__draft__owner','handoff__package__case','handoff__actor','version__document__case','version__template').filter(version=version).first()

def person(c,v,key):
 a=get_user_model().objects.filter(pk=v[key+'_id'],is_active=True).first()
 if a is None:raise ValidationError('Actual active publication principal required')
 h.readable(a,c);require(a,c,'finance.accepted.'+('review' if key=='reviewer' else 'publish'));require(a,c,'document.read')
 if key=='publisher':require(a,c,'document.publish')
 return a,decision_authority(a,c,'Finance')

def validate_policy(c,v,runtime=False):
 rows=list(h.Handoff.objects.filter(case=c,pk__in=v['handoff_ids']))
 if len(rows)!=len(v['handoff_ids']):raise ValidationError('Exact case handoff inventory required')
 templates=Template.objects.filter(case=c,pk__in=v['template_ids'],definition__document_type=TYPE)
 if templates.count()!=len(v['template_ids']) or any(v['audience'] not in t.definition['audience_fields'] for t in templates):raise ValidationError('Exact metadata templates and configured audience required')
 if v['reviewer_id']==v['publisher_id'] or any(x.actor_id in [v['reviewer_id'],v['publisher_id']] for x in rows):raise ValidationError('Independent source owner, document reviewer and publisher required')
 if not runtime:
  try:
   for key in ['reviewer','publisher']:
    a,_=person(c,v,key)
    for row in rows:h.access(a,row)
   recipients(c,v)
  except PermissionDenied:raise ValidationError('Actual source/role/publication or recipient grants required') from None

def recipients(c,v):
 users=list(get_user_model().objects.filter(pk__in=v['recipient_ids'],is_active=True))
 if len(users)!=len(v['recipient_ids']):raise PermissionDenied('Active configured recipients required')
 for a in users:require(a,c,'document.receive:'+v['audience'])
 return sorted(v['recipient_ids'])

def rules(c):return h.finance.ledger.config(c,COMPONENT)

def pins(a,row,t,audience):
 h.access(a,row);config,v=rules(row.case);validate_policy(row.case,v,True)
 if row.pk not in v['handoff_ids'] or t.pk not in v['template_ids'] or audience!=v['audience']:raise ValidationError('Exact configured accepted handoff/template/audience required')
 auth={}
 for key in ['reviewer','publisher']:
  who,auth[key]=person(row.case,v,key);h.access(who,row)
 metadata,accepted=AcceptedFinanceMetadataAdapter().read(a,row,v['fields'])
 return {'handoff':row.pk,'handoff_sha256':row.sha256,'acceptance':accepted,'policy':config.pk,'template':t.pk,'audience':audience,'metadata':metadata,'reviewer':v['reviewer_id'],'publisher':v['publisher_id'],'authority':auth,'recipients':recipients(row.case,v)}

def payload(value):return {'title':'Accepted Finance / AF13 metadata','type':TYPE,'sections':[{'heading':key,'text':str(val)} for key,val in value['metadata'].items()]}

def access(a,b):
 h.access(a,b.handoff);require(a,b.handoff.case,'document.read')

def exact(c,pk):
 v=Version.objects.select_related('document__case','template').filter(pk=pk,document__case=c).first()
 b=binding(v) if v else None
 if b is None:raise ValidationError('Exact case accepted metadata document required')
 return b

@transaction.atomic
@evaluation.evaluated
def draft(a,case_id,handoff_id,template_id,audience,expected=None,document_id=None):
 c=h.locked(a,case_id,'finance.accepted.draft',expected);require(a,c,'document.draft');row=h.exact(c,handoff_id)
 if a.pk!=row.actor_id:raise PermissionDenied('Original Finance owner prepares metadata')
 t=Template.objects.filter(case=c,pk=template_id,definition__document_type=TYPE).first()
 if not t:raise ValidationError('Native metadata template required')
 value=pins(a,row,t,audience)
 if document_id:
  doc=Document.objects.filter(case=c,pk=document_id,owner=a).first()
  if not doc or not doc.current_id:raise ValidationError('Exact owned metadata document predecessor required')
  old=exact(c,doc.current_id);access(a,old)
 else:doc=Document.objects.create(case=c,title='Accepted Finance / AF13 metadata',owner=a)
 projected=payload(value)
 version=Version.objects.create(document=doc,number=doc.versions.count()+1,template=t,audience=audience,fields={},source_manifest={'native':'accepted_finance','handoff':row.pk,'acceptance':value['acceptance']},baseline_manifest=baseline_manifest(c),payload=projected,payload_sha256=digest(projected),created_by=a)
 Binding.objects.create(version=version,handoff=row,policy_id=value['policy'],snapshot=value,sha256=digest(value));doc.current=version;doc.save(update_fields=['current'])
 event(a,c,'agent.data.finance_metadata_drafted',version=version.pk);bump(c);return version

def current(b):
 v=b.version;c=v.document.case
 if v.document.current_id!=v.pk or b.snapshot!=pins(v.created_by,b.handoff,v.template,v.audience) or b.sha256!=digest(b.snapshot) or v.payload!=payload(b.snapshot) or v.payload_sha256!=digest(v.payload) or v.baseline_manifest!=baseline_manifest(c):raise ValidationError('Metadata source, acceptance, policy, payload or document head changed; prepare and review a successor')

def reviewer(a,b,key):
 access(a,b);_,v=rules(b.handoff.case);who,auth=person(b.handoff.case,v,key)
 if a.pk!=who.pk or a.pk!=b.snapshot[key]:raise PermissionDenied('Exact configured and recorded publication principal required')
 return {'policy':b.policy_id,'role':auth,'binding':b.sha256}

@transaction.atomic
@evaluation.evaluated
def review(a,case_id,pk,verdict,note,expected=None):
 if verdict not in ['approve','return','reject','withdraw'] or not isinstance(note,str) or not note.strip() or len(note)>2000:raise ValidationError('Typed human review and bounded rationale required')
 c=h.locked(a,case_id,'finance.accepted.review',expected);b=exact(c,pk);auth=reviewer(a,b,'reviewer')
 if verdict=='approve':current(b)
 r=ControlledReview.objects.create(version=b.version,actor=a,verdict=verdict,note=note,authority=auth,payload_sha256=b.version.payload_sha256)
 event(a,c,'agent.data.finance_metadata_reviewed',version=pk,review=r.pk);bump(c);return r

def approved(b):
 r=b.version.reviews.select_related('actor').order_by('-pk').first()
 if not r or r.verdict!='approve' or r.payload_sha256!=b.version.payload_sha256 or r.authority!=reviewer(r.actor,b,'reviewer'):raise ValidationError('Independent current exact metadata document review required')
 _,v=rules(b.handoff.case)
 if (timezone.now()-r.created_at).total_seconds()>v['review_ttl_seconds']:raise ValidationError('Metadata document review expired')
 return r

def requirements(b):
 policies,users,retention=publication_requirements(b.handoff.case,b.version)
 if users!=b.snapshot['recipients']:raise ValidationError('Document recipients must exactly match the metadata audience policy')
 policies[COMPONENT]=b.policy_id
 return policies,users,retention

@transaction.atomic
@evaluation.evaluated
def publish(a,case_id,pk,expected=None):
 c=h.locked(a,case_id,'finance.accepted.publish',expected);b=exact(c,pk);reviewer(a,b,'publisher');current(b);r=approved(b);policies,users,retention=requirements(b)
 old=Publication.objects.filter(version=b.version).first()
 if old:return old
 p=Publication.objects.create(version=b.version,review=r,actor=a,policies=policies,recipient_ids=users,retention_days=retention,operation_key=f'accepted-finance:{pk}:v1');PublicationJob.objects.create(publication=p)
 event(a,c,'agent.data.finance_metadata_reserved',publication=p.pk);bump(c);return p

@transaction.atomic
@evaluation.evaluated
def deliver(job_id,fence):
 from apps.documents.delivery import check_fence
 from apps.core.models import Case
 from apps.finance.ledger import scope_lock
 job=PublicationJob.objects.select_related('publication__version__document').get(pk=job_id);p=job.publication
 scope_lock(p.version.document.case_id);Case.objects.select_for_update().get(pk=p.version.document.case_id);evaluation.locked(p.version.document.case_id)
 job=PublicationJob.objects.select_for_update().get(pk=job_id);check_fence(job,fence)
 from adapters.publications import InternalPublicationAdapter
 if InternalPublicationAdapter().lookup(p):return str(p.pk)
 b=exact(p.version.document.case,p.version_id);reviewer(p.actor,b,'publisher');current(b);r=approved(b);policies,users,retention=requirements(b)
 from apps.workflows.readiness import gate
 gate(b.handoff.case,'publication',source_job=job_id)
 if (policies,users,retention,r.pk)!=(p.policies,p.recipient_ids,p.retention_days,p.review_id):raise ValidationError('Publication snapshot changed')
 for user in users:PublicationReceipt.objects.create(publication=p,recipient_id=user,operation_key=f'{p.operation_key}:user:{user}',payload=b.version.payload,payload_sha256=b.version.payload_sha256)
 return str(p.pk)

def recipient_access(a,receipt):
 b=binding(receipt.publication.version)
 if not b:return
 config,v=rules(b.handoff.case)
 if a.pk!=receipt.recipient_id or config.pk!=b.policy_id or a.pk not in recipients(b.handoff.case,v) or v['audience']!=b.version.audience:raise PermissionDenied('Current exact metadata audience permission required')

@transaction.atomic
@evaluation.evaluated
def report(a,case_id,pk):
 c=h.locked(a,case_id,'finance.handoff.read');b=exact(c,pk);access(a,b);findings=[]
 try:current(b);approved(b);requirements(b)
 except (PermissionDenied,ValidationError,ConnectionError):findings=['Current source, acceptance, audience or independent document review is held']
 return {'version':pk,'number':b.version.number,'handoff':b.handoff_id,'payload':b.version.payload,'findings':findings,'reviews':list(b.version.reviews.values('id','actor_id','verdict','note')),'publications':list(Publication.objects.filter(version=b.version).values('id','recipient_ids','job__id','job__status','job__attempts')),'receipts':list(PublicationReceipt.objects.filter(publication__version=b.version).values('id','publication_id','recipient_id','payload_sha256')),'posted':False,'whole_product_accepted':False}


@transaction.atomic
@evaluation.evaluated
def operate(a,case_id,job_id,action,reason,expected=None):
 from apps.documents.delivery import check_fence
 c=h.locked(a,case_id,'document.operate',expected)
 j=PublicationJob.objects.select_for_update().select_related('publication__version__document').filter(pk=job_id,publication__version__document__case=c).first()
 if not j or action not in ['cancel','retry'] or not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Exact native job, typed recovery and bounded reason required')
 b=exact(c,j.publication.version_id);access(a,b)
 from adapters.publications import InternalPublicationAdapter
 if InternalPublicationAdapter().lookup(j.publication):raise ValidationError('Committed receipts require worker reconciliation')
 if j.status in ['unknown','confirmed','cancelled'] or j.status=='leased':raise ValidationError('Uncertain or finished work requires receipt reconciliation, not reset')
 if action=='retry':
  if j.status!='held' or j.attempts>=5:raise ValidationError('Only unchanged held work within its original attempt budget may retry')
  p=j.publication;reviewer(p.actor,b,'publisher');current(b);r=approved(b);policies,users,retention=requirements(b)
  if (policies,users,retention,r.pk)!=(p.policies,p.recipient_ids,p.retention_days,p.review_id):raise ValidationError('Changed publication requires a fresh reviewed revision')
  j.status='pending'
 else:j.status='cancelled'
 j.error=reason;j.save(update_fields=['status','error'])
 event(a,c,'agent.data.finance_metadata_operator_'+action,job=j.pk);bump(c);return j
