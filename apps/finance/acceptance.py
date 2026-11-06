"""Private Finance handoff, recipient validation and separate human AF13 acceptance."""
from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.identity.services import require
from apps.core.services import event,bump
from apps.documents.contracts import digest,validate
from apps.documents import validation as af13
from apps.policy.ledger_validators import HANDOFF as COMPONENT
from adapters.forecast import KEY
from adapters.finance_acceptance import FinanceAcceptanceAdapter
from . import ledger_agents as finance
from . import acceptance_evaluation as evaluation
from .acceptance_models import FinanceHandoff as Handoff,FinanceHandoffDecision as Decision

def readable(a,c):
 if a is None:raise PermissionDenied('Native private Finance principal required')
 finance.source_access(a,c)
 for action in ['validation.read','finance.handoff.read']:require(a,c,action)

def locked(a,case_id,action,expected=None):
 c=finance.locked(a,case_id,action,expected);readable(a,c);evaluation.locked(c.pk);return c

def rules(c):return finance.ledger.config(c,COMPONENT)

def participant(a,p,key,v):
 readable(a,p.case)
 if a.pk!=v[key+'_id']:raise PermissionDenied('Exact configured handoff principal required')
 if key=='recipient':
  require(a,p.case,'finance.handoff.receive');require(a,p.case,'finance.handoff.validate')
  return {k:af13.owner_authority(a,p,k) for k in ['meaning','expectations']}
 require(a,p.case,'finance.handoff.accept');return {'acceptance':af13.owner_authority(a,p,'acceptance')}

def access(a,h):
 readable(a,h.case);finance.projection_access(a,h.draft.source.projection)

def exact(c,pk):
 h=Handoff.objects.select_related('case','draft__source__projection','draft__owner','package__case','actor','recipient','acceptor').filter(case=c,pk=pk).first()
 if not h:raise ValidationError('Exact case Finance handoff required')
 return h

def pins(a,draft,p):
 readable(a,p.case);require(a,p.case,'finance.handoff.prepare')
 if a.pk!=draft.owner_id or draft.case_id!=p.case_id:raise PermissionDenied('Exact original Finance owner/case required')
 from .readiness_acceptance import binding as private_binding
 if private_binding(p) or hasattr(p,'private_protection_packet'):raise ValidationError('Private readiness packages cannot recursively become Finance source handoffs')
 af13.package_current(p);policy,v=rules(p.case)
 if p.pk not in v['package_ids'] or 'F01' not in p.payload['process_ids'] or COMPONENT in p.payload['policy_components']:raise ValidationError('Configured nonrecursive F01 package required')
 if a.pk in [v['recipient_id'],v['acceptor_id']]:raise PermissionDenied('Finance preparer, recipient and acceptor must be distinct')
 auth={}
 for key in ['recipient','acceptor']:
  person=get_user_model().objects.filter(pk=v[key+'_id'],is_active=True).first()
  if person is None:raise PermissionDenied('Actual active handoff principal required')
  finance.projection_access(person,draft.source.projection);auth[key]=participant(person,p,key,v)
 return {'case':str(p.case_id),'policy':policy.pk,'package':p.pk,'package_sha256':p.sha256,'finance':FinanceAcceptanceAdapter().read(a,draft),'recipient':v['recipient_id'],'acceptor':v['acceptor_id'],'authority':auth}

@transaction.atomic
@evaluation.evaluated
def prepare(a,case_id,draft_id,package_id,reference,predecessor=None,expected=None):
 c=locked(a,case_id,'finance.handoff.prepare',expected);validate(KEY,reference);draft=finance.draft_for(c,draft_id);p=af13.package_for(c,package_id);value=pins(a,draft,p)
 old=Handoff.objects.filter(case=c,reference=reference).order_by('-version').first()
 if old:
  access(a,old)
  if old.snapshot==value and old.draft_id==draft.pk and old.package_id==p.pk and predecessor in [None,old.parent_id]:return old
 if (old.pk if old else None)!=predecessor:raise ValidationError('Explicit latest handoff predecessor required')
 if Handoff.objects.filter(package=p).exclude(reference=reference).exists():raise ValidationError('Package already has another native handoff reference')
 # Preserve every historical private source before moving a chain to new evidence.
 for row in Handoff.objects.filter(case=c,reference=reference):access(a,row)
 h=Handoff.objects.create(case=c,reference=reference,version=old.version+1 if old else 1,parent=old,draft=draft,package=p,policy_id=value['policy'],recipient_id=value['recipient'],acceptor_id=value['acceptor'],actor=a,snapshot=value,sha256=digest(value))
 evaluation.changed();event(a,c,'agent.data.finance_handoff_prepared',handoff=h.pk);bump(c);return h

def current(h):
 checked=evaluation.checks(h.case_id);key=(h.pk,h.sha256)
 if checked is not None and key in checked:return
 if Handoff.objects.filter(case=h.case,reference=h.reference,version__gt=h.version).exists():raise ValidationError('Handoff superseded; old decisions remain historical')
 if h.snapshot!=pins(h.actor,h.draft,h.package) or h.sha256!=digest(h.snapshot):raise ValidationError('Exact Finance/package/policy/recipient context changed')
 _,v=rules(h.case)
 if (timezone.now()-h.created_at).total_seconds()>v['freshness_seconds']:raise ValidationError('Finance handoff expired; explicit reviewed successor required')
 if checked is not None:checked.add(key)

def latest(h,phase):return h.decisions.filter(phase=phase).select_related('actor').order_by('-pk').first()

def authority(a,h,phase):
 access(a,h)
 if a.pk!=(h.acceptor_id if phase=='accept' else h.recipient_id):raise PermissionDenied('Exact named handoff-record principal required')
 _,v=rules(h.case);return participant(a,h.package,'acceptor' if phase=='accept' else 'recipient',v)

def decision_pins(h,phase):
 current(h);value={'handoff':h.pk,'sha256':h.sha256}
 if phase in ['validate','accept']:value['receive']=confirmed(h,'receive').pk
 if phase=='accept':
  value['validate']=confirmed(h,'validate').pk
  value['af13_acceptance']=af13.approved_review(h.package,'acceptance').pk
 return value

def confirmed(h,phase):
 return evaluation.confirmed(h.case_id,('handoff',h.pk,phase),lambda:_confirmed(h,phase))

def _confirmed(h,phase):
 r=latest(h,phase)
 if not r or r.verdict!='confirm':raise ValidationError('Current explicit '+phase+' confirmation required')
 if r.authority!=authority(r.actor,h,phase) or r.snapshot!=decision_pins(h,phase):raise ValidationError('Handoff decision inputs/authority changed')
 return r

@transaction.atomic
@evaluation.evaluated
def decide(a,case_id,pk,phase,verdict,key,reason,expected=None):
 if phase not in ['receive','validate','accept'] or verdict not in ['confirm','return','withdraw']:raise ValidationError('Typed handoff phase/verdict required')
 c=locked(a,case_id,'finance.handoff.'+phase,expected);h=exact(c,pk);auth=authority(a,h,phase);validate(KEY,key)
 if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Bounded actual human decision reason required')
 old=Decision.objects.filter(handoff=h,operation_key=key).first()
 if old:
  if (old.actor_id,old.phase,old.verdict,old.reason)!=(a.pk,phase,verdict,reason):raise ValidationError('Decision intent conflicts')
  return old # Historical receipt, not a current-use assertion.
 value=decision_pins(h,phase) if verdict=='confirm' else {'handoff':h.pk,'sha256':h.sha256}
 r=Decision.objects.create(handoff=h,operation_key=key,phase=phase,verdict=verdict,reason=reason,snapshot=value,authority=auth,actor=a)
 evaluation.changed();event(a,c,'agent.data.finance_handoff_decided',handoff=h.pk,decision=r.pk,phase=phase,verdict=verdict);bump(c);return r

def package_access(a,p):
 from apps.documents.native_validation import package_access as native_access
 native_access(a,p)
 from .readiness_acceptance import package_access as private_access
 private_access(a,p)
 from apps.documents.protection_acceptance import package_access as protection_access
 protection_access(a,p)
 for h in Handoff.objects.filter(package=p).select_related('case','draft__source__projection'):access(a,h)

def review_pins(p,a):
 rows=list(Handoff.objects.filter(package=p).order_by('pk'))
 if not rows:return None
 if a is None:raise PermissionDenied('Native private Finance package access required')
 package_access(a,p);heads={}
 for h in rows:heads[h.reference]=h
 values=[]
 for h in heads.values():
  current(h);r=confirmed(h,'validate');values.append({'handoff':h.pk,'sha256':h.sha256,'validation':r.pk})
 return values

def visible_packages(a,c):
 q=af13.ValidationPackage.objects.filter(case=c);hidden=[]
 for p in q:
  try:package_access(a,p)
  except PermissionDenied:hidden.append(p.pk)
 return q.exclude(pk__in=hidden)

@transaction.atomic
@evaluation.evaluated
def report(a,case_id,pk):
 c=locked(a,case_id,'finance.handoff.read');h=exact(c,pk);access(a,h);states={}
 for phase in ['receive','validate','accept']:
  r=latest(h,phase);valid=False
  try:confirmed(h,phase);valid=True
  except (ValidationError,PermissionDenied,ConnectionError):pass
  states[phase]={'decision':r.pk if r else None,'verdict':r.verdict if r else 'pending','current':valid}
 return {'handoff':h.pk,'version':h.version,'parent':h.parent_id,'package':h.package_id,'draft':h.draft_id,'recipient':h.recipient_id,'acceptor':h.acceptor_id,'snapshot':h.snapshot,'states':states,'history':list(h.decisions.order_by('pk').values('id','phase','verdict','actor_id','reason','created_at')[:100]),'body':h.draft.body,'scoped_acceptance_current':states['accept']['current'],'native_quickbooks_verified':False,'whole_product_accepted':False,'posted':False,'published':False,'deployment_authorized':False}
