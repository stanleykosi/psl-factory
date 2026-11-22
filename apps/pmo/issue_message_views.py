from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.core.services import bump, lock_case
from apps.core.views import accessible_case
from apps.documents.contracts import validate
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.issue_message_validators import COMPONENT, VALUE
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import active_component, reference_values, role_policy
from apps.policy.services import PolicyHold

from . import issue_messages as service, issue_teams
from .issue_access import state_public
from .issue_models import Issue
from .issue_message_models import IssueMessageDraft, IssueMessageReview, IssueMessageDispatch, IssueMessageAttempt, IssueMessageCancellation
from .issue_message_forms import (MessageRulesForm, RoutesFormSet, PrepareMessageForm, EditMessageForm,
    ReviewMessageForm, ReleaseMessageForm, ReceiptMessageForm, SenderActionForm, ManualStartForm, CancelMessageForm, evidence_choices)


def permissions(actor,case):
    return set(Grant.objects.filter(user=actor,case=case,active=True).values_list('action',flat=True))


def eligible(actor,case,roles):
    result=[]
    for role in roles:
        try:role_policy(actor,case,role)
        except (PermissionDenied,ValidationError):continue
        result.append(role)
    return result


def strict(post,form):
    if set(post)-set(form.fields)-{'csrfmiddlewaretoken','action'}:
        raise ValidationError('Use the fields in the displayed message form.')


def error(form,exc):
    form.add_error(None,'The required review or delivery rules need a current owner decision.' if isinstance(exc,PolicyHold) else '; '.join(exc.messages))


def readable_issue(request,case_id,issue_id):
    case=accessible_case(request.user,case_id)
    require(request.user,case,'issue.read')
    require(request.user,case,'issue.message.read')
    issue=get_object_or_404(Issue.objects.select_related('case','current__owner'),case=case,pk=issue_id)
    if not state_public(issue.current):raise PermissionDenied('Use the source-authorised private issue interface.')
    return case,issue


@login_required
@never_cache
@require_http_methods(['GET','HEAD','POST'])
def index(request,case_id,issue_id):
    case,issue=readable_issue(request,case_id,issue_id)
    allowed=permissions(request.user,case)
    form=PrepareMessageForm(case,issue,request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        d=form.cleaned_data
        try:
            strict(request.POST,form)
            draft=service.prepare(request.user,case.pk,issue.pk,d['state'],d['kind'],d['operation_key'],d['revision'])
        except ValidationError as exc:error(form,exc)
        else:
            messages.success(request,'Message suggestion prepared. Review its wording before releasing it.')
            return redirect('issue_message_detail',case_id=case.pk,issue_id=issue.pk,draft_id=draft.pk)
    rows=[]
    records=issue.message_drafts.select_related('issue__case','state__issue__case','actor').defer('body','source').order_by('-number')[:20]
    for draft in records:
        try:service.readable(request.user,draft)
        except (PermissionDenied,ValidationError):continue
        entry=IssueMessageReview.objects.defer('note').filter(draft=draft).first()
        review_visible=True
        if entry:
            try:service.review_readable(request.user,entry)
            except (PermissionDenied,ValidationError):review_visible=False
        dispatch=IssueMessageDispatch.objects.filter(review=entry).first() if entry else None
        label,receipt,finding=service.status(dispatch,request.user) if dispatch else (
            'Wording approved' if entry and entry.verdict=='approve' else 'Returned for changes' if entry and entry.verdict=='return'
            else 'Rejected' if entry else 'Review needed',None,'')
        if not review_visible:label,receipt,finding='Review needs access',None,'Review current access to the original review evidence.'
        rows.append({'draft':draft,'review':entry if review_visible else None,'dispatch':dispatch,'status':label,'receipt':receipt,'finding':finding})
    finding=''
    try:timeline=service.chronology(request.user,case,issue.pk)
    except (PermissionDenied,ValidationError) as exc:
        timeline={};finding='Review the current team and its source authority before preparing a message.'
    return render(request,'pmo/issue_messages.html',{'case':case,'issue':issue,'rows':rows,'form':form,
        'permissions':allowed,'timeline':timeline,'finding':finding,
        'can_prepare':'issue.message.prepare' in allowed and issue.current.status in {'Open','In Progress'} and not finding})


@login_required
@never_cache
@require_http_methods(['GET','HEAD','POST'])
def detail(request,case_id,issue_id,draft_id):
    case,issue=readable_issue(request,case_id,issue_id)
    draft=get_object_or_404(IssueMessageDraft.objects.select_related('issue__case','state__issue__case','actor','assignment').defer('body','source'),
                            pk=draft_id,issue=issue)
    service.readable(request.user,draft)
    allowed=permissions(request.user,case)
    try:config,value=service.rules(case)
    except (PermissionDenied,ValidationError):config,value=None,{}
    reviewers=eligible(request.user,case,value.get('reviewer_roles',[]))
    senders=eligible(request.user,case,value.get('sender_roles',[]))
    channels=[r['channel'] for r in value.get('routes',[]) if r['team_key']==draft.assignment.team_key]
    entry=IssueMessageReview.objects.select_related('actor').defer('note').filter(draft=draft).first()
    review_visible=True
    review_current=False
    if entry:
        try:service.review_readable(request.user,entry)
        except (PermissionDenied,ValidationError):review_visible=False
        if entry.verdict=='approve':
            try:service.current_review(request.user,case,entry.pk);review_current=True
            except (PermissionDenied,ValidationError):pass
    dispatch=IssueMessageDispatch.objects.filter(review=entry).first() if entry else None
    current=False
    finding=''
    if dispatch is None:
        try:service.check_draft(request.user,draft);current=True
        except (PermissionDenied,ValidationError):finding='The source, owner or drafting authority changed. Prepare current wording before a new release.'
    action=request.POST.get('action') if request.method=='POST' else None
    forms={
        'edit':EditMessageForm(case,draft,request.POST if action=='edit' else None),
        'review':ReviewMessageForm(case,reviewers,request.POST if action=='review' else None),
        'release':ReleaseMessageForm(case,senders,channels,request.POST if action=='release' else None),
        'receipt':ReceiptMessageForm(case,senders,request.POST if action=='receipt' else None),
        'manual':ManualStartForm(case,request.POST if action=='manual' else None),
        'recover':SenderActionForm(case,senders,request.POST if action=='recover' else None,auto_id='message_recover_%s'),
        'cancel':CancelMessageForm(case,senders,request.POST if action=='cancel' else None,auto_id='message_cancel_%s'),
    }
    if request.method=='POST':
        if action not in forms:raise Http404('Choose a displayed message action.')
        form=forms[action]
        if form.is_valid():
            d=form.cleaned_data
            try:
                strict(request.POST,form)
                if action=='edit':
                    result=service.prepare(request.user,case.pk,issue.pk,d['state'],draft.kind,d['operation_key'],d['revision'],
                        previous_id=d['previous'],body=d['body'],evidence_id=int(d['evidence']),reason=d['reason'])
                    return redirect('issue_message_detail',case_id=case.pk,issue_id=issue.pk,draft_id=result.pk)
                elif action=='review':service.review(request.user,case.pk,draft.pk,d['role'],d['verdict'],int(d['evidence']),d['note'],d['revision'])
                elif action=='release':
                    if entry is None:raise ValidationError('Review the wording before releasing this message.')
                    service.release(request.user,case.pk,entry.pk,d['role'],d['channel'],d['revision'],not_before=d['not_before'])
                else:
                    if dispatch is None:raise ValidationError('Release reviewed wording before checking its delivery.')
                    if action=='manual':service.begin_manual(request.user,case.pk,dispatch.pk,d['revision'])
                    elif action=='recover':service.recover(request.user,case.pk,dispatch.pk,d['role'],d['revision'])
                    elif action=='cancel':service.cancel(request.user,case.pk,dispatch.pk,d['role'],d['reason'],d['revision'])
                    elif action=='receipt':service.attest(request.user,case.pk,dispatch.pk,d['role'],int(d['evidence']),
                        d['reference'],d['delivered'],d['delivered_at'],d['checked'],d['revision'])
            except ValidationError as exc:error(form,exc)
            else:
                messages.success(request,'Message record updated. Only a recorded delivery receipt establishes delivery.')
                return redirect('issue_message_detail',case_id=case.pk,issue_id=issue.pk,draft_id=draft.pk)
    label,receipt,delivery_finding=service.status(dispatch,request.user) if dispatch else ('Not released',None,'')
    started=bool(dispatch and IssueMessageAttempt.objects.filter(dispatch=dispatch).exists())
    cancellation=IssueMessageCancellation.objects.select_related('actor').filter(dispatch=dispatch).first() if dispatch else None
    return render(request,'pmo/issue_message_detail.html',{'case':case,'issue':issue,'draft':draft,'review':entry if review_visible else None,
        'review_held':not review_visible,
        'dispatch':dispatch,'status':label,'receipt':receipt,'finding':finding,'delivery_finding':delivery_finding,'cancellation':cancellation,
        'forms':forms,'permissions':allowed,'rules_available':bool(value),'started':started,
        'can_edit':current and not dispatch and 'issue.message.prepare' in allowed,
        'can_review':current and not entry and bool(reviewers) and 'issue.message.review' in allowed,
        'can_release':current and review_current and not dispatch and bool(senders) and bool(channels) and value.get('independent_release') is not None and 'issue.message.release' in allowed,
        'can_cancel':bool(dispatch) and not started and not receipt and label!='Cancelled' and bool(senders) and 'issue.message.release' in allowed,
        'can_manual':bool(dispatch) and dispatch.route['mode']=='manual_evidence' and not started and label=='Ready for manual sending' and dispatch.actor_id==request.user.pk and 'issue.message.release' in allowed,
        'can_recover':started and not receipt and bool(senders) and 'issue.message.recover' in allowed,
        'can_receipt':started and not receipt and bool(dispatch) and dispatch.route['mode']=='manual_evidence' and bool(senders) and 'issue.message.recover' in allowed and 'evidence.add' in allowed})


@login_required
@never_cache
@require_http_methods(['GET','HEAD','POST'])
def configuration(request,case_id):
    case=accessible_case(request.user,case_id)
    require(request.user,case,'policy.read');require(request.user,case,'policy.configure')
    current,value,finding=None,{},''
    try:current=active_component(COMPONENT,case)
    except (PermissionDenied,ValidationError):pass
    if current:
        from apps.policy.impact import configuration as readable_configuration
        readable_configuration(request.user,case.pk,current.pk)
        value=reference_values(current)[0]
        validate(VALUE,value)
        try:service.rules(case)
        except (PermissionDenied,ValidationError):finding='Existing settings need a current team or source review before use.'
    try:teams=issue_teams.rules(case)[1]['teams']
    except (PermissionDenied,ValidationError):teams=[]
    initial={k:v for k,v in value.items() if k not in {'routes'}}
    for field in ['independent_release','draft_on_owner_wait']:
        initial[field]='yes' if value.get(field) is True else 'no' if value.get(field) is False else ''
    initial['revision']=case.revision
    form=MessageRulesForm(request.POST if request.method=='POST' else None,initial=initial,auto_id='message_rules_%s')
    form.fields['evidence'].choices=evidence_choices(case,kinds=['policy_decision'],
        selected=request.POST.get('evidence') if request.method=='POST' else None)
    routes=RoutesFormSet(request.POST if request.method=='POST' else None,initial=value.get('routes',[]),
                        prefix='routes',form_kwargs={'teams':teams})
    if request.method=='POST' and form.is_valid() and routes.is_valid():
        d=form.cleaned_data
        try:
            names=set(form.fields)|{'csrfmiddlewaretoken'}
            names.update(field.html_name for row in routes for field in row)
            names.update(field.html_name for field in routes.management_form)
            if set(request.POST)-names:raise ValidationError('Use the displayed message settings fields.')
            route_values=[{k:row[k] for k in ['team_key','channel','destination','mode']} for row in routes.cleaned_data
                          if row and not row.get('DELETE')]
            payload={k:d[k] for k in ['reviewer_roles','sender_roles','independent_release','reminder_after_hours',
                'escalation_after_hours','draft_on_owner_wait']}
            payload.update(routes=route_values,escalation_target=d['escalation_target'] or None,clock_basis=d['clock_basis'] or None)
            with transaction.atomic():
                locked=lock_case(request.user,case.pk,'policy.configure',d['revision'])
                service.proof(locked,int(d['evidence']))
                draft_operator_policy(request.user,locked.pk,COMPONENT,payload,int(d['evidence']),timezone.now())
                bump(locked)
        except ValidationError as exc:error(form,exc)
        else:
            messages.success(request,'Owner-message settings saved as a draft. Review and activate the version before use.')
            return redirect('issue_message_configuration',case_id=case.pk)
    return render(request,'pmo/issue_message_configuration.html',{'case':case,'form':form,'routes':routes,
                                                               'current':current,'finding':finding,'teams_available':bool(teams)})
