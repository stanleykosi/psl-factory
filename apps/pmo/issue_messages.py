"""Scoped drafts and human message release never stand in for an owner reply."""
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Func, IntegerField
from django.utils import timezone

from adapters.issue_messages import SyntheticIssueMailbox, receipt_facts, verify_evidence, expected_receipt
from apps.agents.models import AgentRun
from apps.core.services import bump, event, lock_case, add_evidence
from apps.core.models import Evidence
from apps.documents.contracts import digest
from apps.identity.services import require
from apps.policy.issue_message_validators import COMPONENT, validate_reference
from apps.policy.services import active_component, reference_values, role_policy, decision_authority

from . import issue_teams
from .issue_access import issue_subject, state_public
from .issue_models import Issue
from .issue_message_models import (IssueMessageDraft, IssueMessageReview, IssueMessageDispatch,
    IssueMessageAttempt, IssueMessageReceipt, IssueMessageCancellation, IssueMessageCursor)


def rules(case):
    from apps.policy.models import RegisteredReference
    config=active_component(COMPONENT,case)
    artifact=config.envelope['value']
    reference=RegisteredReference.objects.get(case=config.case,ref=artifact['artifact_ref'],
                                             version=artifact['artifact_version'])
    value=validate_reference(reference,case)
    if reference.sha256!=artifact['sha256'] or reference.content!=reference_values(config)[0]:
        raise ValidationError('Review the exact owner-message controls.')
    return config,value


def positive(*values):
    if any(type(value) is not int or value<1 for value in values):
        raise ValidationError('Use exact current issue, message and revision references.')


def key(value):
    try:
        return UUID(str(value))
    except (ValueError,TypeError,AttributeError):
        raise ValidationError('Reload the current message form before continuing.') from None


def note(value,limit=2000):
    if not isinstance(value,str) or not value.strip() or len(value)>limit:
        raise ValidationError('Provide a clear note within the displayed limit.')
    return value.strip()


def proof(case,evidence_id):
    positive(evidence_id)
    source=issue_subject(case,evidence_id,metadata_only=True)
    require(source.created_by,case,'case.read')
    require(source.created_by,case,'evidence.add')
    return source


def receipt_proof(actor,case,evidence_id):
    positive(evidence_id)
    require(actor,case,'case.read')
    require(actor,case,'issue.read')
    require(actor,case,'issue.message.read')
    evidence=Evidence.objects.filter(case=case,pk=evidence_id,kind='issue_message_receipt').alias(
        receipt_bytes=Func(F('body'),function='OCTET_LENGTH',output_field=IntegerField())).filter(
            receipt_bytes__lte=32000).defer('body').select_related('created_by').first()
    if evidence is None:
        raise ValidationError('Choose exact message-receipt evidence within thirty-two thousand bytes.')
    require(evidence.created_by,case,'case.read')
    require(evidence.created_by,case,'evidence.add')
    return evidence


def source(actor,case,issue_id,*,open_only=True):
    positive(issue_id)
    require(actor,case,'case.read')
    require(actor,case,'issue.read')
    require(actor,case,'issue.message.read')
    issue=Issue.objects.select_related('case','current__owner').filter(case=case,pk=issue_id).first()
    if issue is None or not state_public(issue.current):
        raise ValidationError('Use this project current readable issue.')
    if open_only and issue.current.status not in {'Open','In Progress'}:
        raise ValidationError('Resolved or closed issues do not need new owner messages.')
    assignment=issue_teams.latest(issue)
    if assignment is None or assignment.mode!='team':
        raise ValidationError('Use the factory owner task for a person with an account.')
    issue_teams.current(assignment,issue)
    issue.current.evidence=proof(case,issue.current.evidence_id)
    return issue,assignment


def facts(issue,assignment):
    state=issue.current
    return {'protocol':'issue-owner-message-source/v1','issue_id':issue.pk,'state_id':state.pk,
        'assignment_id':assignment.pk,'team_key':assignment.team_key,'team_label':assignment.team_label,
        'recorder_id':assignment.recorder_id,'team_rules':assignment.policy_id,
        'recorder_authority':assignment.authority,'evidence_id':state.evidence_id,
        'evidence_sha256':state.evidence.sha256,'reference':issue.reference,'title':state.title,
        'status':state.status,'next_action':state.next_action,
        'acknowledged_at':state.acknowledged_at.isoformat() if state.acknowledged_at else None}


def latest(issue):
    return issue.message_drafts.defer('body','source').order_by('-number').first()


def maybe_prepare(actor,case_id,issue_id,work_id,head_id):
    from uuid import uuid5, NAMESPACE_URL
    from apps.core.models import Case
    case=Case.objects.get(pk=case_id)
    issue=Issue.objects.get(case=case,pk=issue_id)
    assignment=issue_teams.latest(issue)
    if assignment is None or assignment.mode!='team':return None
    if rules(case)[1]['draft_on_owner_wait'] is not True:return None
    issue,assignment=source(actor,case,issue_id)
    existing=latest(issue)
    if existing and existing.state_id==issue.current_id and existing.assignment_id==assignment.pk:
        readable(actor,existing)
        return existing
    receipt=delivered(issue)
    kind='reminder' if receipt and receipt.dispatch.review.draft.state_id==issue.current_id and receipt.dispatch.review.draft.assignment_id==assignment.pk else 'request'
    return prepare(actor,case.pk,issue.pk,issue.current_id,kind,
        uuid5(NAMESPACE_URL,f'psl:issue-owner-message:{work_id}:{head_id}:{assignment.pk}'),case.revision)


def readable(actor,draft):
    case=draft.issue.case
    for action in ['case.read','issue.read','issue.message.read']:require(actor,case,action)
    if not state_public(draft.state):
        raise PermissionDenied('Use the source-authorised private interface for this historical message.')
    proof(case,draft.state.evidence_id)
    proof(case,draft.evidence_id)
    for action in ['case.read','issue.read','issue.message.read']:require(draft.actor,case,action)
    return draft


def review_readable(actor,entry):
    readable(actor,entry.draft)
    case=entry.draft.issue.case
    proof(case,entry.evidence_id)
    for action in ['case.read','issue.read','issue.message.read']:require(entry.actor,case,action)
    return entry


def delivered(issue):
    return IssueMessageReceipt.objects.filter(dispatch__review__draft__issue=issue,
        delivered=True).select_related('dispatch__review__draft').defer('reference','dispatch__payload',
            'dispatch__route','dispatch__review__note','dispatch__review__draft__body',
            'dispatch__review__draft__source').order_by('-pk').first()


def role_authority(actor,case,role,value,kind):
    if role not in value[kind+'_roles']:
        raise PermissionDenied('Use a currently configured owner-message '+kind+' role.')
    assignment=role_policy(actor,case,role)
    return {assignment.component:assignment.pk}


def check_draft(actor,draft,*,current=True):
    issue,assignment=source(actor,draft.issue.case,draft.issue_id)
    require(draft.actor,issue.case,'issue.message.prepare')
    require(draft.actor,issue.case,'case.read')
    require(draft.actor,issue.case,'issue.read')
    require(draft.actor,issue.case,'issue.message.read')
    proof(issue.case,draft.evidence_id)
    if (draft.state_id!=issue.current_id or draft.assignment_id!=assignment.pk or
            facts(issue,assignment)!=draft.source or digest({'source':draft.source,'body':draft.body})!=draft.sha256):
        raise ValidationError('The issue or owner changed. Prepare a fresh message from current facts.')
    if current and latest(issue).pk!=draft.pk:
        raise ValidationError('Review the latest message wording.')
    if draft.kind=='reminder':
        receipt=delivered(issue)
        if (receipt is None or receipt.dispatch_id!=draft.previous_release_id or
                receipt.dispatch.review.draft.state_id!=draft.state_id or
                receipt.dispatch.review.draft.assignment_id!=draft.assignment_id):
            raise ValidationError('Review the current original owner request receipt before reminding.')
        receipt_current(actor,receipt)
    return issue,assignment


@transaction.atomic
def prepare(actor,case_id,issue_id,state_id,kind,operation_key,expected,*,previous_id=None,
            body=None,evidence_id=None,reason=None):
    positive(issue_id,state_id,expected)
    if previous_id is not None:positive(previous_id)
    operation=key(operation_key)
    intent=digest({'actor':actor.pk,'issue':issue_id,'state':state_id,'kind':kind,
        'previous':previous_id,'body':body,'evidence':evidence_id,'reason':reason})
    case=lock_case(actor,case_id,'issue.message.prepare')
    issue,assignment=source(actor,case,issue_id)
    if issue.current_id!=state_id or not isinstance(kind,str) or kind not in {'request','reminder'}:
        raise ValidationError('Choose the current issue and owner-message step.')
    old=IssueMessageDraft.objects.filter(operation_key=operation).first()
    if old:
        if old.issue_id!=issue.pk or old.intent_sha256!=intent or old.source!=facts(issue,assignment):
            raise ValidationError('This message request key identifies different source facts.')
        return old
    if case.revision!=expected:
        raise ValidationError('The issue workspace changed. Reload before preparing this message.')
    previous=latest(issue)
    receipt=delivered(issue)
    preceding=None
    if previous_id is not None:
        if previous is None or previous.pk!=previous_id:
            raise ValidationError('The message changed. Reload before editing it.')
        check_draft(actor,previous)
        if IssueMessageDispatch.objects.filter(review__draft=previous).exists():
            raise ValidationError('Check or cancel the original release before changing its message.')
        if kind!=previous.kind:
            raise ValidationError('An edit preserves the current message purpose.')
        body=note(body,4000)
        rationale=note(reason)
        evidence=proof(case,evidence_id)
        preceding=previous.previous_release
    else:
        if any(value is not None for value in [body,evidence_id,reason]):
            raise ValidationError('Prepare the source-bound suggestion before editing its wording.')
        if kind=='reminder':
            if (receipt is None or receipt.dispatch.review.draft.state_id!=state_id or
                    receipt.dispatch.review.draft.assignment_id!=assignment.pk):
                raise ValidationError('A reminder needs this current issue owner request and its verified delivery.')
            receipt_current(actor,receipt)
            preceding=receipt.dispatch
        elif receipt and receipt.dispatch.review.draft.state_id==state_id and receipt.dispatch.review.draft.assignment_id==assignment.pk:
            raise ValidationError('This owner request was delivered. Use its reviewed reminder step.')
        question='Please provide a current update on' if issue.current.acknowledged_at else 'Please acknowledge responsibility for'
        body=f'{question} {issue.reference}: {issue.current.title}.\nCurrent next action: {issue.current.next_action}\nPlease reply with progress and supporting evidence.'
        if kind=='reminder':
            body='Following up on our recorded owner request '+receipt.reference+'.\n'+body
        rationale='Prepared from the current issue and external owner; no message is sent.'
        evidence=proof(case,issue.current.evidence_id)
    snapshot=facts(issue,assignment)
    fingerprint=digest({'source':snapshot,'body':body})
    run=None
    if previous_id is None:
        run=AgentRun.objects.create(case=case,actor=actor,evidence=evidence,
            provider='deterministic-issue-message-v1',process_id='P50',result={
                'capability':'Scoped owner-message preparation','source':snapshot,'draft':body,
                'approval_granted':False,'communications_dispatched':False})
    draft=IssueMessageDraft.objects.create(issue=issue,state=issue.current,assignment=assignment,
        number=previous.number+1 if previous else 1,previous=previous,previous_release=preceding,
        operation_key=operation,intent_sha256=intent,kind=kind,body=body,source=snapshot,sha256=fingerprint,evidence=evidence,
        reason=rationale,run=run,actor=actor)
    event(actor,case,'issue.message.drafted',draft=draft.pk,issue=issue.pk)
    bump(case)
    return draft


@transaction.atomic
def review(actor,case_id,draft_id,role,verdict,evidence_id,rationale,expected):
    positive(draft_id,expected)
    case=lock_case(actor,case_id,'issue.message.review')
    draft=IssueMessageDraft.objects.select_related('issue__case').defer('body','source').filter(pk=draft_id,issue__case=case).first()
    if draft is None:raise ValidationError('Choose this project current owner message.')
    check_draft(actor,draft)
    config,value=rules(case)
    role_authority(actor,case,role,value,'reviewer')
    if not isinstance(verdict,str) or verdict not in {'approve','return','reject'}:
        raise ValidationError('Approve, return or reject this exact wording.')
    authority=decision_authority(actor,case,role,verdict)
    evidence=proof(case,evidence_id)
    rationale=note(rationale)
    old=IssueMessageReview.objects.filter(draft=draft).first()
    if old:
        if (old.actor_id,old.role,old.verdict,old.evidence_id,old.note,old.authority,old.configuration_id)!=(
                actor.pk,role,verdict,evidence.pk,rationale,authority,config.pk):
            raise ValidationError('This wording was reviewed. Save a fresh revision before another review.')
        return old
    if case.revision!=expected:
        raise ValidationError('The issue workspace changed. Reload before reviewing this message.')
    result=IssueMessageReview.objects.create(draft=draft,configuration=config,role=role,verdict=verdict,
        authority=authority,evidence=evidence,note=rationale,actor=actor)
    event(actor,case,'issue.message.reviewed',review=result.pk,verdict=verdict)
    bump(case)
    return result


def current_review(actor,case,review_id):
    positive(review_id)
    entry=IssueMessageReview.objects.select_related('draft__issue__case','actor').defer('note','draft__body','draft__source').filter(
        pk=review_id,draft__issue__case=case).first()
    if entry is None or entry.verdict!='approve':
        raise ValidationError('Release a current human-approved owner message.')
    require(entry.actor,case,'issue.message.review')
    require(entry.actor,case,'case.read')
    require(entry.actor,case,'issue.read')
    require(entry.actor,case,'issue.message.read')
    config,value=rules(case)
    role_authority(entry.actor,case,entry.role,value,'reviewer')
    if entry.configuration_id!=config.pk or entry.authority!=decision_authority(entry.actor,case,entry.role,'approve'):
        raise ValidationError('The message review authority changed. Obtain a fresh review.')
    proof(case,entry.evidence_id)
    check_draft(actor,entry.draft)
    return entry,config,value


def clock_at(receipt,value):
    basis=value['clock_basis']
    if basis=='recorded_receipt_time':return receipt.created_at
    if basis=='source_delivery_time' and receipt.delivered_at:return receipt.delivered_at
    if basis=='source_delivery_time':
        raise ValidationError('The channel evidence does not establish the actual delivery time.')
    raise ValidationError('Choose the owner-message timing basis before scheduling a reminder.')


def after(start,hours):
    try:
        return start+timedelta(seconds=float(Decimal(str(hours))*3600))
    except (OverflowError,ValueError):
        raise ValidationError('The configured interval exceeds the supported date range.') from None


@transaction.atomic
def release(actor,case_id,review_id,role,channel,expected,*,not_before=None):
    positive(review_id,expected)
    if not_before is not None and (not isinstance(not_before,datetime) or timezone.is_naive(not_before)):
        raise ValidationError('Choose a scheduled time with its time zone.')
    intent=digest({'actor':actor.pk,'review':review_id,'role':role,'channel':channel,
                   'not_before':not_before.isoformat() if not_before else None})
    case=lock_case(actor,case_id,'issue.message.release')
    entry,config,value=current_review(actor,case,review_id)
    authority=role_authority(actor,case,role,value,'sender')
    if value['independent_release'] is None:
        raise ValidationError('Choose whether message review and release need different people.')
    if value['independent_release'] and entry.actor_id==actor.pk:
        raise PermissionDenied('A different configured person releases this reviewed message.')
    routes=[r for r in value['routes'] if r['team_key']==entry.draft.assignment.team_key and r['channel']==channel]
    if len(routes)!=1:raise ValidationError('Choose one configured current team delivery route.')
    route=routes[0]
    old=IssueMessageDispatch.objects.filter(review=entry).first()
    if old:
        if old.actor_id!=actor.pk or old.intent_sha256!=intent or old.route!=route:
            raise ValidationError('This review has a different original release. Inspect its receipt.')
        return old
    if case.revision!=expected:
        raise ValidationError('The issue workspace changed. Reload before releasing this message.')
    if IssueMessageDispatch.objects.filter(review__draft__issue=entry.draft.issue,
            receipt__isnull=True,cancellation__isnull=True).exists():
        raise ValidationError('Check or cancel the original owner message before releasing another.')
    now=timezone.now()
    due=now
    if entry.draft.kind=='reminder':
        if value['reminder_after_hours'] is None:
            raise ValidationError('Choose the reminder interval before scheduling it.')
        receipt=IssueMessageReceipt.objects.get(dispatch=entry.draft.previous_release,delivered=True)
        due=after(clock_at(receipt,value),value['reminder_after_hours'])
    if not_before is not None:
        if timezone.is_naive(not_before) or not_before<now:
            raise ValidationError('Choose a future scheduled time with its time zone.')
        due=max(due,not_before)
    payload={'issue_reference':entry.draft.issue.reference,'recipient':route['destination'],
             'channel':channel,'body':entry.draft.body}
    result=IssueMessageDispatch.objects.create(review=entry,configuration=config,role=role,
        intent_sha256=intent,authority=authority,route=route,payload=payload,sha256=digest(payload),
        not_before=max(now,due),actor=actor)
    event(actor,case,'issue.message.released',dispatch=result.pk,scheduled_for=result.not_before.isoformat())
    bump(case)
    return result


def check_release(dispatch):
    case=dispatch.review.draft.issue.case
    require(dispatch.actor,case,'issue.message.release')
    entry,config,value=current_review(dispatch.actor,case,dispatch.review_id)
    if value['independent_release'] is None or value['independent_release'] and entry.actor_id==dispatch.actor_id:
        raise ValidationError('Review the current independent message-release choice.')
    routes=[r for r in value['routes'] if r['team_key']==entry.draft.assignment.team_key and r['channel']==dispatch.route['channel']]
    if (config.pk!=dispatch.configuration_id or routes!=[dispatch.route] or
            role_authority(dispatch.actor,case,dispatch.role,value,'sender')!=dispatch.authority or
            digest(dispatch.payload)!=dispatch.sha256 or dispatch.payload!=dict(
                issue_reference=entry.draft.issue.reference,recipient=dispatch.route['destination'],
                channel=dispatch.route['channel'],body=entry.draft.body)):
        raise ValidationError('The reviewed message, destination or release authority changed.')
    return case


def original(actor,case,dispatch_id):
    positive(dispatch_id)
    require(actor,case,'case.read')
    require(actor,case,'issue.read')
    require(actor,case,'issue.message.read')
    dispatch=IssueMessageDispatch.objects.select_related('review__draft__issue__case','review__draft__state',
        'review__draft__assignment','actor').defer('payload','route','review__note',
            'review__draft__body','review__draft__source').filter(pk=dispatch_id,review__draft__issue__case=case).first()
    if dispatch is None or not state_public(dispatch.review.draft.state):
        raise ValidationError('Use this project readable original owner message.')
    proof(case,dispatch.review.draft.evidence_id)
    return dispatch


@transaction.atomic
def begin_manual(actor,case_id,dispatch_id,expected):
    positive(dispatch_id,expected)
    case=lock_case(actor,case_id,'issue.message.release')
    dispatch=original(actor,case,dispatch_id)
    if dispatch.actor_id!=actor.pk or dispatch.route['mode']!='manual_evidence':
        raise PermissionDenied('The original sender starts this reviewed manual message.')
    if IssueMessageCancellation.objects.filter(dispatch=dispatch).exists():
        raise ValidationError('This unsent release was cancelled.')
    check_release(dispatch)
    old=IssueMessageAttempt.objects.filter(dispatch=dispatch).first()
    if old:return old
    if case.revision!=expected or dispatch.not_before>timezone.now():
        raise ValidationError('Reload the current release and wait until its scheduled time.')
    attempt=IssueMessageAttempt.objects.create(dispatch=dispatch)
    event(actor,case,'issue.message.manual_started',dispatch=dispatch.pk,role=dispatch.role,
          authority=dispatch.authority,configuration=dispatch.configuration_id)
    bump(case)
    return attempt


@transaction.atomic
def cancel(actor,case_id,dispatch_id,role,rationale,expected):
    positive(dispatch_id,expected)
    case=lock_case(actor,case_id,'issue.message.release')
    dispatch=original(actor,case,dispatch_id)
    config,value=rules(case)
    authority=role_authority(actor,case,role,value,'sender')
    rationale=note(rationale)
    old=IssueMessageCancellation.objects.filter(dispatch=dispatch).first()
    if old:
        if old.actor_id!=actor.pk or old.reason!=rationale:
            raise ValidationError('This release has a different recorded cancellation.')
        return old
    if case.revision!=expected:
        raise ValidationError('The workspace changed. Reload before cancelling the unsent release.')
    if IssueMessageAttempt.objects.filter(dispatch=dispatch).exists() or IssueMessageReceipt.objects.filter(dispatch=dispatch).exists():
        raise ValidationError('Sending may have started. Check the original receipt instead of cancelling.')
    result=IssueMessageCancellation.objects.create(dispatch=dispatch,reason=rationale,actor=actor)
    event(actor,case,'issue.message.unsent_cancelled',dispatch=dispatch.pk,cancellation=result.pk,
          role=role,authority=authority,configuration=config.pk)
    bump(case)
    return result


def _record(dispatch,actor,observed,clock_source,evidence=None,source_evidence=None):
    if not isinstance(observed,dict) or set(observed)!={'reference','delivered','delivered_at'}:
        raise ValidationError('Use the complete original message delivery result.')
    observed=receipt_facts(**observed)
    attempt=IssueMessageAttempt.objects.filter(dispatch=dispatch).first()
    if attempt is None or observed['delivered_at'] and observed['delivered_at']<attempt.created_at:
        raise ValidationError('The source delivery precedes the recorded controlled send. Review the original authority or clock.')
    old=IssueMessageReceipt.objects.filter(dispatch=dispatch).first()
    if old:
        if (old.reference,old.delivered,old.delivered_at,old.clock_source,old.evidence_id,old.source_evidence_id)!=(
                observed['reference'],observed['delivered'],observed['delivered_at'],clock_source,
                evidence.pk if evidence else None,source_evidence.pk if source_evidence else None):
            raise ValidationError('The original message already has a different delivery result.')
        return old
    result=IssueMessageReceipt.objects.create(dispatch=dispatch,actor=actor,evidence=evidence,
        source_evidence=source_evidence,source_sha256=source_evidence.sha256 if source_evidence else '',
        clock_source=clock_source,**observed)
    case=dispatch.review.draft.issue.case
    event(actor,case,'issue.message.receipt_observed',dispatch=dispatch.pk,receipt=result.pk,
          delivered=result.delivered,observation_kind=clock_source)
    return result


@transaction.atomic
def confirm(actor,case_id,dispatch_id,role,evidence_id,reference,was_delivered,delivered_at,expected):
    positive(dispatch_id,expected)
    case=lock_case(actor,case_id,'issue.message.recover')
    dispatch=original(actor,case,dispatch_id)
    config,value=rules(case)
    authority=role_authority(actor,case,role,value,'sender')
    if dispatch.route['mode']!='manual_evidence' or not IssueMessageAttempt.objects.filter(dispatch=dispatch).exists():
        raise ValidationError('Choose an original manual send that was started and still needs its receipt.')
    evidence=receipt_proof(actor,case,evidence_id)
    observed=receipt_facts(reference,was_delivered,delivered_at)
    context=verify_evidence(dispatch,evidence,reference,was_delivered,delivered_at)
    origin=None
    if context:
        origin=proof(case,context['evidence_id'])
        if origin.sha256!=context['sha256'] or origin.kind not in {'document','support_message','project_artifact','issue_delivery_source'}:
            raise ValidationError('Review the exact original supporting delivery evidence.')
    old=IssueMessageReceipt.objects.filter(dispatch=dispatch).first()
    if not old and case.revision!=expected:
        raise ValidationError('The workspace changed. Reload before recording the receipt.')
    result=_record(dispatch,actor,observed,'human_attested',evidence,origin)
    if old is None:
        event(actor,case,'issue.message.manual_receipt_confirmed',receipt=result.pk,role=role,
              authority=authority,configuration=config.pk)
        bump(case)
    return result


@transaction.atomic
def attest(actor,case_id,dispatch_id,role,source_id,reference,was_delivered,delivered_at,checked,expected):
    positive(dispatch_id,source_id,expected)
    if checked is not True:
        raise ValidationError('Confirm that you checked the source against this exact message and recipient.')
    case=lock_case(actor,case_id,'issue.message.recover',expected)
    dispatch=original(actor,case,dispatch_id)
    role_authority(actor,case,role,rules(case)[1],'sender')
    if dispatch.route['mode']!='manual_evidence' or not IssueMessageAttempt.objects.filter(dispatch=dispatch).exists():
        raise ValidationError('Record the receipt for an original started manual send.')
    if IssueMessageReceipt.objects.filter(dispatch=dispatch).exists():
        raise ValidationError('This message has a recorded receipt. Inspect its original evidence.')
    origin=proof(case,source_id)
    if origin.kind not in {'document','support_message','project_artifact','issue_delivery_source'}:
        raise ValidationError('Choose the original channel evidence, separate from a generated receipt.')
    payload={'protocol':'issue-owner-message-receipt-attestation/v2',
        'result':expected_receipt(dispatch,reference,was_delivered,delivered_at),
        'source':{'evidence_id':origin.pk,'sha256':origin.sha256}}
    wrapper=add_evidence(actor,case.pk,'issue_message_receipt',json.dumps(payload,sort_keys=True),
                         'psl:human-owner-message-attestation')
    case.refresh_from_db()
    result=confirm(actor,case.pk,dispatch.pk,role,wrapper.pk,reference,was_delivered,delivered_at,case.revision)
    event(actor,case,'issue.message.receipt_attested',receipt=result.pk,source=origin.pk,
          source_sha256=origin.sha256,provider_authenticity_verified=False)
    return result


def receipt_current(actor,receipt):
    case=receipt.dispatch.review.draft.issue.case
    original(actor,case,receipt.dispatch_id)
    if receipt.source_evidence_id:
        origin=proof(case,receipt.source_evidence_id)
        if origin.sha256!=receipt.source_sha256:
            raise ValidationError('Review the original channel evidence.')
    if receipt.evidence_id:
        evidence=receipt_proof(actor,case,receipt.evidence_id)
        context=verify_evidence(receipt.dispatch,evidence,receipt.reference,receipt.delivered,receipt.delivered_at)
        expected={'evidence_id':receipt.source_evidence_id,'sha256':receipt.source_sha256} if receipt.source_evidence_id else None
        if context!=expected:raise ValidationError('The receipt supporting-source binding changed.')
    return receipt


def run_once(dispatch_id=None,adapter=None,*,lookup_only=False,reconcile_absence=False):
    if dispatch_id is not None:positive(dispatch_id)
    if type(lookup_only) is not bool:raise ValidationError('Choose an explicit original-receipt lookup mode.')
    if type(reconcile_absence) is not bool or reconcile_absence and not lookup_only:
        raise ValidationError('A provider absence fence is an explicit original-operation recovery.')
    adapter=adapter or SyntheticIssueMailbox()
    ready=IssueMessageDispatch.objects.filter(route__mode='synthetic_mailbox',receipt__isnull=True,
        cancellation__isnull=True,not_before__lte=timezone.now()).select_related(
            'review__draft__issue__case','review__draft__assignment','actor').defer('payload','route',
                'review__note','review__draft__body','review__draft__source')
    candidate=ready.filter(pk=dispatch_id).first() if dispatch_id is not None else ready.order_by('pk').first()
    if candidate is None:return False
    with transaction.atomic():
        case=candidate.review.draft.issue.case
        case=type(case).objects.select_for_update().get(pk=case.pk)
        dispatch=ready.select_for_update(of=('self',),skip_locked=True).select_related(
            'review__draft__issue__case','review__draft__assignment','actor').filter(pk=candidate.pk).first()
        if dispatch is None:return False
        first=not IssueMessageAttempt.objects.filter(dispatch=dispatch).exists()
        if first:
            if lookup_only:return False
            try:
                check_release(dispatch)
            except (PermissionDenied,ValidationError):
                return False
            IssueMessageAttempt.objects.create(dispatch=dispatch)
    try:
        observed=adapter.reconcile(dispatch) if reconcile_absence else adapter.lookup(dispatch)
        if observed is None and first:
            observed=adapter.deliver(dispatch)
        if observed is not None:
            with transaction.atomic():
                case=type(case).objects.select_for_update().get(pk=case.pk)
                IssueMessageDispatch.objects.select_for_update().get(pk=dispatch.pk)
                before=IssueMessageReceipt.objects.filter(dispatch=dispatch).exists()
                _record(dispatch,dispatch.actor,observed,'synthetic_mailbox')
                if not before:bump(case)
    except (ConnectionError,TimeoutError,OSError,ValidationError):
        # The immutable attempt survives. Further runs only inspect this original
        # operation, even if the provider response was lost after actual delivery.
        pass
    return True


def recover(actor,case_id,dispatch_id,role,expected):
    positive(dispatch_id,expected)
    with transaction.atomic():
        case=lock_case(actor,case_id,'issue.message.recover')
        dispatch=original(actor,case,dispatch_id)
        config,value=rules(case)
        authority=role_authority(actor,case,role,value,'sender')
        receipt=IssueMessageReceipt.objects.filter(dispatch=dispatch).first()
        if receipt:return receipt_current(actor,receipt)
        if case.revision!=expected:
            raise ValidationError('The workspace changed. Reload the original delivery before checking it.')
        if not IssueMessageAttempt.objects.filter(dispatch=dispatch).exists():
            raise ValidationError('Sending has not started. Review or cancel this unsent release.')
        event(actor,case,'issue.message.receipt_check_requested',dispatch=dispatch.pk,role=role,
              authority=authority,configuration=config.pk)
        bump(case)
    if dispatch.route['mode']=='synthetic_mailbox':
        run_once(dispatch.pk,lookup_only=True,reconcile_absence=True)
    return IssueMessageReceipt.objects.filter(dispatch=dispatch).first()


@transaction.atomic
def next_batch(limit=20):
    if type(limit) is not int or not 1<=limit<=100:
        raise ValidationError('Choose a message batch between one and one hundred.')
    cursor,_=IssueMessageCursor.objects.get_or_create(name='owner-messages-v1')
    cursor=IssueMessageCursor.objects.select_for_update().get(pk=cursor.pk)
    ready=IssueMessageDispatch.objects.filter(route__mode='synthetic_mailbox',receipt__isnull=True,
        cancellation__isnull=True,not_before__lte=timezone.now()).order_by('pk')
    ids=list(ready.filter(pk__gt=cursor.last_dispatch_id).values_list('pk',flat=True)[:limit])
    if not ids:ids=list(ready.values_list('pk',flat=True)[:limit])
    cursor.last_dispatch_id=ids[-1] if ids else 0
    cursor.save(update_fields=['last_dispatch_id'])
    return ids


def status(dispatch,actor=None):
    receipt=IssueMessageReceipt.objects.filter(dispatch=dispatch).first()
    if receipt:
        if actor is not None:
            try:receipt_current(actor,receipt)
            except (PermissionDenied,ValidationError):
                return 'Evidence needs access',None,'Review current access to the original delivery evidence.'
        return ('Delivered' if receipt.delivered else 'Not delivered'),receipt,''
    if IssueMessageCancellation.objects.filter(dispatch=dispatch).exists():return 'Cancelled',None,''
    if IssueMessageAttempt.objects.filter(dispatch=dispatch).exists():
        return 'Receipt needed',None,'Inspect the original operation before releasing another message.'
    try:check_release(dispatch)
    except (PermissionDenied,ValidationError):
        return 'Needs review',None,'The source or release authority changed. Review or cancel this unsent release.'
    if dispatch.not_before>timezone.now():return 'Scheduled',None,''
    return ('Ready for manual sending' if dispatch.route['mode']=='manual_evidence' else 'Queued'),None,''


def chronology(actor,case,issue_id):
    issue,assignment=source(actor,case,issue_id,open_only=False)
    current=delivered(issue)
    result={'last_delivery':current,'reminder_due_at':None,'escalation_due_at':None,
            'escalation_target':None,'finding':'','reminder_hold':'Awaiting timing decision',
            'escalation_hold':'Awaiting timing decision'}
    if current is None:return result
    if current.dispatch.review.draft.state_id!=issue.current_id or current.dispatch.review.draft.assignment_id!=assignment.pk:
        result['finding']='The source changed after the last message. Review the current owner task.'
        return result
    try:receipt_current(actor,current)
    except (PermissionDenied,ValidationError):
        result.update(last_delivery=None,finding='Review current access to the original delivery evidence.')
        return result
    try:config,value=rules(case)
    except (PermissionDenied,ValidationError):
        result['finding']='Review owner-message timing rules before relying on a follow-up deadline.'
        return result
    result['escalation_target']=value['escalation_target']
    findings=[]
    if value['reminder_after_hours'] is not None and value['clock_basis'] is not None:
        try:result['reminder_due_at']=after(clock_at(current,value),value['reminder_after_hours'])
        except ValidationError:
            result['reminder_hold']='Delivery time needed'
            findings.append('The channel evidence does not establish the actual delivery time.')
    else:findings.append('Some follow-up timing choices await an owner decision.')
    # Escalation stays anchored to the first request. A later reminder with an
    # unknown clock must not hide a deadline established by that first receipt.
    first=IssueMessageReceipt.objects.filter(dispatch__review__draft__issue=issue,
        dispatch__review__draft__state_id=issue.current_id,dispatch__review__draft__assignment=assignment,
        dispatch__review__draft__kind='request',delivered=True).order_by('pk').first()
    if first and value['escalation_after_hours'] is not None and value['escalation_target'] is not None and value['clock_basis'] is not None:
        try:
            receipt_current(actor,first)
            result['escalation_due_at']=after(clock_at(first,value),value['escalation_after_hours'])
        except PermissionDenied:
            result['escalation_hold']='Original receipt access needed'
            findings.append('Review current access to the first request receipt.')
        except ValidationError:
            result['escalation_hold']='First request delivery time needed'
            findings.append('The first request evidence does not establish its actual delivery time.')
    else:findings.append('Some follow-up timing choices await an owner decision.')
    result['finding']=' '.join(dict.fromkeys(findings))
    return result
