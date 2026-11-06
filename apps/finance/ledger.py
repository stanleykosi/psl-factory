"""F01 incumbent references only; all incumbent posting remains a Finance action."""
import json
from datetime import date
from django.db import transaction,connection
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.identity.models import Grant
from apps.pmo.services import subject
from apps.documents.contracts import validate,digest
from apps.policy.services import active_component,reference_values,decision_authority
from apps.policy.ledger_validators import RULES,AUTH
from adapters.forecast import obj,KEY
from adapters.hrfinance import timestamp,day
from adapters.ledger import SuppliedQuickBooksReadAdapter
from .models import LedgerLineage,LedgerCheck,LedgerDecision,FinanceRun,ScheduleWork
from apps.policy.schedule_validators import ID
SOURCE=obj({'provider':{'const':'quickbooks'},'realm':KEY,'entity':KEY,'source_reference':KEY,'transaction_date':{'type':'string'},'accounting_period':{'type':'string','pattern':r'^\d{4}-(0[1-9]|1[0-2])$'},'treatment_evidence_id':ID,'incumbent_user_reference':KEY,'posting_evidence_id':ID,'target_reference':{'anyOf':[KEY,{'type':'null'}]},'outcome':{'enum':['reported_posted','uncertain']},'provenance':{'type':'array','maxItems':20,'items':obj({'kind':{'enum':['finance_mapping','ppe_register','ppe_schedule']},'id':ID})}})
RESPONSE=obj({'provider':{'const':'quickbooks'},'realm':KEY,'entity':KEY,'source_reference':KEY,'target_reference':{'anyOf':[KEY,{'type':'null'}]},'state':{'enum':['found','not_found','unknown','multiple']},'observed_at':{'type':'string'},'transaction_date':{'type':'string'},'accounting_period':{'type':'string'},'treatment_evidence_id':ID,'incumbent_version':{'anyOf':[KEY,{'type':'null'}]}})
def readable(a,c):
 if not get_user_model().objects.filter(pk=a.pk,is_active=True).exists():raise PermissionDenied('Active principal required')
 for k in ['case.read','finance.read','ledger.read']:require(a,c,k)
def scope_lock(case_id,member_ids=(),extra_case_ids=()):
 # Lock complete known participant scopes in one order. A concurrent newly joined scope holds use.
 from apps.core.models import Case
 from .ledger_models import LedgerResolution,LedgerResolutionMember
 def closure(ids):
  ids=set(ids)
  while True:
   packets=LedgerResolution.objects.filter(members__lineage__case_id__in=ids).values('pk')
   joined=set(LedgerResolutionMember.objects.filter(resolution_id__in=packets).values_list('lineage__case_id',flat=True))
   if joined<=ids:return ids
   ids|=joined
 case_ids=closure({Case.objects.get(pk=case_id).pk}|set(extra_case_ids)|set(LedgerLineage.objects.filter(pk__in=member_ids).values_list('case_id',flat=True)))
 cases=list(Case.objects.select_for_update().filter(pk__in=case_ids).order_by('pk'))
 if not closure(case_ids)<=case_ids:raise ValidationError('Resolution participant scopes changed; refresh')
 grants=list(Grant.objects.select_for_update().filter(case_id__in=case_ids).order_by('pk'))
 list(get_user_model().objects.select_for_update().filter(pk__in={g.user_id for g in grants}).order_by('pk'))

def locked(a,case_id,action,expected=None):
 scope_lock(case_id)
 c=lock_case(a,case_id,action,expected);readable(a,c);return c
def config(c,k):
 p=active_component(k,c);return p,reference_values(p)[0]
def identity(c,p):return digest({'tenant':c.tenant,**{k:p[k] for k in ['provider','realm','entity','source_reference']}})
def target_lock(c,p):
 if p['target_reference']:identity_lock(digest({'tenant':c.tenant,'provider':p['provider'],'realm':p['realm'],'target':p['target_reference']}))
def identity_lock(key):
 with connection.cursor() as cur:cur.execute('SELECT pg_advisory_xact_lock(%s)',[int(key[:15],16)])
def exact(c,pk):
 w=LedgerLineage.objects.filter(case=c,pk=pk).first()
 if not w:raise ValidationError('Exact case lineage required')
 return w
def target_conflict(w):
 p=w.payload
 if not p['target_reference']:return False
 from .ledger_resolution import exclusions
 retired,_=exclusions(w)
 return LedgerLineage.objects.filter(case__tenant=w.case.tenant,payload__provider=p['provider'],payload__realm=p['realm'],payload__target_reference=p['target_reference']).exclude(identity=w.identity).exclude(pk__in=retired).exists()
def is_head(w):
 from .ledger_resolution import exclusions
 retired,_=exclusions(w)
 return w.pk not in retired and not LedgerLineage.objects.filter(identity=w.identity,pk__gt=w.pk).exclude(pk__in=retired).exists()
@transaction.atomic
def capture(a,case_id,evidence_id,predecessor=None,expected=None):
 c=locked(a,case_id,'ledger.capture',expected);e=subject(c,evidence_id,'ledger_source')
 p=SuppliedQuickBooksReadAdapter().source(e,SOURCE)
 day(p['transaction_date'])
 subject(c,p['treatment_evidence_id']);subject(c,p['posting_evidence_id'])
 for r in p['provenance']:
  q=FinanceRun.objects.filter(case=c,pk=r['id'],kind='mapping') if r['kind']=='finance_mapping' else ScheduleWork.objects.filter(case=c,pk=r['id'],kind=r['kind'])
  if not q.exists():raise ValidationError('Exact case mapping or asset provenance required')
 key=identity(c,p);identity_lock(key);target_lock(c,p)
 prev=exact(c,predecessor) if predecessor else None
 if prev and (prev.identity!=key or not is_head(prev)):raise ValidationError('Correction must extend current identical source identity')
 w=LedgerLineage.objects.create(case=c,actor=a,evidence=e,predecessor=prev,identity=key,payload=p)
 event(a,c,'ledger.capture',lineage=w.pk,duplicate=LedgerLineage.objects.filter(identity=key).exclude(pk=w.pk).exists());bump(c);return w
def context(w):
 p,v=config(w.case,RULES);s=w.payload
 if s['incumbent_user_reference'] not in v['incumbent_user_references']:raise ValidationError('Configured incumbent user reference required; native system rights remain unverified')
 if any(s[k]!=v[k] for k in ['entity','realm','provider']) or s['treatment_evidence_id'] not in v['treatment_evidence_ids']:raise ValidationError('Configured incumbent scope and Finance treatment required')
 return p,v
@transaction.atomic
def verify(a,case_id,pk,evidence_id,expected=None):
 c=locked(a,case_id,'ledger.verify',expected);w=exact(c,pk);identity_lock(w.identity);target_lock(c,w.payload);p,v=context(w)
 e=subject(c,evidence_id);r=SuppliedQuickBooksReadAdapter().read(e,RESPONSE)
 at=timestamp(r['observed_at']);age=(timezone.now()-at).total_seconds()
 if age<0 or age>v['max_age_seconds']:raise ValidationError('Current incumbent observation required')
 for k in ['provider','realm','entity','source_reference','transaction_date','accounting_period','treatment_evidence_id']:
  if r[k]!=w.payload[k]:raise ValidationError('Exact incumbent/source correlation required')
 duplicates=LedgerLineage.objects.filter(identity=w.identity).exclude(pk=w.pk)
 # Only one explicit same-case successor chain may be resolved by a fresh observation.
 allowed=set();cur=w
 while cur.predecessor_id:
  allowed.add(cur.predecessor_id);cur=cur.predecessor
 from .ledger_resolution import exclusions,enrolled
 retired,resolution=exclusions(w)
 conflict=duplicates.exclude(pk__in=allowed|retired).exists()
 status='candidate' if is_head(w) and not conflict and not target_conflict(w) and r['state']=='found' and r['target_reference'] and r['target_reference']==w.payload['target_reference'] and r['incumbent_version'] else 'held'
 if w.predecessor_id and enrolled(c) and (not resolution or resolution['selected']!=w.pk):status='held'
 if resolution and at<=timestamp(resolution['reviewed_at']):status='held'
 pins={RULES:p.pk}
 if resolution:pins['resolution']=resolution
 x=LedgerCheck.objects.create(lineage=w,actor=a,evidence=e,payload=r,snapshot=pins,status=status)
 event(a,c,'ledger.verify',check=x.pk,status=status,native_verified=False);bump(c);return x
def current(x):
 w=x.lineage;readable(w.actor,w.case);require(w.actor,w.case,'ledger.capture');readable(x.actor,w.case);require(x.actor,w.case,'ledger.verify');p,v=context(w)
 if target_conflict(w):raise ValidationError('Incumbent target reference claimed by another source')
 from .ledger_resolution import exclusions,enrolled
 retired,resolution=exclusions(w);pins={RULES:p.pk}
 if resolution:pins['resolution']=resolution
 if x.status!='candidate' or not is_head(w) or w.checks.order_by('-pk').first().pk!=x.pk or x.snapshot!=pins:raise ValidationError('Fresh current unambiguous verification required')
 if w.predecessor_id and enrolled(w.case) and (not resolution or resolution['selected']!=w.pk):raise ValidationError('Current reviewed correction resolution required')
 if resolution and (x.created_at<=timestamp(resolution['reviewed_at']) or timestamp(x.payload['observed_at'])<=timestamp(resolution['reviewed_at'])):raise ValidationError('Fresh post-decision incumbent verification required')
 age=(timezone.now()-timestamp(x.payload['observed_at'])).total_seconds()
 if not 0<=age<=v['max_age_seconds']:raise ValidationError('Incumbent observation expired')
 # A later duplicate anywhere invalidates an earlier review immediately.
 ancestors=set();cur=w
 while cur.predecessor_id:ancestors.add(cur.predecessor_id);cur=cur.predecessor
 if LedgerLineage.objects.filter(identity=w.identity).exclude(pk__in=ancestors|{w.pk}|retired).exists():raise ValidationError('Unresolved duplicate source identity')
def authority(a,x):
 c=x.lineage.case;readable(a,c);require(a,c,'ledger.review');p,v=config(c,AUTH)
 if a.pk not in v['user_ids'] or (v['independent_reviewer'] and a.pk in [x.actor_id,x.lineage.actor_id]):raise PermissionDenied('Configured independent Finance reviewer required')
 return {AUTH:p.pk,**decision_authority(a,c,'Finance')}
@transaction.atomic
def review(a,case_id,pk,evidence_id,verdict='approve',expected=None):
 c=locked(a,case_id,'ledger.review',expected);x=LedgerCheck.objects.filter(lineage__case=c,pk=pk).first()
 if not x or verdict not in ['approve','reject']:raise ValidationError('Exact check and decision required')
 identity_lock(x.lineage.identity);target_lock(c,x.lineage.payload);auth=authority(a,x)
 if verdict=='approve':current(x)
 r=LedgerDecision.objects.create(verification=x,actor=a,evidence=subject(c,evidence_id),verdict=verdict,authority=auth)
 event(a,c,'ledger.review',decision=r.pk,verdict=verdict);bump(c);return r
@transaction.atomic
def report(a,case_id,pk):
 c=locked(a,case_id,'ledger.read');w=exact(c,pk);identity_lock(w.identity);target_lock(c,w.payload);x=w.checks.order_by('-pk').first()
 if not x:raise ValidationError('Incumbent verification required')
 current(x);r=x.decisions.order_by('-pk').first()
 if not r or r.verdict!='approve' or r.authority!=authority(r.actor,x):raise ValidationError('Current Finance review required')
 return {'lineage_id':w.pk,'source':w.payload,'check_id':x.pk,'review_id':r.pk,'incumbent':x.payload,'verification_mode':'supplied_read_only','native_authenticity_verified':False,'posting_performed':False}
