"""Partner facts, configured human decisions and exact local activity computation."""
import json,re
from datetime import date,timedelta
from zoneinfo import ZoneInfo
from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.services import event,bump
from apps.pmo.services import subject
from apps.pmo.clocks import aware
from apps.identity.services import require
from apps.policy.services import active_component,reference_values,decision_authority
from apps.policy.partner_validators import STAGES,DEADLINES,ACTIVITY,METER,SCHEMAS
from apps.finance.analysis import digest,note
from adapters.partner_operations import parse
from .reconciliation import locked as lock_baas
from .models import PartnerRecord,PartnerDecision,OnboardingEvent,PartnerReport,PartnerReportReview,PartnerFollowup,PartnerFinanceJob,PartnerFinanceReceipt,PartnerBillingImport

def locked(actor,case_id,action,expected):
    case=lock_baas(actor,case_id,action,expected);require(actor,case,'partner.read');return case

def rule(case,key):
    c=active_component(key,case);values=reference_values(c)
    from apps.policy.models import RegisteredReference
    raw=c.envelope['value'];refs=raw if isinstance(raw,list) else [raw]
    for ref in refs:
        name=ref['artifact_ref'] if isinstance(ref,dict) else ref;version=ref['artifact_version'] if isinstance(ref,dict) else 1
        if RegisteredReference.objects.get(case=case,ref=name,version=version).schema_ref!=SCHEMAS[key]:raise ValidationError('This action needs the typed partner namespace for '+key)
    return c,values

def exact(case,model,pk):
    lookup='case' if model is PartnerRecord else 'record__case' if model in [PartnerReport,OnboardingEvent] else 'report__record__case'
    r=model.objects.filter(pk=pk,**{lookup:case}).first()
    if not r:raise ValidationError('Choose the exact partner record in this case')
    return r

def current(record):
    if PartnerRecord.objects.filter(case=record.case,reference=record.reference,version__gt=record.version).exists():raise ValidationError('A newer partner source version exists')
    require(record.actor,record.case,'partner.capture');require(record.actor,record.case,'baas.read');require(record.actor,record.case,'partner.read')

def authority(actor,case,role,allowed,action):
    require(actor,case,action);require(actor,case,'baas.read');require(actor,case,'partner.read')
    if role not in allowed:raise PermissionDenied('Role is not configured for this partner action')
    return decision_authority(actor,case,role)

@transaction.atomic
def capture(actor,case_id,kind,reference,evidence_id,expected):
    case=locked(actor,case_id,'partner.capture',expected)
    if kind not in ['agreement','onboarding','activity'] or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',reference):raise ValidationError('Supply a bounded partner source reference and kind')
    e=subject(case,evidence_id,'partner_'+kind);v=parse(kind,e.body)
    old=PartnerRecord.objects.filter(case=case,reference=reference).order_by('-version').first()
    if old and (old.kind!=kind or any(old.payload[k]!=v[k] for k in ['partner','customer'])):raise ValidationError('Partner source revisions preserve kind/partner/customer identity')
    if old and old.evidence_id==e.pk:return old
    r=PartnerRecord.objects.create(case=case,reference=reference,kind=kind,version=old.version+1 if old else 1,evidence=e,payload=v,actor=actor)
    event(actor,case,'partner.source_captured',record=r.pk,predecessor=old.pk if old else None);bump(case);return r

def agreement_snapshot(record):
    current(record)
    if record.kind!='agreement':raise ValidationError('Select an executed agreement source')
    v=record.payload
    if not v.get('executed_evidence_id') or not v.get('executed_sha256'):raise ValidationError('Exact executed agreement evidence is missing; capture remains available')
    proof=subject(record.case,v['executed_evidence_id'],'signature')
    if proof.sha256!=v['executed_sha256']:raise ValidationError('Executed agreement source hash differs')
    c,v=rule(record.case,DEADLINES)
    return {'record':record.pk,'hash':record.evidence.sha256,'executed_evidence':proof.pk,'executed_hash':proof.sha256,'deadline_policy':c.pk},v[0]

@transaction.atomic
def decide_agreement(actor,case_id,record_id,purpose,verdict,role,evidence_id,reason,expected):
    case=locked(actor,case_id,'partner.agreement.decide',expected);r=exact(case,PartnerRecord,record_id);snapshot,m=agreement_snapshot(r);note(reason)
    allowed={'terms':['approve','return','reject'],'renewal':['review_renewal','review_notice','no_action','undecided']}
    if purpose not in allowed or verdict not in allowed[purpose]:raise ValidationError('Choose a terms decision or renewal/notice review intent')
    pins=authority(actor,case,role,m['agreement_roles'] if purpose=='terms' else m['renewal_roles'],'partner.agreement.decide')
    if purpose=='renewal':validated_terms(r)
    e=subject(case,evidence_id,'partner_decision')
    d=PartnerDecision.objects.create(record=r,purpose=purpose,verdict=verdict,role=role,snapshot=snapshot,authority=pins,evidence=e,reason=reason,actor=actor)
    event(actor,case,'partner.agreement_decided',decision=d.pk,purpose=purpose,verdict=verdict,external_notice=False,renewal_executed=False);bump(case);return d

def validated_terms(record):
    snapshot,m=agreement_snapshot(record);d=PartnerDecision.objects.filter(record=record,purpose='terms').order_by('-pk').first()
    if not d or d.verdict!='approve' or d.snapshot!=snapshot:raise ValidationError('Exact current human term validation is required')
    if authority(d.actor,record.case,d.role,m['agreement_roles'],'partner.agreement.decide')!=d.authority:raise ValidationError('Agreement authority changed')
    return d,m

def agreement_position(record,as_of=None):
    v=record.payload
    out={'as_of':str(as_of),'expires_on':v['expires_on'],'notice_on':v['notice_on'],'auto_renewal':v['auto_renewal'],'status':'unknown','followups':[],'findings':[]}
    try:
        _,m=validated_terms(record)
        as_of=as_of or timezone.now().astimezone(ZoneInfo(m['timezone'])).date();out['as_of']=str(as_of)
        expiry=date.fromisoformat(v['expires_on']) if v['expires_on'] else None
        expired=expiry is not None and (expiry<as_of or expiry==as_of and m['expiry_boundary']=='start_of_day')
        out['status']='unknown_expiry' if expiry is None else 'supplied_term_ended' if expired else 'not_started' if date.fromisoformat(v['starts_on'])>as_of else 'in_term'
        for key,lead in [('notice_on','notice_lead_days'),('expires_on','expiry_lead_days')]:
            if v[key] and as_of>=date.fromisoformat(v[key])-timedelta(days=m[lead]):out['followups'].append(key)
        if v['notice_on'] is None:out['findings'].append('Notice deadline unknown; no inferred clause interpretation')
    except (ValidationError,PermissionDenied) as exc:out['findings'].append(str(exc))
    return out

def stages(case):
    c,v=rule(case,STAGES);return c,{r['key']:r for r in v}

def stage_current(record):
    return OnboardingEvent.objects.filter(record=record).order_by('-sequence').first()

@transaction.atomic
def transition_stage(actor,case_id,record_id,operation,stage,occurred_at,role,evidence_id,required_evidence_ids,expected):
    case=locked(actor,case_id,'partner.onboarding.transition',expected);r=exact(case,PartnerRecord,record_id);current(r)
    if r.kind!='onboarding':raise ValidationError('Choose an onboarding source')
    c,catalogue=stages(case);last=stage_current(r);at=aware(occurred_at)
    if at>timezone.now() or last and at<last.occurred_at:raise ValidationError('Stage history must be actual and chronological')
    if stage not in catalogue or operation not in ['enter','pause','resume']:raise ValidationError('Choose a configured stage and history operation')
    m=catalogue[stage];pins=authority(actor,case,role,m['roles'],'partner.onboarding.transition')
    if last:
        if last.policy['catalogue']!=c.pk:raise ValidationError('Stage policy changed; reconcile history through an explicit source version before further transitions')
        if operation=='enter':
            if stage not in catalogue[last.stage]['next_stages']:raise ValidationError('Stage transition is not configured')
        elif stage!=last.stage or m['terminal'] or m['pause']!='freeze_elapsed' or (operation=='pause')==(last.operation=='pause'):raise ValidationError('Invalid pause/resume state')
    elif operation!='enter' or not m['initial']:raise ValidationError('First validated event must enter the configured initial stage')
    if not isinstance(required_evidence_ids,list) or len(required_evidence_ids)>100 or any(type(pk) is not int or pk<1 for pk in required_evidence_ids):raise ValidationError('Supply bounded exact required evidence IDs')
    e=subject(case,evidence_id,'partner_stage');proofs=[subject(case,pk) for pk in required_evidence_ids]
    if operation=='enter' and set(m['required_evidence_kinds'])-{e.kind for e in proofs}:raise ValidationError('Required stage completion/entry evidence is missing')
    value={'catalogue':c.pk,'authority':pins,'required_evidence':[{'id':e.pk,'hash':e.sha256} for e in proofs]}
    state=OnboardingEvent.objects.create(record=r,previous=last,sequence=last.sequence+1 if last else 1,operation=operation,stage=stage,occurred_at=at,role=role,policy=value,evidence=e,actor=actor)
    event(actor,case,'partner.stage_recorded',stage_event=state.pk,operation=operation);bump(case);return state

def age(record,as_of=None):
    as_of=as_of or timezone.now();out={'seconds':None,'stage':None,'paused':False,'terminal':False,'followup_due':False,'findings':[]}
    try:
        current(record);c,cat=stages(record.case);history=list(OnboardingEvent.objects.filter(record=record).order_by('sequence'))
        if not history:raise ValidationError('No validated stage-entry history; reported tracker dates are evidence only')
        last=history[-1];out['stage']=last.stage
        if any(h.policy['catalogue']!=c.pk for h in history):raise ValidationError('Historical stage policy differs; age needs explicit reconciliation')
        for h in history:
            if authority(h.actor,record.case,h.role,cat[h.stage]['roles'],'partner.onboarding.transition')!=h.policy['authority']:raise ValidationError('Stage holder authority changed')
        entered=max(i for i,h in enumerate(history) if h.operation=='enter');segment=history[entered:];m=cat[last.stage]
        if as_of<segment[-1].occurred_at:raise ValidationError('Age as-of precedes recorded history')
        elapsed=0
        for i,h in enumerate(segment):
            end=segment[i+1].occurred_at if i+1<len(segment) else as_of
            if h.operation!='pause' and not m['terminal']:elapsed+=int((end-h.occurred_at).total_seconds())
        out.update(seconds=elapsed,paused=last.operation=='pause',terminal=m['terminal'],followup_due=not m['terminal'] and m['followup_after_seconds'] is not None and elapsed>=m['followup_after_seconds'])
    except (ValidationError,PermissionDenied) as exc:out['findings'].append(str(exc))
    return out

@transaction.atomic
def followup(actor,case_id,record_id,source_key,owner_id,due_at,role,evidence_id,reason,expected):
    case=locked(actor,case_id,'partner.followup',expected);r=exact(case,PartnerRecord,record_id);current(r);note(reason)
    old=PartnerFollowup.objects.filter(record=r,source_key=source_key).first()
    if old:return old
    if r.kind=='agreement':
        _,m=validated_terms(r);pos=agreement_position(r)
        if source_key not in pos['followups']:raise ValidationError('This agreement reminder is not due')
        roles=m['followup_roles'];snapshot={'position':pos,'terms':agreement_snapshot(r)[0]}
    elif r.kind=='onboarding':
        pos=age(r);last=stage_current(r)
        if not pos['followup_due'] or source_key!='stage:'+str(last.pk if last else ''):raise ValidationError('No configured overdue stage follow-up is due')
        _,cat=stages(case);roles=cat[last.stage]['roles'];snapshot={'stage_event':last.pk,'age':pos}
    else:raise ValidationError('Follow-up requires an agreement or onboarding record')
    authority(actor,case,role,roles,'partner.followup')
    if due_at is None:raise ValidationError('Follow-up needs an explicit owned deadline')
    from apps.pmo.meetings import create_action
    item=create_action(actor,case.pk,'PARTNER:'+str(r.pk)+':'+source_key,'Partner '+r.reference+' '+source_key,owner_id,due_at,evidence_id,reason,None)
    f=PartnerFollowup.objects.create(record=r,source_key=source_key,snapshot=snapshot,action=item,actor=actor)
    event(actor,case,'partner.followup_created',followup=f.pk,action_item=item.pk,external_message=False);bump(case);return f

def activity_calculation(record):
    current(record)
    if record.kind!='activity':raise ValidationError('Choose activity source evidence')
    c,values=rule(record.case,ACTIVITY);m=values[0];v=record.payload;findings=[];zone=ZoneInfo(m['timezone'])
    if v['source'] not in m['sources']:findings.append('Unapproved activity source')
    seen=set();groups={p:{'count':0,'users':set(),'unknown_users':False} for p in v['products']}
    for e in v['events']:
        if e['event'] in seen:findings.append('Duplicate event identity: '+e['event'])
        seen.add(e['event'])
        if aware(e['at']).astimezone(zone).strftime('%Y-%m')!=v['period']:findings.append('Activity outside exact reporting period: '+e['event'])
        if e['product'] not in groups:findings.append('Product outside declared coverage: '+e['product']);continue
        if e['kind'] in m['excluded_kinds']:continue
        g=groups[e['product']];g['count']+=1
        if e['kind'] in m['active_kinds']:
            if e['user'] is None:g['unknown_users']=True
            else:g['users'].add(e['user'])
    relevant=[]
    for other in PartnerRecord.objects.filter(case=record.case,kind='activity').exclude(pk=record.pk):
        if other.payload['partner']==v['partner'] and other.payload['period']==v['period'] and not PartnerRecord.objects.filter(case=record.case,reference=other.reference,version__gt=other.version).exists():
            relevant.append(other.pk)
            if other.reference!=record.reference and other.payload['source']==v['source'] and seen & {e['event'] for e in other.payload['events']}:findings.append('Overlapping captured activity identities require reconciliation')
    if v['completeness']!='complete' and not m['allow_partial']:findings.append('Partial or unknown source coverage is not allowed for handoff')
    result={'status':'held' if findings else 'ready','partner':v['partner'],'customer':v['customer'],'period':v['period'],'coverage':v['completeness'],'scope':'selected_supplied_batch_only','activity_is_billable_usage':False,'findings':findings,'rows':[{'product':p,'event_count':g['count'] if not findings else None,'active_users':None if g['unknown_users'] or findings else len(g['users']),'coverage':v['completeness']} for p,g in groups.items()]}
    if any(g['unknown_users'] for g in groups.values()):result['findings'].append('Missing activity user identity; active-user metric unknown');result['status']='held'
    snapshot={'record':record.pk,'source_hash':record.evidence.sha256,'policy':c.pk,'other_relevant_current_sources':sorted(relevant)}
    return snapshot,result,m

@transaction.atomic
def build_report(actor,case_id,record_id,expected):
    case=locked(actor,case_id,'partner.report.calculate',expected);r=exact(case,PartnerRecord,record_id)
    if r.kind!='activity':raise ValidationError('Select activity evidence for a report')
    try:snapshot,result,_=activity_calculation(r)
    except (ValidationError,PermissionDenied) as exc:
        current(r);snapshot={'record':r.pk,'source_hash':r.evidence.sha256,'policy':None};result={'status':'held','findings':[str(exc)],'rows':[],'activity_is_billable_usage':False}
    h=digest({'snapshot':snapshot,'result':result});old=PartnerReport.objects.filter(record=r,sha256=h).first()
    if old:return old
    out=PartnerReport.objects.create(record=r,snapshot=snapshot,result=result,sha256=h,actor=actor);event(actor,case,'partner.activity_calculated',report=out.pk);bump(case);return out

def report_current(report):
    require(report.actor,report.record.case,'partner.report.calculate');require(report.actor,report.record.case,'baas.read')
    snapshot,result,m=activity_calculation(report.record)
    if digest({'snapshot':snapshot,'result':result})!=report.sha256:raise ValidationError('Activity source, definition or coverage changed; rebuild report')
    return m

@transaction.atomic
def review_report(actor,case_id,report_id,verdict,role,evidence_id,expected):
    case=locked(actor,case_id,'partner.report.review',expected);r=exact(case,PartnerReport,report_id);m=report_current(r)
    if verdict not in ['approve','return','reject']:raise ValidationError('Choose exact report disposition')
    if verdict=='approve' and r.result['status']!='ready':raise ValidationError('Resolve report findings before approval')
    if actor.pk==r.actor_id and not m['allow_preparer_review']:raise PermissionDenied('Report requires a distinct reviewer')
    pins=authority(actor,case,role,m['reviewer_roles'],'partner.report.review');e=subject(case,evidence_id,'partner_decision')
    out=PartnerReportReview.objects.create(report=r,verdict=verdict,role=role,snapshot={'hash':r.sha256,'policy':r.snapshot['policy']},authority=pins,evidence=e,actor=actor)
    event(actor,case,'partner.activity_reviewed',review=out.pk,verdict=verdict);bump(case);return out

def approved(report):
    m=report_current(report);d=PartnerReportReview.objects.filter(report=report).order_by('-pk').first()
    if not d or d.verdict!='approve' or d.snapshot!={'hash':report.sha256,'policy':report.snapshot['policy']}:raise ValidationError('Exact current report approval required')
    if authority(d.actor,report.record.case,d.role,m['reviewer_roles'],'partner.report.review')!=d.authority:raise ValidationError('Report reviewer authority changed')
    return d,m

def finance_intent(actor,report,role):
    d,m=approved(report);case=report.record.case;authority(actor,case,role,m['sender_roles'],'partner.finance.dispatch')
    from django.contrib.auth import get_user_model
    person=get_user_model().objects.filter(pk=m['recipient_id'],is_active=True).first()
    if not person:raise ValidationError('Finance recipient unavailable')
    require(person,case,'partner.finance.receive');require(person,case,'finance.read');decision_authority(person,case,'Finance')
    public={k:report.result[k] for k in ['partner','period','coverage','scope','activity_is_billable_usage']}
    public['rows']=[{k:r[k] for k in m['columns']} for r in report.result['rows']];public['report_hash']=report.sha256
    return {'report':report.pk,'review':d.pk,'hash':report.sha256,'recipient':person.pk,'role':role,'public':public,'lease_seconds':m['lease_seconds'],'max_attempts':m['max_attempts']}

@transaction.atomic
def reserve(actor,case_id,report_id,role,expected):
    case=locked(actor,case_id,'partner.finance.dispatch',expected);report=exact(case,PartnerReport,report_id);value=finance_intent(actor,report,role)
    old=PartnerFinanceJob.objects.filter(report=report).order_by('-generation').first()
    if old:
        if old.intent!=value:raise ValidationError('Reserved report intent changed; explicit operator reconciliation required')
        return old
    j=PartnerFinanceJob.objects.create(report=report,intent=value,actor=actor);event(actor,case,'partner.finance_reserved',job=j.pk);bump(case);return j

@transaction.atomic
def import_finance_usage(actor,case_id,receipt_id,role,evidence_id,expected):
    case=locked(actor,case_id,'partner.finance.import',expected);receipt=exact(case,PartnerFinanceReceipt,receipt_id)
    require(actor,case,'finance.read');require(actor,case,'partner.finance.receive');decision_authority(actor,case,'Finance')
    if actor.pk!=receipt.recipient_id:raise PermissionDenied('Only the appointed Finance recipient can accept meter evidence')
    if role!='Finance':raise PermissionDenied('Finance owns billing import')
    old=PartnerBillingImport.objects.filter(receipt=receipt).first()
    if old:return old
    r=receipt.report.record;current(r);c,vals=rule(case,METER);m=vals[0];v=r.payload
    from apps.finance.models import BillingCoverage
    from apps.finance import billing
    cov=BillingCoverage.objects.get(pk=m['coverage_id'],case=case)
    if not billing.coverage_current(cov):raise ValidationError('Billing coverage is stale')
    if (v['partner'],v['customer'])!=(m['partner'],cov.customer):raise ValidationError('Activity partner/customer differs from explicit Finance meter mapping')
    if v['completeness']!='complete' and not m['allow_partial']:raise ValidationError('Finance meter requires complete source coverage')
    # Revalidate source identity and metrics under current configuration; receipt remains historical proof.
    report_current(receipt.report)
    selected=[e for e in v['events'] if e['product']==m['product'] and e['kind'] in m['event_kinds']]
    if not selected or any(e['quantity'] is None for e in selected):raise ValidationError('Exact supplied meter quantities required; activity counts are not billing quantities')
    e=subject(case,evidence_id,'partner_decision')
    from .models import PartnerMeterClaim
    from django.db import IntegrityError
    try:
        with transaction.atomic():
            for row in sorted(selected,key=lambda e:e['event']):PartnerMeterClaim.objects.create(identity=digest({'tenant':case.tenant,'source':v['source'],'partner':v['partner'],'event':row['event']}),receipt=receipt)
    except IntegrityError:raise ValidationError('Meter source events already handed to Finance; reconcile correction')
    import csv,io
    from apps.core.services import add_evidence
    out=io.StringIO();writer=csv.writer(out,lineterminator='\n');writer.writerow(['transaction_id','customer','service','contract','period','unit','quantity'])
    for row in selected:writer.writerow(['PE-'+digest({'source':v['source'],'partner':v['partner'],'event':row['event']}),cov.customer,cov.service,cov.contract,v['period'],m['unit'],row['quantity']])
    proof=add_evidence(actor,case.pk,'billing_usage',out.getvalue(),'partner-meter:'+str(receipt.pk),None)
    usage=billing.capture_usage(actor,case.pk,cov.pk,proof.pk,None,{'provider_ref':v['source'],'extracted_at':v['extracted_at'],'completeness':v['completeness']})
    if usage.findings:raise ValidationError(usage.findings)
    result=PartnerBillingImport.objects.create(receipt=receipt,usage=usage,policy={'meter':c.pk,'receipt_hash':receipt.sha256},evidence=e,actor=actor)
    event(actor,case,'partner.meter_imported',import_id=result.pk,usage=usage.pk,invoice_created=False);bump(case);return result

def meter_origin(usage):
    """Keep accepted source history while holding new Finance use of superseded meter evidence."""
    accepted=PartnerBillingImport.objects.filter(usage=usage).select_related('receipt__report__record').first()
    if not accepted:return None
    c,_=rule(usage.coverage.case,METER)
    if c.pk!=accepted.policy['meter']:raise ValidationError('Partner meter mapping changed; reconcile accepted usage before new financial use')
    report_current(accepted.receipt.report)
    return {'acceptance':accepted.pk,'receipt':accepted.receipt_id,'receipt_hash':accepted.receipt.sha256,'report_hash':accepted.receipt.report.sha256,'meter_policy':c.pk,'source_hash':accepted.receipt.report.record.evidence.sha256}
