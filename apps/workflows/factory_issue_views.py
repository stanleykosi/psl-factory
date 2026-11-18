"""Work-centric issue investigation with native source controls and owner response."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from apps.core.models import Case
from apps.core.workbench import granted
from apps.pmo.models import Issue
from . import factory,factory_issues as domain
from .factory_progress_views import StartWithBackground, start_work

class StartForm(StartWithBackground):
    definition=forms.CharField(initial=domain.DEFINITION,widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none())
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,*args,case_id=None,**kwargs):
        super().__init__(*args,**kwargs);cases=granted(actor,['issue.read','factory.start','evidence.add']);self.fields['case'].queryset=cases
        self.selected=cases.filter(pk=case_id).first() if case_id else None
        ids=[]
        if self.selected:
            self.fields['case'].initial=self.selected;self.fields['revision'].initial=self.selected.revision
            for issue in Issue.objects.filter(case=self.selected):
                try:domain.inputs(actor,self.selected,issue.pk);ids.append(issue.pk)
                except (ValidationError,PermissionDenied):continue
        self.fields['issue']=forms.ModelChoiceField(queryset=Issue.objects.filter(pk__in=ids),label='Current authoritative issue')
        self.fields['issue'].label_from_instance=lambda i:f'{i.reference} · {i.current.title}'
        if not self.is_bound:self.fields['key'].initial='ISSUE-'+uuid4().hex


@never_cache
@require_http_methods(['GET','HEAD','POST'])
def create(request):
    data=request.POST if request.method=='POST' else None
    try:form=StartForm(request.user,data,case_id=request.POST.get('case') if data else request.GET.get('case'))
    except (ValueError,ValidationError):form=StartForm(request.user,{});form.is_valid();form.add_error(None,'Select an accessible case')
    if not data and request.GET.get('issue', '').isdecimal():
        form.fields['issue'].initial = form.fields['issue'].queryset.filter(pk=request.GET['issue']).first()
    if data and form.is_valid():
        try:
            p=form.cleaned_data
            if p['definition']!=domain.DEFINITION:raise ValidationError('Select the issue investigation definition')
            return start_work(request, lambda: domain.start(request.user, p['case'].pk, p['key'], p['issue'].pk, p['revision']),
                              p['background'])
        except ValidationError as exc:form.add_error(None,domain.finding(exc))
    return render(request,'factory/issue_start.html',{'form':form,'case':form.selected})


def presentation(actor,work):
    from .factory_views import permitted
    factory.access(actor,work.case,'factory.read',domain.DEFINITION)
    row={'work':work,'title':'Issue investigation and owner follow-up','owner':'Current responsible owner','state':work.status,'next_action':'Inspect current issue evidence','blocker':'','needs_me':False,'can_advance':False,'jobs':[],'tasks':[],'readiness_changed':False,'issues':{}}
    try:panel=domain.projection(actor,work)
    except (ValidationError,PermissionDenied):
        row.update(state='Source access needs review',next_action='Current issue and external source-reader permission is required');return row
    stopped=work.cancel_requested or work.status in ['verified','cancelled','followup_needed']
    row.update(title=panel['issue'].current.title,owner=panel['team']['label'],issues=panel,tasks=panel['tasks'],blocker=panel['finding'],next_action=panel['finding'],readiness_changed=panel['readiness_changed'],can_advance=bool(panel['options']) and not stopped and permitted(actor,work,'factory.execute'),can_configure=permitted(actor,work,'policy.configure'),can_manage=permitted(actor,work,'factory.manage'))
    panel['can_respond']=panel['can_respond'] and not stopped and permitted(actor,work,'issue.work')
    row['can_assign_team'] = not stopped and permitted(actor,work,'issue.manage')
    panel['can_record_team'] = panel['team']['mode']=='team' and panel['team']['can_record'] and panel['can_respond']
    row['needs_me']=panel['can_respond'] and any(t.status=='open' for t in panel['tasks']) or row['can_advance']
    if work.status=='verified' and not panel['readiness_changed']:row['next_action']='Owner follow-up recorded. Review issue resolution in the issue register.'
    return row


@never_cache
@require_http_methods(['GET','HEAD','POST'])
def detail(request,work):
    reply_form = None
    try:domain.source(work,request.user,False)
    except (ValidationError,PermissionDenied):
        return render(request,'factory/issue_detail.html',{'row':presentation(request.user,work),'case':work.case},status=403)
    if request.method=='POST':
        try:
            p=request.POST;action=p.get('action');revision=int(p.get('revision','0'));case_revision=int(p.get('case_revision','0'))
            if action=='advance':factory.advance(request.user,work.pk,revision)
            elif action=='respond':domain.respond(request.user,work.pk,revision,case_revision,int(p['task']),int(p['task_revision']),p['operation'],int(p['evidence']),p['note'],p['next_action'])
            elif action=='team_respond':
                from apps.pmo.issue_team_forms import TeamReplyForm
                panel = domain.projection(request.user,work)
                task = next((task for task in panel['tasks'] if task.pk==int(p.get('task','0')) and task.status=='open'),None)
                if not task or not panel['team']['can_record']:
                    raise ValidationError('Open the current team response assigned to you.')
                reply_form = TeamReplyForm(work,panel['team'],task,p)
                if not reply_form.is_valid():raise ValidationError('Check the team response fields.')
                if set(p)-set(reply_form.fields)-{'csrfmiddlewaretoken','action'}:
                    raise ValidationError('Use the displayed team response fields.')
                data = reply_form.cleaned_data
                team_reply = {key:data[key] for key in ['assignment_id','operation_key','party','channel','responded_at','source_ref']}
                domain.respond(request.user,work.pk,data['revision'],data['case_revision'],data['task'],data['task_revision'],
                    data['operation'],int(data['evidence']),data['note'],data['next_action'],team_reply=team_reply)
            elif action in ['refresh','restart']:domain.refresh(request.user,work.pk,revision,case_revision,p.get('reason',''),restart=action=='restart')
            elif action=='cancel':factory.manage(request.user,work.pk,revision,'cancel')
            elif action=='resume':factory.manage(request.user,work.pk,revision,'resume')
            elif action=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(p['configuration']),p.get('reason',''))
            elif action=='reconcile':
                from apps.agents.factory_coordinator import reconcile
                reconcile(request.user,work.pk,revision)
            else:raise ValidationError('Select a current typed action')
            messages.success(request,'Issue investigation action recorded');return redirect(request.get_full_path())
        except (ValidationError,ValueError,KeyError) as exc:messages.error(request,str(exc));work.refresh_from_db();work.case.refresh_from_db()
    from apps.core.evidence_access import public_evidence
    row = presentation(request.user,work)
    if row['issues'].get('can_record_team') and reply_form is None:
        from apps.pmo.issue_team_forms import TeamReplyForm
        task = next((task for task in row['tasks'] if task.status=='open'),None)
        if task:reply_form = TeamReplyForm(work,row['issues']['team'],task)
    from apps.pmo.issue_team_models import IssueTeamReply
    team_history = IssueTeamReply.objects.filter(assignment__issue_id=work.request['issue_id']).select_related(
        'assignment','actor','state').order_by('-pk')[:20]
    return render(request,'factory/issue_detail.html',{'row':row,'case':work.case,
        'evidence':public_evidence(work.case.evidence.all()).defer('body').order_by('-pk')[:50],
        'team_reply_form':reply_form,'team_history':team_history})
