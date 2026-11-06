from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.identity.models import Grant
from apps.documents.models import Template
from apps.policy.clock_drafts import draft_clock_policy
from apps.agents.meetings import suggest_commitments, investigate_actions
from .models import Meeting, ActionItem, ReportSchedule, PeriodReport, MinutesReportBinding
from .forms import MeetingForm, ActionForm, DraftMinutesForm, ReportForm, ClockPolicyForm
from .meetings import record_meeting, create_action, change_action, action_timing, link_action
from .reporting import draft_minutes, draft_period_report
from .schedules import save_schedule, arm_schedule, pause_schedule

@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'meeting.read')
    evidence=case.evidence.order_by('-pk');meetings=Meeting.objects.filter(case=case).select_related('current').order_by('-pk')
    owners=get_user_model().objects.filter(is_active=True,grant__case=case,grant__active=True,grant__action='action.own').distinct()
    participants=get_user_model().objects.filter(is_active=True,grant__case=case,grant__active=True,grant__action='meeting.participate').distinct()
    templates=Template.objects.filter(case=case)
    mf=MeetingForm(auto_id='meeting_%s');af=ActionForm(auto_id='action_%s');df=DraftMinutesForm(auto_id='minutes_%s');rf=ReportForm(auto_id='report_%s');cf=ClockPolicyForm(auto_id='clock_%s')
    def bind_queries():
        mf.fields['participants'].queryset=participants;mf.fields['evidence'].queryset=evidence
        af.fields['meeting'].queryset=meetings;af.fields['owner'].queryset=owners;af.fields['evidence'].queryset=evidence;af.fields['change_evidence'].queryset=evidence.filter(kind='change_request')
        df.fields['meeting'].queryset=meetings;df.fields['template'].queryset=templates.filter(definition__document_type='minutes')
        rf.fields['template'].queryset=templates.filter(definition__document_type='status_report')
        cf.fields['evidence'].queryset=evidence.filter(kind='policy_decision')
    bind_queries()
    if request.method=='POST':
        try:
            action=request.POST.get('action');expected=int(request.POST['revision'])
            if action=='meeting':
                mf=MeetingForm(request.POST,auto_id='meeting_%s');bind_queries()
                if not mf.is_valid():raise ValidationError(mf.errors.as_text())
                d=mf.cleaned_data;record_meeting(request.user,case.pk,d['reference'],d['kind'],d['occurred_at'],d['purpose'],d['summary'],[u.pk for u in d['participants']],d['decisions'] or [],d['evidence'].pk,expected,d['meeting_id'])
            elif action=='new_action':
                af=ActionForm(request.POST,auto_id='action_%s');bind_queries()
                if not af.is_valid():raise ValidationError(af.errors.as_text())
                d=af.cleaned_data;create_action(request.user,case.pk,d['reference'],d['description'],d['owner'].pk if d['owner'] else None,d['due_at'],d['evidence'].pk,d['reason'],expected,
                    d['meeting'].pk if d['meeting'] else None,d['calculated'],d['change_evidence'].pk if d['change_evidence'] else None)
            elif action=='transition':
                change_action(request.user,case.pk,int(request.POST['item']),request.POST['operation'],int(request.POST['evidence']),request.POST.get('reason',''),expected,int(request.POST['action_revision']),
                    int(request.POST['owner']) if request.POST.get('owner') else None,request.POST.get('due_at') or None)
            elif action=='link':
                link_action(request.user,case.pk,int(request.POST['meeting']),int(request.POST['item']),int(request.POST['evidence']),expected)
            elif action=='minutes':
                df=DraftMinutesForm(request.POST,auto_id='minutes_%s');bind_queries()
                if not df.is_valid():raise ValidationError(df.errors.as_text())
                d=df.cleaned_data;draft_minutes(request.user,case.pk,d['meeting'].pk,d['template'].pk,d['audience'],expected)
            elif action in ['report','schedule']:
                if action=='report':
                    rf=ReportForm(request.POST,auto_id='report_%s');bind_queries()
                    if not rf.is_valid():raise ValidationError(rf.errors.as_text())
                    d=rf.cleaned_data;draft_period_report(request.user,case.pk,d['kind'],d['start_at'],d['end_at'],d['template'].pk,d['audience'],expected)
                else:save_schedule(request.user,case.pk,request.POST['kind'],int(request.POST['template']),request.POST['audience'],expected)
            elif action=='arm':arm_schedule(request.user,case.pk,int(request.POST['schedule']),request.POST['after'],expected)
            elif action=='pause_schedule':pause_schedule(request.user,case.pk,int(request.POST['schedule']),request.POST.get('reason',''),expected)
            elif action=='clock_draft':
                cf=ClockPolicyForm(request.POST,auto_id='clock_%s');bind_queries()
                if not cf.is_valid():raise ValidationError(cf.errors.as_text())
                d=cf.cleaned_data;draft_clock_policy(request.user,case.pk,d['component'],d['value'],d['evidence'].pk,d['effective_from'])
            elif action=='suggest':suggest_commitments(request.user,case.pk,int(request.POST['evidence']),expected)
            elif action=='investigate':investigate_actions(request.user,case.pk)
            else:raise ValidationError('Unknown meeting/report operation')
            messages.success(request,'Recorded. Review the current commitment history and document drafts.')
            return redirect('meetings',case_id=case.pk)
        except (ValidationError,ValueError,KeyError) as exc:
            messages.error(request,str(exc));case.refresh_from_db()
    bind_queries()
    items=list(ActionItem.objects.filter(case=case).select_related('current__owner').order_by('-pk'))
    for item in items:item.timing=action_timing(item.current)
    actions=set(Grant.objects.filter(case=case,user=request.user,active=True).values_list('action',flat=True))
    return render(request,'pmo/meetings.html',{'case':case,'actions':actions,'meeting_form':mf,'action_form':af,'minutes_form':df,'report_form':rf,'clock_form':cf,
        'meetings':meetings,'items':items,'owners':owners,'evidence':evidence,'templates':templates,'schedules':ReportSchedule.objects.filter(case=case).order_by('pk'),
        'bindings':MinutesReportBinding.objects.filter(version__document__case=case).select_related('version__document').order_by('-pk'),
        'agent_runs':case.agentrun_set.filter(process_id__in=['P43','P04']).order_by('-pk')[:20] if 'agent.meetings' in actions else []})
