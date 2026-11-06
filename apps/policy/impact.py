"""Human engineering reassessment; never activates policy or replays a business action."""
import hashlib,json
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,DatabaseError
from apps.core.models import Case,Evidence
from apps.core.services import event
from apps.identity.models import Grant
from apps.identity.services import require
from adapters import policy_impact as adapter
from .models import Configuration,ScopeApplication,ScopeVersion,ImpactAssessment,ImpactReview
from .scopes import authorized,application_health
from .services import resolve

FORMAT='psl.policy-impact/v1'
SNAPSHOT_LIMIT=100


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def context(actor,case_id):
    if not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():
        raise PermissionDenied('Current active principal required')
    if not Grant.objects.filter(user=actor,case_id=case_id,action='case.read',active=True).exists():
        raise PermissionDenied('Current case access required before record lookup')
    case=Case.objects.get(pk=case_id)
    authorized(actor,case,'policy.read')
    return case


def configuration(actor,case_id,pk):
    case=context(actor,case_id)
    config=Configuration.objects.select_related('case').get(case=case,pk=pk)
    application=ScopeApplication.objects.select_related('source__configuration__case').filter(configuration=config).first()
    if application:
        authorized(actor,application.source.configuration.case,'policy.read')
    return config


def selected(keys):
    if not isinstance(keys,list) or not keys or len(keys)>len(adapter.REGISTRY) or any(not isinstance(k,str) or k not in adapter.REGISTRY for k in keys) or len(set(keys))!=len(keys):
        raise ValidationError('Select distinct registered domain adapters')
    return sorted(keys)


def page(actor,case_id,configuration_id,key,cursor=None,limit=25):
    config=configuration(actor,case_id,configuration_id);adapter.authorize(actor,config.case,key)
    if type(limit) is not int or not 1<=limit<=50:
        raise ValidationError('Page size must be between 1 and 50')
    after=0
    if cursor:
        try:
            if not isinstance(cursor,str) or len(cursor)>4096:raise ValueError()
            token=signing.loads(cursor,salt=FORMAT,max_age=3600)
            if token[:4]!=[actor.pk,str(config.case_id),config.pk,key] or type(token[4]) is not int or token[4]<0:raise ValueError()
            after=token[4]
        except (signing.BadSignature,ValueError,TypeError,IndexError):
            raise ValidationError('Invalid or stale impact page link')
    rows=list(adapter.query(config,key).filter(pk__gt=after)[:limit+1])
    for row in rows:adapter.authorize_row(actor,config.case,key,row)
    more=len(rows)>limit;rows=rows[:limit]
    token=signing.dumps([actor.pk,str(config.case_id),config.pk,key,rows[-1].pk],salt=FORMAT) if more else None
    return {'records':[adapter.project(r,key) for r in rows],'next_cursor':token,'coverage':'live page of one declared adapter; not a complete dependency inventory',
        'adapter':key,'uncovered':adapter.UNCOVERED,'configuration':config.pk}


def observation(actor,previous,successor,keys,lock=False):
    keys=selected(keys)
    # Both selected source namespaces must still be readable, even if the old source is revoked.
    for cfg in [previous,successor]:configuration(actor,cfg.case_id,cfg.pk)
    current=resolve(previous.component,previous.case)
    value={'format':FORMAT,'previous':previous.pk,'successor':successor.pk,'component':previous.component,
        'previous_state':previous.states.order_by('-pk').first().state,
        'previous_origin':application_health(previous),'successor_state':successor.states.order_by('-pk').first().state,
        'effective_configuration':current.configuration.pk if current.configuration else None,'effective_status':current.status,
        'successor_origin':application_health(successor),'domains':{},'uncovered':adapter.UNCOVERED,
        'coverage':'complete only for selected declared adapters at the observed heads; other consumers remain unknown'}
    for key in keys:
        adapter.authorize(actor,previous.case,key)
        query=adapter.query(previous,key)
        # Effect rows are mutable independently of case services. NOWAIT avoids a case/job lock-order deadlock.
        try:
            with transaction.atomic():
                if lock and key in ['finance.invoice_effects','finance.correction_effects','baas.response_effects']:
                    query=query.select_for_update(of=('self',),nowait=True)
                rows=list(query[:SNAPSHOT_LIMIT+1])
        except DatabaseError:
            raise ValidationError('An effect is being reconciled; refresh the impact observation')
        for row in rows:
            adapter.authorize_row(actor,previous.case,key,row)
            if lock:adapter.lock_row(row,key)
        if len(rows)>SNAPSHOT_LIMIT:
            raise ValidationError('Impact snapshot exceeds the declared adapter budget; use paged investigation and narrower reassessment coverage')
        value['domains'][key]=[adapter.project(row,key) for row in rows]
    return value


def lock_context(previous,successor,users):
    source_cases=list(ScopeApplication.objects.filter(configuration__in=[previous,successor]).values_list('source__configuration__case_id',flat=True))
    from apps.finance.ledger import scope_lock
    scope_lock(previous.case_id,extra_case_ids=source_cases)
    list(get_user_model().objects.select_for_update().filter(pk__in=users).order_by('pk'))
    list(Grant.objects.select_for_update().filter(case_id__in=source_cases+[previous.case_id],user_id__in=users).order_by('pk'))


def explanation(value):
    if not isinstance(value,str) or not value.strip() or len(value)>2000:
        raise ValidationError('An explanation of at most 2000 characters is required')
    return value.strip()


def proof(case,pk):
    evidence=Evidence.objects.filter(case=case,pk=pk,kind='policy_decision').first()
    if not evidence:raise ValidationError('Use policy-decision evidence from this exact case')
    return evidence


@transaction.atomic
def capture(actor,case_id,previous_id,successor_id,keys,evidence_id,reason):
    previous=configuration(actor,case_id,previous_id);successor=configuration(actor,case_id,successor_id)
    lock_context(previous,successor,[actor.pk]);require(actor,previous.case,'policy.configure')
    if previous.component!=successor.component or successor.revision<=previous.revision:
        raise ValidationError('Select a later local configuration of the same component and case')
    if ScopeVersion.objects.filter(configuration__in=[previous,successor]).exists():
        raise ValidationError('Select executable local configurations; apply scoped sources first')
    evidence=proof(previous.case,evidence_id);reason=explanation(reason);keys=selected(keys)
    snapshot=observation(actor,previous,successor,keys,lock=True)
    if snapshot['effective_configuration']!=successor.pk or snapshot['effective_status']!='ACTIVE':
        raise ValidationError('Select the currently ACTIVE reviewed local successor before reassessment')
    sha=digest(snapshot);key=digest([FORMAT,actor.pk,previous.pk,successor.pk,sha,evidence.pk,reason])
    existing=ImpactAssessment.objects.filter(operation_key=key).first()
    if existing:return existing
    row=ImpactAssessment.objects.create(previous=previous,successor=successor,adapters=keys,observation=snapshot,
        sha256=sha,evidence=evidence,reason=reason,operation_key=key,actor=actor)
    event(actor,previous.case,'policy.impact.captured',assessment=row.pk,previous=previous.pk,successor=successor.pk)
    return row


@transaction.atomic
def review(actor,case_id,assessment_id,verdict,evidence_id,reason):
    context(actor,case_id)
    row=ImpactAssessment.objects.select_related('previous__case','successor__case','actor').get(pk=assessment_id,previous__case_id=case_id)
    lock_context(row.previous,row.successor,[actor.pk,row.actor_id])
    # Serializes duplicate reviews without mutating the captured observation.
    row=ImpactAssessment.objects.select_for_update().get(pk=row.pk)
    authorized(actor,row.previous.case,'policy.activate')
    if actor.pk==row.actor_id:raise PermissionDenied('A second authorized human must review this engineering reassessment')
    if verdict not in ['accept','reject','defer']:raise ValidationError('Unsupported reassessment disposition')
    if ImpactReview.objects.filter(assessment=row).exists():raise ValidationError('Review already recorded; capture a successor assessment')
    evidence=proof(row.previous.case,evidence_id);reason=explanation(reason)
    fresh=observation(actor,row.previous,row.successor,row.adapters,lock=True)
    if verdict=='accept':
        row.actor.refresh_from_db()
        authorized(row.actor,row.previous.case,'policy.configure')
        observation(row.actor,row.previous,row.successor,row.adapters,lock=True)
        if digest(row.observation)!=row.sha256 or digest(fresh)!=row.sha256 or fresh['effective_configuration']!=row.successor_id or fresh['effective_status']!='ACTIVE':
            raise ValidationError('Policy, authority or domain heads changed; capture and review a new assessment')
    result=ImpactReview.objects.create(assessment=row,verdict=verdict,observed_sha256=digest(fresh),evidence=evidence,reason=reason,actor=actor)
    event(actor,row.previous.case,'policy.impact.reviewed',assessment=row.pk,review=result.pk,verdict=verdict)
    return result


def inspect(actor,case_id,assessment_id):
    context(actor,case_id)
    row=ImpactAssessment.objects.select_related('previous__case','successor__case').get(pk=assessment_id,previous__case_id=case_id)
    fresh=observation(actor,row.previous,row.successor,row.adapters)
    decision=ImpactReview.objects.filter(assessment=row).first()
    review_authority_current=None
    if decision:
        try:
            authorized(decision.actor,row.previous.case,'policy.activate')
            observation(decision.actor,row.previous,row.successor,row.adapters)
            review_authority_current=True
        except PermissionDenied:
            review_authority_current=False
    return {'assessment':row.pk,'previous':row.previous_id,'successor':row.successor_id,'domains':fresh['domains'],
        'current':digest(fresh)==row.sha256 and digest(row.observation)==row.sha256,
        'verdict':decision.verdict if decision else 'unreviewed','review':decision.pk if decision else None,'review_authority_current':review_authority_current,
        'effect_tools':[],'business_approval':False,'coverage':fresh['coverage'],'uncovered':adapter.UNCOVERED}
