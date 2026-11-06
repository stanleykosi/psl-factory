from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import render,redirect
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.documents.models import Template,PublicationReceipt
from apps.agents.models import AgentRun
from apps.agents.escalations import investigate_escalations
from apps.policy.clock_drafts import draft_clock_policy
from .forms import ClockPolicyForm
from .escalation_forms import ProfileForm,RequestForm
from .escalations import capture_profile,current_profile,request_escalation,decide_escalation,draft_escalation,scan_profile,timing
from .models import EscalationProfile,EscalationRequest

@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'issue.read')
    pf=ProfileForm(case=case,auto_id='escalation_profile_%s');rf=RequestForm(case=case,auto_id='escalation_request_%s')
    cf=ClockPolicyForm(auto_id='escalation_clock_%s');cf.fields['evidence'].queryset=case.evidence.filter(kind='policy_decision')
    if request.method=='POST':
        try:
            p=request.POST;expected=int(p['revision']);action=p['action']
            if action=='profile':
                pf=ProfileForm(p,case=case,auto_id='escalation_profile_%s')
                if not pf.is_valid():raise ValidationError(pf.errors.as_text())
                d=pf.cleaned_data;capture_profile(request.user,case.pk,d['state'].issue_id,d['state'].pk,d['classification'],d['timeline_impact'],d['trigger_at'],d['evidence'].pk,d['note'],expected)
            elif action=='request':
                rf=RequestForm(p,case=case,auto_id='escalation_request_%s')
                if not rf.is_valid():raise ValidationError(rf.errors.as_text())
                d=rf.cleaned_data;request_escalation(request.user,case.pk,d['profile'].pk,d['direction'],d['target'],d['evidence'].pk,d['note'],expected)
            elif action=='decision':decide_escalation(request.user,case.pk,int(p['request']),p['role'],p['verdict'],p['note'],expected,p.get('delegated')=='on')
            elif action=='draft':draft_escalation(request.user,case.pk,int(p['request']),int(p['template']),expected)
            elif action=='scan':
                # Scan service also locks and checks its current profile; the UI expected revision guards this command.
                from apps.core.services import lock_case
                from django.db import transaction
                with transaction.atomic():
                    lock_case(request.user,case.pk,'issue.escalate',expected)
                    scan_profile(request.user,case.pk,int(p['profile']))
            elif action=='investigate':investigate_escalations(request.user,case.pk,expected)
            elif action=='clock':
                cf=ClockPolicyForm(p,auto_id='escalation_clock_%s');cf.fields['evidence'].queryset=case.evidence.filter(kind='policy_decision')
                if not cf.is_valid():raise ValidationError(cf.errors.as_text())
                d=cf.cleaned_data;draft_clock_policy(request.user,case.pk,d['component'],d['value'],d['evidence'].pk,d['effective_from'])
            else:raise ValidationError('Unsupported escalation operation')
            messages.success(request,'Escalation evidence updated; delivery is a separate reviewed operation')
            return redirect('escalations',case_id=case.pk)
        except (ValidationError,ValueError,KeyError) as exc:
            messages.error(request,str(exc));case.refresh_from_db()
    profiles=list(EscalationProfile.objects.filter(state__issue__case=case).select_related('state__issue').order_by('-pk')[:100])
    for p in profiles:
        try:current_profile(case,p.pk);p.is_current=True;p.clock=timing(p)
        except ValidationError:p.is_current=False;p.clock=None
    return render(request,'pmo/escalations.html',{'case':case,'profile_form':pf,'request_form':rf,'clock_form':cf,'profiles':profiles,
        'requests':EscalationRequest.objects.filter(profile__state__issue__case=case).order_by('-pk')[:100],
        'templates':Template.objects.filter(case=case,definition__document_type__in=['status_report','project_artifact']),
        'receipts':PublicationReceipt.objects.filter(publication__version__escalationdocumentbinding__request__profile__state__issue__case=case),
        'runs':AgentRun.objects.filter(case=case,provider='deterministic-escalation-investigation-v1').order_by('-pk')[:10]})
