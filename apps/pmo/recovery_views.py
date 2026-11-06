import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.policy.document_validators import ROLES
from apps.policy.change_drafts import draft_standard_policy
from apps.agents.authority_recovery import investigate_recovery
from apps.agents.models import AgentRun
from adapters.authority_recovery import LocalAuthorityRecoveryAdapter
from .recoveries import request_recovery,decide_recovery,finalize_recovery
from .emergency_followups import create_followup,complete_followup,link_followup_revision
from .models import AuthorityRecoveryRequest,EmergencyOutcome,BaselineAdoption,EmergencyFollowup,ChangeClosure


@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'authority.read')
    if request.method=='POST':
        try:
            p=request.POST;expected=int(p['revision']);action=p['action']
            if action=='request':request_recovery(request.user,case.pk,p['kind'],int(p['target']),int(p['evidence']),p['note'],expected)
            elif action=='decide':decide_recovery(request.user,case.pk,int(p['request']),p['role'],p['verdict'],int(p['evidence']),p['note'],expected)
            elif action=='finalize':finalize_recovery(request.user,case.pk,int(p['request']),expected)
            elif action=='investigate':investigate_recovery(request.user,case.pk,int(p['request']),expected)
            elif action=='followup':create_followup(request.user,case.pk,int(p['outcome']),p['reference'],p['category'],p['module'],p['description'],p['note'],int(p['evidence']),expected)
            elif action=='complete':complete_followup(request.user,case.pk,int(p['followup']),int(p['closure']),p['note'],expected)
            elif action=='relink':link_followup_revision(request.user,case.pk,int(p['followup']),int(p['version']),p['note'],expected)
            elif action=='policy':draft_standard_policy(request.user,case.pk,'D05.revision_invalidation_rules',json.loads(p['value']),int(p['evidence']),p['effective_from'])
            else:raise ValidationError('Unsupported recovery command')
            messages.success(request,'Recorded current evidence; original history and financial/release controls remain preserved')
            return redirect('authority_recovery',case_id=case.pk)
        except (ValidationError,ValueError,KeyError) as exc:messages.error(request,str(exc));case.refresh_from_db()
    rows=[]
    for r in AuthorityRecoveryRequest.objects.filter(case=case).order_by('-pk')[:100]:
        try:projection=LocalAuthorityRecoveryAdapter().read(case,r.pk)
        except (ValidationError,PermissionDenied) as exc:projection={'findings':[str(exc)]}
        rows.append({'record':r,'projection':projection})
    return render(request,'pmo/recoveries.html',{'case':case,'rows':rows,'roles':ROLES,'evidence':case.evidence.all(),
        'runs':AgentRun.objects.filter(case=case,provider='deterministic-authority-investigation-v1').order_by('-pk')[:10],
        'outcomes':EmergencyOutcome.objects.filter(profile__version__change__case=case).order_by('-pk')[:100],
        'adoptions':BaselineAdoption.objects.filter(revision__dossier__case=case).order_by('-pk')[:100],
        'followups':EmergencyFollowup.objects.filter(outcome__profile__version__change__case=case).select_related('version__change').order_by('-pk')[:100],
        'closures':ChangeClosure.objects.filter(authorization__version__change__case=case).order_by('-pk')[:100]})
