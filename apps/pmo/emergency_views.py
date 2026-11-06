from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.documents.models import Template,PublicationReceipt
from apps.agents.models import AgentRun
from apps.agents.emergencies import investigate_emergency
from apps.policy.change_drafts import draft_standard_policy
from apps.policy.clock_drafts import draft_clock_policy
from .emergency_forms import ProfileForm,PreauthorizationForm,OutcomeForm,EmergencyPolicyForm
from .emergencies import (capture_profile,decide_emergency,authorize_emergency,capture_outcome,record_review,
    decide_retrospective,reconcile_retrospective,preauthorization_inputs,timing,retrospective_inputs,emergency_policy)
from .emergency_documents import draft_retrospective
from .models import EmergencyProfile,EmergencyAuthorization,EmergencyOutcome


@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'emergency.read')
    forms={'profile':ProfileForm(case=case,auto_id='emergency_profile_%s'),
        'predecision':PreauthorizationForm(case=case,auto_id='emergency_predecision_%s'),
        'outcome':OutcomeForm(case=case,auto_id='emergency_outcome_%s'),
        'policy':EmergencyPolicyForm(auto_id='emergency_policy_%s')}
    forms['policy'].fields['evidence'].queryset=case.evidence.filter(kind='policy_decision')
    if request.method=='POST':
        try:
            p=request.POST;expected=int(p['revision']);action=p['action']
            if action in forms:
                form_class={'profile':ProfileForm,'predecision':PreauthorizationForm,'outcome':OutcomeForm,'policy':EmergencyPolicyForm}[action]
                kwargs={'case':case} if action!='policy' else {}
                forms[action]=form_class(p,auto_id='emergency_'+action+'_%s',**kwargs)
                if action=='policy':forms[action].fields['evidence'].queryset=case.evidence.filter(kind='policy_decision')
                if not forms[action].is_valid():raise ValidationError(forms[action].errors.as_text())
                d=forms[action].cleaned_data
                if action=='profile':capture_profile(request.user,case.pk,d['version'].pk,d['candidate'].pk,d['critical_production'],d['p1'],d['evidence'].pk,d['note'],expected)
                elif action=='predecision':decide_emergency(request.user,case.pk,d['profile'].pk,d['role'],d['authority_role'],d['verdict'],d['evidence'].pk,d['note'],expected)
                elif action=='outcome':capture_outcome(request.user,case.pk,d['profile'].pk,d['authorization'].pk if d['authorization'] else None,d['implemented_at'],d['evidence'].pk,d['note'],expected)
                else:
                    function=draft_clock_policy if d['component'].startswith('D04.') else draft_standard_policy
                    function(request.user,case.pk,d['component'],d['value'],d['evidence'].pk,d['effective_from'])
            elif action=='authorize':authorize_emergency(request.user,case.pk,int(p['profile']),expected)
            elif action=='review':record_review(request.user,case.pk,int(p['outcome']),int(p['evidence']),p['note'],expected)
            elif action=='retrospective':decide_retrospective(request.user,case.pk,int(p['outcome']),p['role'],p['verdict'],int(p['evidence']),p['note'],expected)
            elif action=='reconcile':reconcile_retrospective(request.user,case.pk,int(p['outcome']),expected)
            elif action=='investigate':investigate_emergency(request.user,case.pk,int(p['outcome']),expected)
            elif action=='scan':
                from django.db import transaction
                from apps.core.services import lock_case
                from .emergency_obligations import scan_outcome
                with transaction.atomic():
                    lock_case(request.user,case.pk,'emergency.manage',expected)
                    scan_outcome(request.user,case.pk,int(p['outcome']))
            elif action=='draft':draft_retrospective(request.user,case.pk,int(p['outcome']),int(p['template']),p['audience'],expected)
            else:raise ValidationError('Unsupported emergency command')
            messages.success(request,'Emergency evidence updated; publication remains a separate exact-version review')
            return redirect('emergencies',case_id=case.pk)
        except (ValidationError,ValueError,KeyError) as exc:messages.error(request,str(exc));case.refresh_from_db()
    profiles=list(EmergencyProfile.objects.filter(version__change__case=case).select_related('version__change','candidate').order_by('-pk')[:100])
    for profile in profiles:
        try:profile.readiness=preauthorization_inputs(case,profile);profile.findings=[]
        except (ValidationError,PermissionDenied) as exc:profile.findings=[str(exc)];profile.readiness=None
    outcomes=list(EmergencyOutcome.objects.filter(profile__version__change__case=case).select_related('profile__version__change','profile__candidate','authorization').order_by('-pk')[:100])
    for outcome in outcomes:
        outcome.clock=timing(case,outcome)
        try:outcome.readiness=retrospective_inputs(case,outcome);outcome.findings=[]
        except (ValidationError,PermissionDenied) as exc:outcome.readiness=None;outcome.findings=[str(exc)]
    try:policy,pins=emergency_policy(case);policy_error=''
    except ValidationError as exc:policy={};pins={};policy_error=str(exc)
    return render(request,'pmo/emergencies.html',{'case':case,'forms':forms,'profiles':profiles,'outcomes':outcomes,
        'policy':policy,'policy_pins':pins,'policy_error':policy_error,
        'authorizations':EmergencyAuthorization.objects.filter(profile__version__change__case=case).order_by('-pk')[:100],
        'templates':Template.objects.filter(case=case,definition__document_type__in=['project_artifact','status_report']),
        'evidence':case.evidence.all(),'runs':AgentRun.objects.filter(case=case,provider='deterministic-emergency-investigation-v1').order_by('-pk')[:10],
        'receipts':PublicationReceipt.objects.filter(publication__version__emergencydocumentbinding__outcome__profile__version__change__case=case)})
