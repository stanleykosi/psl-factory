"""Human adjudication of supplied claims. No incumbent posting, reversal or retry interface."""
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import event,bump
from apps.identity.services import require
from apps.agents.boundary import lock_principals
from apps.documents.contracts import digest,validate
from apps.pmo.services import subject
from apps.policy.models import PolicyState
from apps.policy.ledger_validators import RESOLUTION,resolution_principal
from apps.policy.services import decision_authority
from adapters.forecast import KEY
from adapters.ledger import SuppliedQuickBooksReadAdapter
from . import ledger as d
from .ledger_models import LedgerResolution as Resolution,LedgerResolutionMember as Member,LedgerResolutionReview as Review

def enrolled(c):return PolicyState.objects.filter(configuration__case=c,configuration__component=RESOLUTION,state='active').exists()

def authority(a,c,purpose):
 d.readable(a,c);require(a,c,'ledger.resolve' if purpose=='proposer' else 'ledger.resolve_review');p,v=d.config(c,RESOLUTION)
 if resolution_principal(c,v,purpose).pk!=a.pk:raise PermissionDenied('Exact configured Finance resolution principal required')
 return {'policy':p.pk,'role':decision_authority(a,c,'Finance')}

def ancestors(w):
 ids=set();cur=w
 while cur.predecessor_id:
  if len(ids)>=100 or cur.predecessor_id in ids:raise ValidationError('Correction lineage budget or cycle')
  ids.add(cur.predecessor_id);cur=cur.predecessor
 return ids

def related(selected,retired):
 targets={w.payload['target_reference'] for w in [selected,*retired] if w.payload['target_reference']}
 p=selected.payload
 query=Q(identity=selected.identity)
 if targets:query|=Q(payload__provider=p['provider'],payload__realm=p['realm'],payload__target_reference__in=sorted(targets))
 return d.LedgerLineage.objects.filter(case__tenant=selected.case.tenant).filter(query).order_by('pk')

def proof(x):
 w=x.lineage;d.readable(w.actor,w.case);require(w.actor,w.case,'ledger.capture');d.readable(x.actor,w.case);require(x.actor,w.case,'ledger.verify');p,v=d.context(w)
 value=SuppliedQuickBooksReadAdapter().checked_observation(w,x,d.RESPONSE,v)
 return {'rule':p.pk,'observation':digest(value),'lineage':digest(w.payload),'evidence':w.evidence.sha256,'check':x.pk}

def member_scope(a,rows,purpose):
 cases={w.case_id:w.case for w in rows};out={}
 for pk,c in sorted(cases.items(),key=lambda pair:str(pair[0])):
  auth=authority(a,c,purpose);_,v=d.config(c,RESOLUTION)
  if len(cases)>1 and not v['allow_cross_case']:raise ValidationError('Cross-case resolution not configured in every participant scope')
  if len(rows)>v['max_members']:raise ValidationError('Resolution member budget exceeded')
  out[str(pk)]=auth
 return out

def build_snapshot(a,selected,rows,retired_ids,mode):
 auth=member_scope(a,rows,'proposer');members=[]
 for w in rows:
  _,rules=d.config(w.case,RESOLUTION)
  if mode not in rules['allowed_modes']:raise ValidationError('Resolution mode not configured for every participant')
  if any(w.payload[k]!=selected.payload[k] for k in ['provider','realm','entity']):raise ValidationError('Exact entity/realm resolution scope required')
  x=w.checks.select_related('lineage__case','actor','evidence').order_by('-pk').first()
  if not x:raise ValidationError('Every claim requires current incumbent read evidence')
  pins=proof(x);members.append({'lineage':w.pk,'proof':pins,'disposition':'selected' if w.pk==selected.pk else 'retired' if w.pk in retired_ids else 'retained'})
 if d.LedgerLineage.objects.filter(predecessor=selected).exists():raise ValidationError('Select an actual correction-chain head')
 chosen=next(w.checks.order_by('-pk').first() for w in rows if w.pk==selected.pk)
 if chosen.payload['target_reference']!=selected.payload['target_reference'] or selected.payload['target_reference'] is None:raise ValidationError('Selected mapping needs exact found target/version evidence')
 economic=['provider','realm','entity','source_reference','transaction_date','accounting_period']
 for w in rows:
  x=w.checks.order_by('-pk').first()
  if w.pk in retired_ids:
   if w.identity!=selected.identity or any(w.payload[k]!=selected.payload[k] for k in economic) or subject(w.case,w.payload['treatment_evidence_id']).sha256!=subject(selected.case,selected.payload['treatment_evidence_id']).sha256:raise ValidationError('Retirement cannot erase a different transaction or treatment')
   if x.payload['target_reference']!=chosen.payload['target_reference'] or x.payload['incumbent_version']!=chosen.payload['incumbent_version']:raise ValidationError('Exact matching incumbent target/version required for retired claims')
  elif w.pk!=selected.pk:
   if w.identity==selected.identity or x.payload['target_reference']!=w.payload['target_reference'] or w.payload['target_reference']==selected.payload['target_reference']:raise ValidationError('Retained source still conflicts with selected mapping')
 if mode=='reference_correction':
  if not selected.predecessor_id or not ancestors(selected)<=retired_ids:raise ValidationError('Retire every explicit corrected-reference ancestor and adjudicate any duplicate aliases')
 elif mode=='duplicate_alias':
  if any(w.identity!=selected.identity or w.payload['target_reference']!=selected.payload['target_reference'] for w in rows) or any(w.pk in ancestors(selected) or selected.pk in ancestors(w) for w in rows if w.pk!=selected.pk):raise ValidationError('Duplicate aliases must be disconnected claims for the identical mapping')
 else:raise ValidationError('Typed resolution mode required')
 return {'schema':'psl.ledger-resolution/v1','selected':selected.pk,'mode':mode,'members':members,'authority':auth,'posting_performed':False,'verification_mode':'supplied_read_only'}

def locked_scope(a,case_id,ids,purpose,expected=None):
 if not isinstance(ids,list) or not 2<=len(ids)<=100 or len(ids)!=len(set(ids)) or any(type(x) is not int or x<1 for x in ids):raise ValidationError('Distinct bounded exact claim IDs required')
 d.scope_lock(case_id,ids)
 initial=list(d.LedgerLineage.objects.select_related('case').filter(pk__in=ids))
 if len(initial)!=len(ids) or str(case_id) not in {str(w.case_id) for w in initial}:raise ValidationError('Exact anchor/participant claims required')
 for c in Case.objects.select_for_update().filter(pk__in={w.case_id for w in initial}).order_by('pk'):
  lock_principals(c);d.readable(a,c)
 anchor=Case.objects.get(pk=case_id)
 if expected is not None and expected!=anchor.revision:raise ValidationError('Stale revision; refresh')
 member_scope(a,initial,purpose)
 for key in sorted({w.identity for w in initial}):d.identity_lock(key)
 for key in sorted({digest({'tenant':w.case.tenant,'provider':w.payload['provider'],'realm':w.payload['realm'],'target':w.payload['target_reference']}) for w in initial if w.payload['target_reference']}):d.identity_lock(key)
 return anchor,sorted(initial,key=lambda w:w.pk)

@transaction.atomic
def propose(a,case_id,selected_id,retired_ids,member_ids,mode,reference,predecessor,evidence_id,reason,expected=None):
 c,rows=locked_scope(a,case_id,member_ids,'proposer',expected);validate(KEY,reference)
 if type(selected_id) is not int or not isinstance(retired_ids,list) or any(type(x) is not int or x<1 for x in retired_ids) or not retired_ids or len(retired_ids)!=len(set(retired_ids)) or not set(retired_ids)<set(member_ids) or selected_id in retired_ids:raise ValidationError('Explicit proper retired claim subset required')
 selected=next((w for w in rows if w.pk==selected_id and w.case_id==c.pk),None)
 if not selected or not isinstance(reason,str) or not 1<=len(reason.strip())<=400:raise ValidationError('Selected anchor mapping and bounded human reason required')
 retired=[w for w in rows if w.pk in retired_ids]
 if {w.pk for w in related(selected,retired)}!=set(member_ids):raise ValidationError('Exact complete source/target conflict population required; obtain authorised evidence')
 e=subject(c,evidence_id,'ledger_resolution');old=Resolution.objects.filter(case=c,reference=reference).order_by('-version').first()
 snapshot=build_snapshot(a,selected,rows,set(retired_ids),mode)
 if old and old.snapshot==snapshot and old.evidence_id==e.pk and old.actor_id==a.pk and old.reason==reason:return old
 if predecessor!=(old.pk if old else None):raise ValidationError('Explicit latest resolution predecessor required')
 row=Resolution.objects.create(case=c,reference=reference,version=old.version+1 if old else 1,predecessor=old,selected=selected,mode=mode,snapshot=snapshot,evidence=e,reason=reason,actor=a)
 Member.objects.bulk_create([Member(resolution=row,lineage=w,verification_id=next(m['proof']['check'] for m in snapshot['members'] if m['lineage']==w.pk),disposition=next(m['disposition'] for m in snapshot['members'] if m['lineage']==w.pk)) for w in rows])
 event(a,c,'agent.data.ledger_resolution_proposed',resolution=row.pk);bump(c);return row

def current(r,for_review=False):
 members=list(r.members.select_related('lineage__case','verification__lineage__case','verification__actor','verification__evidence').order_by('lineage_id'));rows=[m.lineage for m in members];retired=[m.lineage for m in members if m.disposition=='retired']
 if not members or Resolution.objects.filter(members__lineage_id__in=[w.pk for w in rows],pk__gt=r.pk).exists():raise ValidationError('A newer overlapping resolution requires current review')
 if {w.pk for w in related(r.selected,retired)}!={w.pk for w in rows}:raise ValidationError('Claim population changed')
 if member_scope(r.actor,rows,'proposer')!=r.snapshot['authority']:raise ValidationError('Resolution authority/policy changed')
 for m in members:
  old=next(p['proof'] for p in r.snapshot['members'] if p['lineage']==m.lineage_id)
  if proof(m.verification)!=old:raise ValidationError('Resolution source/read basis changed')
  latest=m.lineage.checks.order_by('-pk').first()
  if latest.pk!=m.verification_id:
   if for_review or m.disposition=='retired':raise ValidationError('Resolution read evidence changed')
   proof(latest)
   # New post-decision selected reads are expected, but cannot change the adjudicated fact.
   if {k:v for k,v in latest.payload.items() if k!='observed_at'}!={k:v for k,v in m.verification.payload.items() if k!='observed_at'}:raise ValidationError('New incumbent result requires a resolution successor')
 if for_review and build_snapshot(r.actor,r.selected,rows,{w.pk for w in retired},r.mode)!=r.snapshot:raise ValidationError('Resolution context changed')
 return members

def accepted(r):
 members=current(r);rr=r.reviews.select_related('actor').order_by('-pk').first()
 if not rr or rr.verdict!='confirm':raise ValidationError('Independent current Finance resolution review required')
 if rr.actor_id in {r.actor_id}|{m.lineage.actor_id for m in members}|{m.verification.actor_id for m in members}:raise PermissionDenied('Independent resolution reviewer required')
 if member_scope(rr.actor,[m.lineage for m in members],'reviewer')!=rr.authority:raise ValidationError('Resolution reviewer authority changed')
 for m in members:
  _,v=d.config(m.lineage.case,RESOLUTION)
  if (timezone.now()-rr.created_at).total_seconds()>v['decision_ttl_seconds']:raise ValidationError('Resolution decision expired')
 return rr,members

@transaction.atomic
def review(a,case_id,pk,verdict,evidence_id,expected=None):
 r=Resolution.objects.select_related('case','selected').filter(case_id=case_id,pk=pk).first()
 if not r or verdict not in ['confirm','return','withdraw']:raise ValidationError('Exact resolution and typed human verdict required')
 c,rows=locked_scope(a,case_id,list(r.members.values_list('lineage_id',flat=True)),'reviewer',expected)
 if a.pk in {r.actor_id}|{w.actor_id for w in rows}|set(r.members.values_list('verification__actor_id',flat=True)):raise PermissionDenied('Independent resolution reviewer required')
 if verdict=='confirm':current(r,True)
 rr=Review.objects.create(resolution=r,actor=a,verdict=verdict,authority=member_scope(a,rows,'reviewer'),evidence=subject(c,evidence_id,'ledger_resolution_review'))
 event(a,c,'agent.data.ledger_resolution_review',review=rr.pk,verdict=verdict);bump(c);return rr

def exclusions(w):
 # Resolve only the newest relevant packet. No fallback after withdrawal, staleness or a pending successor.
 p=w.payload;related_ids=d.LedgerLineage.objects.filter(case__tenant=w.case.tenant).filter(Q(identity=w.identity)|Q(payload__provider=p['provider'],payload__realm=p['realm'],payload__target_reference=p['target_reference'])).values_list('pk',flat=True)
 r=Resolution.objects.filter(members__lineage_id__in=related_ids).order_by('-pk').first()
 if not r:return set(),None
 try:rr,members=accepted(r)
 except (ValidationError,PermissionDenied):return set(),None
 return {m.lineage_id for m in members if m.disposition=='retired'},{'resolution':r.pk,'review':rr.pk,'selected':r.selected_id,'reviewed_at':rr.created_at.isoformat()}

def readable_packet(a,r):
 for m in r.members.select_related('lineage__case'):d.readable(a,m.lineage.case)

def visible_packets(a,c):
 rows=[]
 for r in Resolution.objects.filter(Q(case=c)|Q(members__lineage__case=c)).distinct().order_by('-pk')[:40]:
  try:readable_packet(a,r)
  except PermissionDenied:continue
  active=False
  try:accepted(r);active=True
  except (ValidationError,PermissionDenied):pass
  rows.append({'row':r,'current_reviewed':active,'members':list(r.members.select_related('lineage').order_by('lineage_id')),'reviews':r.reviews.order_by('-pk')})
 return rows

def visible_claims(a,c):
 from apps.identity.models import Grant
 cases=Case.objects.filter(tenant=c.tenant,pk__in=Grant.objects.filter(user=a,active=True,action='ledger.read').values('case_id'))
 allowed=[]
 for other in cases:
  try:d.readable(a,other)
  except PermissionDenied:continue
  allowed.append(other.pk)
 return d.LedgerLineage.objects.filter(pk__in=list(d.LedgerLineage.objects.filter(case_id__in=allowed).order_by('-pk').values_list('pk',flat=True)[:200]))

def visible_evidence(a,c):
 hidden=set()
 for r in Resolution.objects.filter(case=c):
  try:readable_packet(a,r)
  except PermissionDenied:
   hidden.add(r.evidence_id);hidden.update(r.reviews.values_list('evidence_id',flat=True))
 return c.evidence.filter(kind__in=['ledger_resolution','ledger_resolution_review']).exclude(pk__in=hidden).order_by('-pk')[:40]
