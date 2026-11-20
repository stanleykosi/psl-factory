"""Structured RFP operating settings; native RFP records retain business authority."""
from hashlib import sha256

from django import forms
from django.core.exceptions import ValidationError,PermissionDenied
from django.db.models import Q
from apps.documents.models import Template
from apps.policy.services import active_component,reference_values,resolve
from .factory_views import ProfileForm, QUEUES
from uuid import uuid4,UUID
from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.paginator import Paginator
from django.forms import formset_factory
from django.http import Http404
from django.shortcuts import get_object_or_404,render,redirect
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Evidence
from apps.core.services import lock_case
from apps.core.read_observation import read_observation
from apps.core.evidence_access import public_evidence
from apps.core.presentation import workspace_name
from apps.identity.services import visible_cases,require
from apps.policy.services import decision_authority
from apps.policy.models import Configuration
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.policy.rfp_outcome_validators import COMPONENT as OUTCOME_COMPONENT,METHOD as OUTCOME_METHOD
from apps.policy.rfp_loss_validators import COMPONENT as LOSS_COMPONENT, validate_reason_names
from apps.pmo import rfp,commercial
from apps.pmo.models import RFPCase,RFPDocumentBinding,RFPSubmission,RFPOutcome,RFPDisposition
from apps.documents.models import Publication,PublicationJob,PublicationReceipt
from apps.documents import controlled
from .models import FactoryWork,FactoryActivity,HumanTask
from . import factory as runtime

OUTCOME_CHOICES = {'won': 'Won', 'lost': 'Lost', 'pending': 'Pending', 'unknown': 'Unconfirmed'}


class RFPProfileForm(ProfileForm):
    template_id=forms.ModelChoiceField(queryset=Template.objects.none(),required=False,label='Client response template')
    route_key=forms.ChoiceField(required=False,label='Reviewed submission destination')

    def __init__(self,case,*args,**kwargs):
        super().__init__(case,*args,**kwargs)
        self.fields['template_id'].queryset=Template.objects.filter(case=case,definition__document_type='rfp_response').filter(
            Q(definition__internal_review_required=True)|~Q(definition__has_key='internal_review_required')).order_by('name','version')
        choices=[('','Not selected')]
        try:
            config=active_component('D11.adapter_configuration_refs',case)
            choices += [(row['key'],row['key'].replace('_',' ')) for row in reference_values(config) if row.get('kind')=='rfp_submission']
        except (ValidationError,PermissionDenied):pass
        self.fields['route_key'].choices=choices
        self.fields['route_key'].help_text='Only current workspace submission routes are listed. Selection grants no sending authority.'
        self.fields['executor_id'].label='Response publisher'
        for field,actions in [('executor_id',['case.read','rfp.read','rfp.submit','document.publish']),
                              ('information_resolver_id',['case.read','rfp.read'])]:
            for action in actions:
                self.fields[field].queryset=self.fields[field].queryset.filter(grant__case=case,grant__active=True,grant__action=action).distinct()


class SourceForm(forms.Form):
    response_evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),required=False,label='Response wording')
    public_terms=forms.ModelChoiceField(queryset=Evidence.objects.none(),required=False,label='Public commercial terms')
    requirements=forms.ModelChoiceField(queryset=Evidence.objects.none(),required=False,label='Requirements')
    plan=forms.ModelChoiceField(queryset=Evidence.objects.none(),required=False,label='Plan')
    costing=forms.ModelChoiceField(queryset=Evidence.objects.none(),required=False,label='Costing evidence')
    lessons=forms.ModelChoiceField(queryset=Evidence.objects.none(),required=False,label='Loss lessons, when applicable')
    revision=forms.IntegerField(widget=forms.HiddenInput,min_value=1)
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        kinds={'response_evidence':'rfp_response','public_terms':'rfp_commercial_terms','lessons':'rfp_lessons',
               **{kind:kind for kind in ['requirements','plan','costing']}}
        for field,kind in kinds.items():
            self.fields[field].queryset=public_evidence(Evidence.objects.filter(case=case,kind=kind)).order_by('-version','-pk')
            self.fields[field].label_from_instance=lambda e:e.source+' · version '+str(e.version)


class MappingForm(forms.Form):
    key=forms.CharField(required=False,max_length=100,label='Requirement reference')
    evidence_id=forms.ModelChoiceField(queryset=Evidence.objects.none(),required=False,label='Requirement source')
    response=forms.CharField(required=False,max_length=4000,widget=forms.Textarea(attrs={'rows':2}),label='Proposed response')
    disposition=forms.ChoiceField(required=False,choices=[('','Choose coverage'),('addressed','Addressed'),('clarification','Needs clarification'),('out_of_scope','Outside scope')],label='Coverage')
    def __init__(self,*args,case,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['evidence_id'].queryset=public_evidence(Evidence.objects.filter(case=case,kind__in=['requirements','rfp_intake'])).order_by('-pk')
        self.fields['evidence_id'].label_from_instance=lambda e:e.kind.replace('_',' ')+' · '+e.source+' · version '+str(e.version)
    def clean(self):
        data=super().clean()
        if data.get('DELETE'):return data
        if any(data.get(key) for key in ['key','evidence_id','response','disposition']):
            for key in ['key','evidence_id','response','disposition']:
                if not data.get(key):self.add_error(key,'Complete this requirement row or leave it empty.')
        return data


Mappings=formset_factory(MappingForm,extra=2,max_num=100,validate_max=True,can_delete=True)


def payload(form,mappings):
    value=form.cleaned_data
    return {'response_evidence':value['response_evidence'].pk if value['response_evidence'] else None,
        'public_terms':value['public_terms'].pk if value['public_terms'] else None,
        'sources':{key:value[key].pk if value[key] else None for key in ['requirements','plan','costing']},
        'lessons':value['lessons'].pk if value['lessons'] else None,
        'matrix':[dict(row,key=row['key'].strip(),evidence_id=row['evidence_id'].pk) for row in
            ({k:f.cleaned_data.get(k) for k in ['key','evidence_id','response','disposition']} for f in mappings
             if f.cleaned_data and not f.cleaned_data.get('DELETE')) if row['key']]}


def response(request,template,context):
    result=render(request,template,context);result['Cache-Control']='no-store';return result


def create(request):
    from . import factory_rfp as service
    from .factory_views import submit_start
    from apps.agents.assistant import work_intent
    from apps.agents.assistant_drafts import latest
    cases=[]
    for case in visible_cases(request.user).filter(kind='project').order_by('title'):
        try:runtime.access(request.user,case,'factory.start',service.DEFINITION);require(request.user,case,'evidence.add')
        except PermissionDenied:continue
        cases.append(case)
    selected=request.GET.get('case') or request.POST.get('case')
    if not selected:
        field=forms.ModelChoiceField(queryset=visible_cases(request.user).filter(pk__in=[c.pk for c in cases]),label='Workspace')
        field.label_from_instance=workspace_name
        return response(request,'factory/rfp_start.html',{'workspace_field':field.widget.render('case',None),'definition':service.DEFINITION})
    try:UUID(selected)
    except (ValueError,TypeError,AttributeError):raise Http404 from None
    case=get_object_or_404(visible_cases(request.user).filter(pk__in=[c.pk for c in cases]),pk=selected)
    root=RFPCase.objects.filter(case=case).select_related('current_intake').first()
    initial={'revision':case.revision}
    form=SourceForm(case,request.POST if request.method=='POST' else None,initial=initial)
    form.fields['reference']=forms.CharField(max_length=100,label='Work reference',initial=root.reference if root else '')
    form.fields['key']=forms.CharField(widget=forms.HiddenInput,max_length=100,initial=uuid4().hex)
    form.fields['background']=forms.BooleanField(required=False, initial=True, label='Continue in background after starting')
    form.fields['assistant_turn']=forms.UUIDField(required=False, widget=forms.HiddenInput)
    form.fields['draft_version']=forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)
    saved_rows = None
    if request.method == 'GET' and request.GET.get('assistant_turn'):
        try:
            turn = work_intent(request.user, request.GET['assistant_turn'], service.DEFINITION, case.pk)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            return redirect('design_agents')
        if turn.started_work_id:
            return redirect('factory_detail', turn.started_work_id)
        form.initial.update(assistant_turn=turn.pk, key=str(turn.pk))
        draft = latest(turn)
        if draft:
            selected_inputs = draft.payload['native_inputs']
            form.initial.update(reference=draft.payload['reference'], draft_version=draft.number,
                                response_evidence=selected_inputs['response_evidence'], public_terms=selected_inputs['public_terms'],
                                lessons=selected_inputs['lessons'], **selected_inputs['sources'])
            saved_rows = selected_inputs['matrix']
    mappings=Mappings(request.POST if request.method=='POST' else None,prefix='requirements',form_kwargs={'case':case},initial=saved_rows)
    if request.method=='POST' and form.is_valid() and mappings.is_valid():
        try:
            values = form.cleaned_data
            values.update(case=case, rfp_intake=root.current_intake_id if root else None, native_inputs=payload(form, mappings))
            return submit_start(request, values, service.DEFINITION,
                                lambda: service.start(request.user, case.pk, values['key'], values['native_inputs'],
                                                      values['reference'], values['revision']))
        except ValidationError as exc:form.add_error(None,exc)
    return response(request,'factory/rfp_start.html',{'case':case,'rfp':root,'form':form,'mappings':mappings,'definition':service.DEFINITION})


def allowed(actor,case,action):
    try:require(actor,case,action);return True
    except PermissionDenied:return False


def decision_options(actor,work,current,document,submission):
    """Offer native permitted actions; command services recheck the exact current target."""
    result=[];case=work.case
    if work.cancel_requested or work.status in ['verified','cancelled','followup_needed']:return result,[]
    valid=False
    if current:
        try:rfp.current_response(case,current.pk);valid=True
        except (ValidationError,PermissionDenied):pass
    def verdicts(action,role):
        if not allowed(actor,case,action):return []
        options=[]
        for verdict in ['approve','return','reject']:
            try:decision_authority(actor,case,role,verdict);options.append(verdict)
            except (ValidationError,PermissionDenied):pass
        return options
    if valid:
        try:rfp.reviewed(current);reviewed=True
        except (ValidationError,PermissionDenied):reviewed=False
        outstanding_reviews = [] if reviewed else rfp.REVIEW_ROLES
        for role in outstanding_reviews:
            last=current.reviews.filter(role=role).order_by('-pk').first()
            choices=verdicts('rfp.review',role)
            if last and last.verdict=='approve':
                try:
                    require(last.actor,case,'rfp.review')
                    if last.authority==decision_authority(last.actor,case,role):continue
                except (ValidationError,PermissionDenied):pass
            if choices:result.append({'kind':'response','target':current.pk,'role':role,'verdicts':choices,'title':role+' response review'})
        if reviewed:
            commercial_roles = ['PM','Head of PMO','CEO']
            try:
                commercial.valid_approvals(current.commercial, commercial_roles)
                commercial_roles = []
            except (ValidationError,PermissionDenied):pass
            for index,role in enumerate(commercial_roles):
                try:commercial.valid_approvals(current.commercial,['PM','Head of PMO','CEO'][:index+1]);continue
                except (ValidationError,PermissionDenied):pass
                choices=verdicts('commercial.decide',role)
                if 'approve' in choices:
                    try:commercial.valid_approvals(current.commercial,['PM','Head of PMO','CEO'][:index])
                    except (ValidationError,PermissionDenied):choices.remove('approve')
                if choices:result.append({'kind':'commercial','target':current.commercial_id,'role':role,'verdicts':choices,'title':role+' commercial decision'})
        if document and allowed(actor,case,'document.review_controlled'):
            try:
                controlled.current_version(case,document.pk)
                if HumanTask.objects.filter(version=document,status='open').exists():
                    choices=verdicts('document.review_controlled','PMO Lead')
                    if choices:result.append({'kind':'document','target':document.pk,'role':'PMO Lead','verdicts':choices,'title':'Final client response review'})
            except (ValidationError,PermissionDenied):pass
    outcome_roles=[]
    if submission and allowed(actor,case,'rfp.outcome'):
        try:
            config=active_component('D05.decision_action_matrix',case)
            for role in reference_values(config)[0].get('rfp',{}).get('outcome_roles',[]):
                try:rfp.authority(actor,case,'outcome',role);outcome_roles.append(role)
                except (ValidationError,PermissionDenied):pass
        except (ValidationError,PermissionDenied):pass
    return result,outcome_roles


@read_observation
def presentation(actor,work,submission_id=None):
    from . import factory_rfp as service
    from .factory_execution import available_actor,can_control
    from apps.agents.factory_coordinator import decorate
    runtime.access(actor,work.case,envelope=service.DEFINITION)
    value=None;state=None;finding='';options=[];jobs=[];missing=[];stale=[];planning_ready=False
    try:_,value=runtime.profile(work,recovery=True)
    except (ValidationError,PermissionDenied):finding='Review execution settings before further agent work. Existing human decisions remain available.'
    if value:
        try:
            state,latest,missing,stale,tasks,jobs=service.snapshot(work,value,reader=actor)
            options,finding=service.eligible(work,value,state,latest,missing,stale,tasks,jobs)
        except (ValidationError,PermissionDenied):finding='Source evidence or authority needs review before further agent work.'
        try:runtime.profile(work);planning_ready=True
        except (ValidationError,PermissionDenied):pass
    root=service.subject(work);current=service.response_for(work)
    document=service.review_document(work)
    actual_submissions=RFPSubmission.objects.filter(response__rfp=root).select_related('response','version')
    submission=actual_submissions.filter(pk=submission_id).first() if submission_id is not None else service.submission_for(work)
    outcome=RFPOutcome.objects.filter(submission=submission).order_by('-pk').first() if submission else None
    from apps.pmo.rfp_outcomes import outcome_selection_state
    selection=outcome_selection_state(work.case)
    disposition=RFPDisposition.objects.filter(rfp=root).first()
    if not jobs:jobs=list(PublicationJob.objects.filter(publication__factory_work=work).select_related('publication').order_by('pk'))
    decisions,outcome_roles=decision_options(actor,work,current,document,actual_submissions.exists())
    owner=available_actor(work)
    busy=bool(work.lease_until and work.lease_until>timezone.now())
    stopped=work.cancel_requested or work.status in ['verified','cancelled','followup_needed']
    can_advance=bool(planning_ready and options and owner and can_control(actor,work) and not busy and not stopped and work.status not in ['blocked','owner_needed','configuration_needed','waiting_effect'])
    can_correct=not stopped and allowed(actor,work.case,'factory.start') and allowed(actor,work.case,'evidence.add') and allowed(actor,work.case,'factory.manage')
    outcome_selection_needed=bool(selection['required'] and submission and outcome and outcome.result in ['won','lost'] and not options and not stopped)
    source_followup=False
    if state and not options and not stopped and not busy:
        data=service.inputs(work)
        source_followup=bool(missing or stale or not state.get('instruction_current',True) or data['intake']!=state['intake'] or not state['native_sources'] or
            any(data[key] is None for key in ['response_evidence','public_terms']) or
            any(value is None for value in data['sources'].values()) or not data['matrix'] or
            outcome and outcome.result=='lost' and data['lessons'] is None)
        if current and not submission:
            try:rfp.current_response(work.case,current.pk)
            except (ValidationError,PermissionDenied):source_followup=True
    final_reviewed=False
    if document:
        try:controlled.validate_review(work.case,document);final_reviewed=True
        except (ValidationError,PermissionDenied):pass
    operation_followup=bool(value and final_reviewed and not submission and not options and not stopped and not busy and not source_followup)
    can_configure=allowed(actor,work.case,'policy.configure')
    can_operate_documents=allowed(actor,work.case,'document.read') and allowed(actor,work.case,'document.operate')
    held=next((job for job in jobs if job.status=='held' and job.publication.factory_work_id==work.pk),None)
    if held and held.error:finding=held.error
    changed=False
    if work.status=='verified':
        try:service.verify(work)
        except (ValidationError,PermissionDenied):changed=True
    label={'ready':'Ready to continue','waiting':'Work in progress','verified':'Verified outcome','waiting_effect':'Submission result uncertain',
        'blocked':'Source or permission needs review','configuration_needed':'Execution setup needed','owner_needed':'Execution owner needed',
        'cancelled':'Cancelled','followup_needed':'Stopped; source follow-up needed'}.get(work.status,'Review required')
    if decisions or outcome_roles:label='Awaiting human decision'
    next_action=finding or ('Continue permitted response work' if can_advance else 'Inspect current sources and recorded decisions')
    if decisions:next_action=decisions[0]['title']
    elif outcome_roles:next_action='Record the actual customer outcome'
    if outcome and outcome.result in ['pending', 'unknown'] and not disposition:
        from apps.pmo.rfp_followup import reminder_time_label
        label = 'Customer decision pending' if outcome.result == 'pending' else 'Customer outcome unconfirmed'
        due = reminder_time_label(outcome)
        next_action = ('Check customer response on ' + due) if due else 'Check for a confirmed customer response'
    if outcome and outcome.result in ['won', 'lost'] and not disposition and options:
        label = 'Customer win recorded' if outcome.result == 'won' else 'Customer loss recorded'
        next_action = 'Verify the project handoff' if outcome.result == 'won' else 'Verify the loss archive'
    if source_followup:
        label='Response inputs need follow-up';next_action='Review the response sources and required team inputs'
    elif operation_followup:
        label='Submission controls need review';next_action='Review the current submission deadline, publisher and destination controls'
    elif outcome_selection_needed:
        label='Customer outcome needs reconciliation';next_action='Identify the submitted response covered by the customer result'
    if disposition:next_action='Inspect the verified Route A handoff' if disposition.kind=='route_a' else 'Inspect the recorded loss lessons and archive'
    if changed:label='Recorded outcome needs review';next_action='Review changed source references; retain the original outcome'
    adoption=None
    if not stopped and not busy and work.policy_id and allowed(actor,work.case,'factory.manage') and allowed(actor,work.case,'policy.activate'):
        resolved=resolve('OPS.factory_rfp_execution',work.case)
        if resolved.status=='ACTIVE' and resolved.configuration.pk!=work.policy_id:
            selected=reference_values(resolved.configuration)[0]
            if selected['enabled']:
                adoption={'id':resolved.configuration.pk,'revision':resolved.configuration.revision,
                    'effective_allowance':min(work.budget_limit,selected['max_tokens'])}
    if adoption and not decisions and not outcome_roles:
        label='Execution settings changed';next_action='Review the changed execution settings before continuing'
    row={'work':work,'state':label,'next_action':next_action,'owner':actor.get_full_name() or actor.username if decisions or outcome_roles else (owner.get_full_name() or owner.username if owner else 'Unassigned'),
        'needs_me':bool(decisions or outcome_roles or can_advance or adoption or outcome_selection_needed and can_configure or source_followup and can_correct or operation_followup and (can_configure or can_correct or can_operate_documents) or held and can_operate_documents and not busy),'department_wait':bool(decisions or outcome_roles),'tasks':[],'jobs':jobs,'can_advance':can_advance,
        'can_cancel':allowed(actor,work.case,'factory.manage') and not stopped,'can_correct':can_correct,'can_reassess':False,
        'can_reconcile':can_control(actor,work) and not busy and any(j.status=='unknown' or j.status=='leased' and j.lease_until and j.lease_until<=timezone.now() for j in jobs),
        'blocker':finding or work.finding,'evidence_as_of':work.updated_at,'profile_available':value is not None,'readiness_changed':changed,
        'can_configure':can_configure,
        'can_view_outcome_settings':allowed(actor,work.case,'policy.read'),
        'adoption':adoption,
        'held_publication_needs_operator':held is not None,
        'can_review_document_operations':can_operate_documents,
        'operation_followup_needed':operation_followup,
        'source_followup_needed':source_followup,
        'outcome_selection_needed':outcome_selection_needed,
        'coordination_needed':bool(value and not planning_ready),'execution_owner_needed':owner is None and not stopped,
        'rfp':{'root':root,'response':current,'document':document,'submission':submission,'outcome':outcome,'disposition':disposition,
               'decisions':decisions,'outcome_roles':outcome_roles,'value':value,'state':state,'selection':selection,
               'submitted_versions':list(actual_submissions.filter(pk__in=[item['id'] for item in selection['inventory']['submissions']]).order_by('pk'))}}
    if work.status == 'verified' and not changed:
        row['owner'] = 'No action required'
        row['blocker'] = ''
    return decorate(actor,work,row)


@transaction.atomic
def human_command(actor,work_id,revision,case_revision,kind,target,role,verdict,evidence,note,observed_at=None,
                  selection_context=None,*,followup_on=None,award_amount=None,award_currency=None,
                  customer_expected_on=None,remind_at=None,loss_reason_key='',loss_catalog_id=None,debrief_version_id=None):
    from . import factory_rfp as service
    work=FactoryWork.objects.select_for_update().select_related('case').get(pk=work_id,definition=service.DEFINITION)
    runtime.access(actor,work.case,envelope=service.DEFINITION)
    if work.revision!=revision:raise ValidationError('STALE_VERSION: refresh the work item')
    if work.cancel_requested or work.status in ['verified','cancelled','followup_needed']:raise ValidationError('This work is stopped')
    if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: a worker owns the current action')
    case=lock_case(actor,work.case_id,'case.read',case_revision)
    current=service.response_for(work)
    if kind=='response':
        if not current or target!=current.pk:raise ValidationError('Review the exact current response')
        rfp.review(actor,case.pk,target,role,verdict,evidence,note,case.revision)
    elif kind=='commercial':
        if not current or target!=current.commercial_id:raise ValidationError('Decide the exact current response costing')
        commercial.decide_proposal(actor,case.pk,target,role,verdict,note,case.revision)
    elif kind=='document':
        intended=service.review_document(work)
        if not intended or intended.pk!=target:raise ValidationError('Review the exact response document')
        controlled.review_version(actor,case.pk,target,verdict,note,case.revision)
    elif kind=='outcome':
        submission=RFPSubmission.objects.filter(pk=target,response__rfp=service.subject(work)).first()
        if not submission:raise ValidationError('Choose an actual submission from this RFP workspace')
        rfp.outcome(actor,case.pk,submission.pk,verdict,observed_at,role,evidence,note,case.revision,
                    selection_context=selection_context,followup_on=followup_on,
                    award_amount=award_amount,award_currency=award_currency,customer_expected_on=customer_expected_on,
                    remind_at=remind_at,loss_reason_key=loss_reason_key,loss_catalog_id=loss_catalog_id,
                    debrief_version_id=debrief_version_id)
    else:raise ValidationError('Choose a current human decision')
    work.status='ready';work.finding='';work.revision+=1;work.save(update_fields=['status','finding','revision','updated_at'])
    from .factory_progress import wake_waiting
    wake_waiting(work.pk)


def detail(request,work,focus=None):
    from . import factory_rfp as service
    from .screen_focus import require_action
    runtime.access(request.user,work.case,envelope=service.DEFINITION)
    queue=request.GET.get('queue','needs_me');q=request.GET.get('q','')[:120]
    if queue not in QUEUES:queue='needs_me'
    navigation={'queue':queue,'q':q}
    actual=RFPSubmission.objects.filter(response__rfp=service.subject(work)).select_related('response','version').order_by('-pk')
    requested=request.POST.get('target') if request.method=='POST' and request.POST.get('action')=='outcome' else request.GET.get('submission')
    try:selected_id=int(requested) if requested else None
    except (ValueError,TypeError):selected_id=None
    chosen=actual.filter(pk=selected_id).first() if selected_id is not None else None
    outcome_post = request.method == 'POST' and request.POST.get('action') == 'outcome'
    outcome_variant = request.POST.get('verdict') if outcome_post else request.GET.get('outcome')
    if outcome_variant not in OUTCOME_CHOICES:
        outcome_variant = 'unknown'
    outcome_values = request.POST if outcome_post else {}
    if request.GET.get('submission') and chosen:navigation['submission']=chosen.pk
    if request.GET.get('submission_page'):navigation['submission_page']=request.GET['submission_page']
    url=request.path+'?'+urlencode(navigation)
    source=None;mappings=None
    if request.method=='POST':
        try:
            action=request.POST.get('action');revision=int(request.POST.get('revision','0'))
            require_action(work, focus, action)
            if action=='advance':runtime.advance(request.user,work.pk,revision)
            elif action=='reconcile':runtime.reconcile(request.user,work.pk,revision)
            elif action=='cancel':runtime.manage(request.user,work.pk,revision,'cancel')
            elif action=='adopt_profile':runtime.adopt_profile(request.user,work.pk,revision,int(request.POST.get('configuration','0')),request.POST.get('reason',''))
            elif action=='portal_receipt':
                from apps.pmo.rfp_portal import record
                binding=service.review_document(work)
                if binding is None or binding.pk!=int(request.POST.get('target','0')):
                    raise ValidationError('Choose the exact approved client pack.')
                record(request.user,work.case_id,binding.pk,int(request.POST.get('evidence','0')),
                       request.POST.get('note',''),int(request.POST.get('case_revision','0')))
            elif action in ['followup_draft','followup_review']:
                from apps.pmo import rfp_followup
                outcome_id=int(request.POST.get('target','0'))
                expected=int(request.POST.get('case_revision','0'))
                if action=='followup_draft':
                    rfp_followup.draft(request.user,work.case_id,outcome_id,expected)
                else:
                    rfp_followup.review(request.user,work.case_id,outcome_id,int(request.POST.get('run','0')),
                        request.POST.get('text',''),int(request.POST.get('reviewed','0')),expected)
            elif action=='followup_send':
                from apps.pmo.rfp_messages import reserve
                reserve(request.user,work.case_id,int(request.POST.get('target','0')),int(request.POST.get('reviewed','0')),
                        request.POST.get('route',''),int(request.POST.get('case_revision','0')))
            elif action=='followup_confirm':
                from apps.pmo.rfp_messages import confirm
                confirm(request.user,work.case_id,int(request.POST.get('dispatch','0')),int(request.POST.get('evidence','0')),
                        request.POST.get('reference',''),request.POST.get('delivered')=='yes',int(request.POST.get('case_revision','0')))
            elif action=='followup_lookup':
                from apps.pmo.models import RFPFollowupDispatch
                from apps.pmo.rfp_messages import run_once
                require(request.user,work.case,'rfp.submit')
                dispatch=RFPFollowupDispatch.objects.filter(pk=int(request.POST.get('dispatch','0')),actor=request.user,
                    outcome__submission__response__rfp__case=work.case).first()
                if dispatch is None:raise ValidationError('Choose your original message.')
                run_once(dispatch.pk,lookup_only=True)
            elif action=='followup_route':
                from apps.core.models import ClientContactRevision
                from apps.policy.change_drafts import draft_standard_policy
                from apps.policy.document_validators import ROLES
                contact=ClientContactRevision.objects.filter(case=work.case,purpose='project',customer='',pk=request.POST.get('contact')).first()
                role=request.POST.get('sender_role','')
                mode=request.POST.get('mode','')
                if contact is None or role not in ROLES or mode not in ['synthetic_mailbox','manual_evidence']:
                    raise ValidationError('Choose an existing project contact, sender role and delivery method.')
                resolved=resolve('D11.adapter_configuration_refs',work.case)
                if resolved.status in ['CONFLICT','AMBIGUOUS']:raise ValidationError('Resolve conflicting delivery rules before adding a route.')
                records=reference_values(resolved.configuration) if resolved.status=='ACTIVE' else []
                key='customer_followup'
                value={'kind':'rfp_followup','key':key,'mode':mode,'contact_id':contact.pk,'sender_roles':[role]}
                draft_standard_policy(request.user,work.case_id,'D11.adapter_configuration_refs',
                    [entry for entry in records if entry.get('kind')!='rfp_followup' or entry['key']!=key]+[value],
                    int(request.POST.get('evidence','0')),timezone.now())
            elif action in ['response','commercial','document','outcome']:
                observed=None;selection_context=None;followup_on=None;customer_expected_on=None;remind_at=None
                loss_reason_key='';loss_catalog_id=None;debrief_version_id=None
                if action=='outcome':
                    observed=forms.DateTimeField().clean(request.POST.get('observed_at'))
                    followup_on=forms.DateField(required=False).clean(request.POST.get('followup_on'))
                    customer_expected_on=forms.DateField(required=False).clean(request.POST.get('customer_expected_on'))
                    remind_at=forms.DateTimeField(required=False).clean(request.POST.get('remind_at'))
                    loss_reason_key=request.POST.get('loss_reason','')
                    loss_catalog_id=forms.IntegerField(min_value=1,required=False).clean(request.POST.get('loss_catalog')) if loss_reason_key else None
                    debrief_version_id=forms.IntegerField(min_value=1,required=False).clean(request.POST.get('debrief_version'))
                    if request.POST.get('selection_acknowledged')=='on':
                        selection_context={'packet':request.POST.get('selection_packet',''),'acknowledged':True}
                human_command(request.user,work.pk,revision,int(request.POST.get('case_revision','0')),action,int(request.POST.get('target','0')),
                    request.POST.get('role',''),request.POST.get('verdict',''),int(request.POST.get('evidence') or '0'),
                    request.POST.get('note',''),observed,selection_context,followup_on=followup_on,
                    award_amount=request.POST.get('award_amount') or None,award_currency=request.POST.get('award_currency') or None,
                    customer_expected_on=customer_expected_on,remind_at=remind_at,loss_reason_key=loss_reason_key,
                    loss_catalog_id=loss_catalog_id,debrief_version_id=debrief_version_id)
            elif action=='correct':
                source=SourceForm(work.case,request.POST);mappings=Mappings(request.POST,prefix='requirements',form_kwargs={'case':work.case})
                if source.is_valid() and mappings.is_valid():
                    service.correct(request.user,work.pk,revision,int(request.POST.get('case_revision','0')),payload(source,mappings),request.POST.get('reason',''))
                else:raise ValidationError('Correct the highlighted source and requirement fields')
            else:raise ValidationError('Choose an action available for this work')
            if action=='outcome' and chosen and actual.count()>1:
                navigation['submission']=chosen.pk
                url=request.path+'?'+urlencode(navigation)
            messages.success(request,'Action recorded. Inspect current decisions, output and receipts.');return redirect(url)
        except (ValidationError,ValueError,TypeError,KeyError) as exc:
            messages.error(request,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Use complete current record references.')
    work.refresh_from_db();work.case.refresh_from_db();row=presentation(request.user,work,chosen.pk if chosen else None)
    if source is None:
        value=service.inputs(work)
        initial={key:value.get(key) for key in ['response_evidence','public_terms','lessons']}
        initial.update(value.get('sources',{}));initial['revision']=work.revision
        source=SourceForm(work.case,initial=initial)
        mappings=Mappings(initial=value.get('matrix',[]),prefix='requirements',form_kwargs={'case':work.case})
    document=row['rfp']['document']
    receipts=PublicationReceipt.objects.filter(publication__version__document__case=work.case).filter(
        Q(publication__factory_work=work)|Q(publication__version=document)).order_by('pk') if document else PublicationReceipt.objects.filter(publication__factory_work=work).order_by('pk')
    activities=list(FactoryActivity.objects.filter(work=work).prefetch_related('attempts').order_by('pk'))
    from apps.agents.factory_catalogue import CATALOGUE
    for activity in activities:activity.business_title=CATALOGUE[activity.kind].title if activity.kind in CATALOGUE else 'Recorded agent work'
    evidence=public_evidence(Evidence.objects.filter(case=work.case)).order_by('-pk')
    submission_page=Paginator(actual,100).get_page(request.GET.get('submission_page','1'))
    choice_ids=[item.pk for item in submission_page]
    if chosen and chosen.pk not in choice_ids:choice_ids.append(chosen.pk)
    field=forms.ModelChoiceField(queryset=actual.filter(pk__in=choice_ids),required=True,empty_label='Choose the response actually submitted')
    field.label_from_instance=lambda item:f'Submission {item.pk} · response revision {item.response.number} · controlled version {item.version.number} · submitted {item.submitted_at:%d %b %Y %H:%M %Z}'
    pager={}
    for direction in ['previous','next']:
        if getattr(submission_page,'has_'+direction)():
            values=dict(navigation,submission_page=getattr(submission_page,direction+'_page_number')())
            pager[direction]=request.path+'?'+urlencode(values)
    outcome_links = [{'key': key, 'label': label, 'url': request.path + '?' + urlencode(dict(navigation, outcome=key)) + '#customer-outcome'}
                     for key, label in OUTCOME_CHOICES.items()]
    selected = chosen or (submission_page.object_list[0] if submission_page.paginator.count == 1 else None)
    from apps.pmo.rfp_pricing import comparison
    followup_context = {}
    if focus in (None, 'response'):
        from apps.core.models import ClientContactRevision
        from apps.pmo.models import RFPFollowupDispatch
        from apps.pmo.rfp_followup import panel as followup_panel
        from apps.pmo.rfp_messages import pre_attempt_hold
        from apps.policy.document_validators import ROLES

        followup_records = RFPFollowupDispatch.objects.filter(outcome__submission__response__rfp__case=work.case)
        messages_sent = list(followup_records.filter(actor=request.user).select_related(
            'outcome', 'receipt', 'attempt', 'mailbox', 'contact').order_by('-pk')[:10])
        for sent in messages_sent:
            if sent.route['mode'] == 'synthetic_mailbox' and not hasattr(sent, 'attempt') and not hasattr(sent, 'receipt'):
                sent.pre_attempt_hold = pre_attempt_hold(request.user, work.case, sent.pk)
        followup = followup_panel(request.user, work.case, row['rfp']['outcome'])
        can_operate_followup = allowed(request.user, work.case, 'rfp.submit')
        if can_operate_followup and followup and followup.get('reviewed'):
            followup['released'] = followup_records.filter(review=followup['reviewed'], actor=request.user).exists()
            followup['waiting_on_original'] = not followup['released'] and followup_records.filter(receipt__isnull=True).exists()
        resolved = resolve('D11.adapter_configuration_refs', work.case)
        routes = [value for value in reference_values(resolved.configuration)
                  if value.get('kind') == 'rfp_followup'] if resolved.status == 'ACTIVE' else []
        followup_context = {
            'followup': followup, 'can_operate_followup': can_operate_followup,
            'followup_routes': routes, 'followup_messages': messages_sent,
            'followup_receipt_evidence': evidence.filter(kind='rfp_followup_receipt'),
            'followup_contacts': ClientContactRevision.objects.filter(
                case=work.case, purpose='project', customer='').order_by('-number')[:20],
            'followup_sender_roles': ROLES,
        }
    portal_pack=RFPDocumentBinding.objects.filter(version=document,snapshot__route__method='manual_client_portal').first() if document else None
    from apps.pmo.rfp_answers import authorize as authorize_answers
    try:
        authorize_answers(request.user,work)
        can_review_requirement_answers=True
    except (PermissionDenied,ValidationError):
        can_review_requirement_answers=False
    final_costing = None
    if focus == 'decision':
        final_decision = next((item for item in row['rfp']['decisions']
                               if item['kind'] == 'commercial' and item['role'] == 'CEO'), None)
        if final_decision:
            from .factory_rfp_pricing import inspect
            pricing = inspect(request.user, work)
            if pricing['current'] and pricing['revision_id'] == final_decision['target']:
                final_costing = pricing
    from apps.pmo import rfp_loss
    loss_catalog, loss_reasons, debrief_choices = None, [], []
    if outcome_variant == 'lost' and row['rfp']['outcome_roles'] and focus in [None, 'response']:
        try:
            loss_catalog, loss_reasons = rfp_loss.catalog(request.user, work.case)
        except PermissionDenied:
            pass
        try:
            debrief_choices = list(rfp_loss.current_debriefs(request.user, work.case).order_by('-occurred_at', '-pk').values(
                'pk', 'meeting__reference', 'number', 'occurred_at')[:40])
        except PermissionDenied:
            pass
    return response(request,'factory/rfp_detail.html',{'case':work.case,'row':row,'queue':queue,'q':q,'source_form':source,'mappings':mappings,
        'loss_catalog':loss_catalog,'loss_reasons':loss_reasons,'debrief_choices':debrief_choices,
        'loss_debrief':rfp_loss.debrief_proof(request.user,work.case,row['rfp']['outcome']),
        'can_review_requirement_answers':can_review_requirement_answers, 'final_costing':final_costing,
        'award_comparison':comparison(work.case,row['rfp']['outcome']),
        **followup_context,
        'portal_receipt':getattr(row['rfp']['submission'],'portal_receipt',None),
        'portal_pack':portal_pack if not row['rfp']['submission'] and allowed(request.user,work.case,'rfp.submit') and allowed(request.user,work.case,'document.read') else None,
        'portal_evidence':evidence.filter(kind='rfp_portal_receipt'),
        'review_evidence':evidence,'outcome_evidence':evidence.filter(kind='rfp_outcome'),'receipts':receipts,'activities':activities,
        'submission_selector':field.widget.render('target',selected.pk if selected else None,attrs={'required':True}),
        'submission_page':submission_page,'submission_pager':pager,'focus':focus,'outcome_variant':outcome_variant,
        'outcome_values':outcome_values,'outcome_links':outcome_links})


class OutcomeSettingsForm(forms.Form):
    revision=forms.IntegerField(widget=forms.HiddenInput,min_value=1)
    base=forms.IntegerField(widget=forms.HiddenInput,min_value=0)
    method=forms.ChoiceField(required=False,label='How the current outcome owner identifies the submitted response',choices=[
        ('','Not decided'),(OUTCOME_METHOD,'Explicit selection by the currently authorised outcome owner')])
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Recorded policy decision')
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['evidence'].queryset=public_evidence(Evidence.objects.filter(case=case,kind='policy_decision')).order_by('-pk')
        self.fields['evidence'].label_from_instance=lambda evidence:evidence.source+' · version '+str(evidence.version)


class LossCatalogForm(forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput, min_value=1)
    base = forms.IntegerField(widget=forms.HiddenInput, min_value=0)
    names = forms.CharField(required=False, max_length=2100, label='Loss reasons, one per line', widget=forms.Textarea(attrs={'rows': 4}))
    evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Recorded policy decision')

    def __init__(self, case, *args, **kwargs):
        super().__init__(*args, **kwargs)
        proofs = public_evidence(case.evidence.filter(kind='policy_decision')).order_by('-pk')
        self.fields['evidence'].queryset = proofs.filter(pk__in=proofs.values('pk')[:50])
        self.fields['evidence'].label_from_instance = lambda evidence: f'{evidence.source} · version {evidence.version}'

    def clean_names(self):
        names = [line.strip() for line in self.cleaned_data['names'].splitlines() if line.strip()]
        reasons = [{'key': 'reason_' + sha256(name.encode()).hexdigest()[:32], 'label': name} for name in names]
        validate_reason_names(reasons)
        return reasons


@login_required
def outcome_configuration(request,case_id):
    from apps.pmo.rfp_loss import catalog_source_access

    case=get_object_or_404(visible_cases(request.user),pk=case_id)
    require(request.user,case,'policy.read')
    versions=Configuration.objects.filter(case=case,component=OUTCOME_COMPONENT).prefetch_related('states').order_by('-revision')
    latest=versions.first();initial={'revision':case.revision,'base':latest.pk if latest else 0}
    if latest:initial['method']=reference_values(latest)[0]['method'] or ''
    action=request.POST.get('action') if request.method == 'POST' else None
    form=OutcomeSettingsForm(case,request.POST if action=='draft' else None,initial=initial)
    catalogs=Configuration.objects.filter(case=case,component=LOSS_COMPONENT).prefetch_related('states').order_by('-revision')
    latest_catalog=catalogs.first()
    loss_initial={'revision':case.revision,'base':latest_catalog.pk if latest_catalog else 0}
    can_configure_loss=allowed(request.user,case,'policy.configure')
    if latest_catalog:
        try:
            catalog_source_access(request.user,latest_catalog)
            loss_initial['names']='\n'.join(row['label'] for row in reference_values(latest_catalog)[0]['reasons'])
        except PermissionDenied:
            can_configure_loss=False
    loss_form=LossCatalogForm(case,request.POST if action=='draft_loss_catalog' else None,initial=loss_initial,prefix='loss')
    if request.method=='POST':
        try:
            if action=='draft' and form.is_valid():
                data=form.cleaned_data
                with transaction.atomic():
                    locked=lock_case(request.user,case.pk,'policy.configure',data['revision'])
                    current=Configuration.objects.filter(case=locked,component=OUTCOME_COMPONENT).order_by('-revision').first()
                    if data['base']!=(current.pk if current else 0):raise ValidationError('STALE_VERSION: refresh the current outcome settings')
                    draft_operator_policy(request.user,locked.pk,OUTCOME_COMPONENT,{'method':data['method'] or None},data['evidence'].pk,timezone.now())
                return redirect(request.path)
            elif action=='draft_loss_catalog' and loss_form.is_valid():
                if not can_configure_loss:
                    raise PermissionDenied('Current authority over the loss catalog is required.')
                data=loss_form.cleaned_data
                with transaction.atomic():
                    locked=lock_case(request.user,case.pk,'policy.configure',data['revision'])
                    current=catalogs.only('pk').first()
                    if data['base']!=(current.pk if current else 0):
                        raise ValidationError('The loss reasons changed. Reload and review the current list.')
                    draft_operator_policy(request.user,locked.pk,LOSS_COMPONENT,{'reasons':data['names']},data['evidence'].pk,timezone.now())
                return redirect(request.path)
            elif action in ['validated','active','revoked']:
                try:configuration_id=int(request.POST.get('configuration',''))
                except (ValueError,TypeError):raise ValidationError('Choose an exact settings revision') from None
                configuration=get_object_or_404(Configuration.objects.filter(case=case,component__in=[OUTCOME_COMPONENT,LOSS_COMPONENT]),pk=configuration_id)
                if configuration.component==LOSS_COMPONENT:catalog_source_access(request.user,configuration)
                transition(request.user,configuration.pk,action);return redirect(request.path)
            elif action not in ['draft','draft_loss_catalog']:raise ValidationError('Choose a current settings action')
        except ValidationError as exc:
            if loss_form.is_bound:loss_form.add_error(None,exc)
            elif form.is_bound:form.add_error(None,exc)
            else:messages.error(request,'; '.join(exc.messages))
    rows=list(versions)
    catalog_rows=list(catalogs.filter(scope_application__isnull=True)[:30])
    for version in [*rows, *catalog_rows]:
        state=max(version.states.all(),key=lambda item:item.pk).state
        value=reference_values(version)[0]
        if version.component==LOSS_COMPONENT:
            version.reason_names=[reason['label'] for reason in value['reasons']]
        else:
            version.method_label='Explicit selection by the currently authorised outcome owner' if value.get('method')==OUTCOME_METHOD else 'Not decided'
        version.can_validate=state=='draft' and allowed(request.user,case,'policy.configure')
        version.can_activate=state=='validated' and allowed(request.user,case,'policy.activate')
        version.can_revoke=state=='active' and allowed(request.user,case,'policy.activate')
    return response(request,'factory/rfp_outcome_settings.html',{'case':case,'form':form,'versions':rows,
        'loss_form':loss_form,'catalogs':catalog_rows,'can_configure_loss':can_configure_loss,
        'can_configure':allowed(request.user,case,'policy.configure')})
