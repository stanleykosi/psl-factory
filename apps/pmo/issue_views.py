from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.identity.models import Grant
from apps.agents.issues import investigate_issues
from apps.agents.models import AgentRun
from .models import Issue
from .issues import log_issue, update_issue, close_issue_log, reopen_issue, SEVERITIES
import json

@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'issue.read')
    if request.method=='POST':
        try:
            p=request.POST;expected=int(p['revision']);action=p['action']
            if action=='log':log_issue(request.user,case.pk,p['reference'],p['title'],p['kind'],int(p['owner']),p['next_action'],int(p['evidence']),p['note'],expected,
                p.get('severity') or None,json.loads(p.get('external_links') or '[]'))
            elif action=='work':update_issue(request.user,case.pk,int(p['issue']),int(p['state']),p['operation'],int(p['evidence']),p['note'],expected,
                p.get('next_action') or None,int(p['owner']) if p.get('owner') else None,p.get('severity') or None,
                int(p['fix']) if p.get('fix') else None,int(p['root_cause']) if p.get('root_cause') else None)
            elif action=='close_log':close_issue_log(request.user,case.pk,int(p['issue']),int(p['state']),p['role'],int(p['evidence']),p['note'],expected)
            elif action=='reopen':reopen_issue(request.user,case.pk,int(p['issue']),int(p['state']),p['role'],int(p['evidence']),p['note'],p['next_action'],expected)
            elif action=='investigate':investigate_issues(request.user,case.pk,expected)
            else:raise ValidationError('Unsupported issue command')
            messages.success(request,'Issue evidence and log updated')
            return redirect('issues',case_id=case.pk)
        except (ValidationError,ValueError,KeyError) as exc:
            messages.error(request,str(exc));case.refresh_from_db()
    owners=get_user_model().objects.filter(is_active=True,grant__case=case,grant__action='issue.own',grant__active=True).distinct()
    return render(request,'pmo/issues.html',{'case':case,'issues':Issue.objects.filter(case=case).select_related('current__owner').order_by('-pk'),
        'owners':owners,'severities':SEVERITIES,'evidence':case.evidence.order_by('-pk'),
        'runs':AgentRun.objects.filter(case=case,provider='deterministic-issue-investigation-v1').order_by('-pk')[:10]})
