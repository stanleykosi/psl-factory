from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import render, redirect
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.identity.models import Grant
from apps.agents.issues import investigate_issues
from apps.agents.models import AgentRun
from apps.core.evidence_access import public_evidence
from .issue_access import issue_projection, readable_runs
from . import issue_references as refs
from .models import Issue
from .issues import log_issue, update_issue, close_issue_log, reopen_issue, SEVERITIES
import json

@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id,source_action='issue.read');require(request.user,case,'issue.read')
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
            elif action=='reference_scope':refs.configure(request.user,case.pk,p['kind'],p['source_identity'],json.loads(p['allowed_fields']),p['mode'],int(p['evidence']),expected)
            elif action=='reference_observe':refs.observe(request.user,case.pk,int(p['issue']),int(p['state']),int(p['contract']),p['source_ref'],int(p['evidence']),expected)
            elif action=='reference_correct':refs.correct(request.user,case.pk,int(p['issue']),int(p['state']),int(p['previous']) if p.get('previous') else None,json.loads(p['references']),json.loads(p.get('relations') or '[]'),int(p['evidence']),p['note'],expected)
            elif action=='investigate':investigate_issues(request.user,case.pk,expected)
            else:raise ValidationError('Unsupported issue command')
            messages.success(request,'Issue evidence and log updated')
            return redirect('issues',case_id=case.pk)
        except (ValidationError,ValueError,KeyError) as exc:
            messages.error(request,str(exc));case.refresh_from_db()
    owners=list(get_user_model().objects.filter(is_active=True,grant__case=case,grant__action='issue.own',grant__active=True).distinct())
    permissions=set(Grant.objects.filter(case=case,user=request.user,active=True).values_list('action',flat=True))
    items=[p for i in Issue.objects.filter(case=case).select_related('case','current__owner').order_by('-pk') if (p:=issue_projection(i,request.user))]
    from apps.policy.services import decision_authority
    from .models import IssueClosureEntry
    closure_roles=[]
    if 'issue.close_log' in permissions:
        for role in ['QA','PM']:
            try:
                decision_authority(request.user,case,role)
                closure_roles.append(role)
            except (ValidationError,PermissionDenied):
                pass
    closure_entries=set(IssueClosureEntry.objects.filter(state_id__in=[item.current_id for item in items]).values_list('state_id','role'))
    owner_ids={owner.pk for owner in owners}
    from .issue_teams import projection as team_projection
    for item in items:
        state=item.current
        item.team = team_projection(request.user, item)
        item.team_replies = []
        if item.team['mode'] == 'team' and item.team['status'] == 'current':
            from .issue_teams import validate_reply
            for reply in item.team['assignment'].replies.select_related('actor','state').defer('state__note').order_by('-pk')[:20]:
                try:
                    validate_reply(reply, item)
                except (PermissionDenied,ValidationError):
                    continue
                item.team_replies.append(reply)
        item.operations=[]
        if item.team['mode'] != 'team' and state.status in ['Open','In Progress'] and state.owner_id==request.user.pk and state.owner_id in owner_ids and 'issue.work' in permissions:
            if not state.acknowledged_at:
                item.operations.append(('acknowledge','Owner acknowledges'))
            else:
                item.operations.extend([('start','Owner starts work'),('progress','Owner progress')])
                if state.severity:item.operations.append(('resolve','Owner resolves with fix'))
        if state.status!='Closed' and 'issue.manage' in permissions:
            item.operations.append(('manage','Manager assignment / PM severity'))
        item.close_roles=[role for role in closure_roles if (state.pk,role) not in closure_entries] if state.status=='Resolved' else []
    return render(request,'pmo/issues.html',{'case':case,'issues':items,'issue_permissions':permissions,
        'owners':owners,'severities':SEVERITIES,'evidence':public_evidence(case.evidence.all()).order_by('-pk'),
        'runs':list(readable_runs(AgentRun.objects.filter(case=case,provider='deterministic-issue-investigation-v1').order_by('-pk'),request.user))[:10]})
