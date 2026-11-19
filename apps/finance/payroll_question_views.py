from uuid import uuid4
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db.models import Q
from django.shortcuts import render,redirect,get_object_or_404
from django.views.decorators.http import require_http_methods

from adapters.payroll_questions import TOPICS,REPLIES
from apps.core.views import accessible_case
from apps.core.models import Evidence
from apps.identity.services import require
from apps.policy.models import Configuration
from apps.policy.payroll_validators import QUESTION_ROUTE
from apps.policy.payroll_drafts import draft_payroll_policy
from apps.policy.services import reference_values
from apps.core.services import lock_case
from django.db import transaction
from django.utils import timezone
from . import payroll_questions as domain,payroll as native
from .payroll_models import PayrollPublication
from .payroll_question_models import PayrollReportQuestion


class QuestionForm(forms.Form):
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    publication=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    operation_key=forms.UUIDField(widget=forms.HiddenInput)
    topic=forms.ChoiceField(label='What would you like HR to check?',choices=list(TOPICS.items()))


class ActionForm(forms.Form):
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    head=forms.IntegerField(min_value=0,widget=forms.HiddenInput)
    question=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    action=forms.ChoiceField(choices=[(key,key) for key in ['dispatched','answered','received','cancelled']])
    reply=forms.ChoiceField(required=False,choices=[('','Choose a response'),*REPLIES.items()])


@login_required
@require_http_methods(['GET','HEAD','POST'])
@transaction.atomic
def desk(request,case_id):
    case=accessible_case(request.user,case_id);create_form=None;held=None
    if request.method=='POST':
        form=QuestionForm(request.POST) if request.POST.get('action')=='record' else ActionForm(request.POST)
        if form.is_valid() and not (set(request.POST)-set(form.fields)-{'csrfmiddlewaretoken','action'}):
            value=form.cleaned_data
            try:
                if request.POST.get('action')=='record':
                    domain.record(request.user,case.pk,value['publication'],value['topic'],value['operation_key'],value['revision'])
                    messages.success(request,'Question recorded. Review it before sending it to HR.')
                else:
                    domain.advance(request.user,case.pk,value['question'],value['action'],value['head'],value['revision'],value['reply'])
                    messages.success(request,'Question history updated.')
                return redirect('payroll_questions',case_id=case.pk)
            except (PermissionDenied,ValidationError):held='The report, question or authority changed. Review the current information.'
        else:held='Choose a displayed question and action.'
    publication_id=request.GET.get('report')
    if publication_id and publication_id.isascii() and publication_id.isdigit():
        publication=get_object_or_404(PayrollPublication.objects.defer('payload').select_related('request'),
                                      request__case=case,pk=publication_id)
        try:
            native.read_publication(request.user,publication.pk)
            create_form=QuestionForm(initial={'revision':case.revision,'publication':publication.pk,'operation_key':uuid4()})
        except (PermissionDenied,ValidationError):held='This report needs current recipient and source checks before a question can be recorded.'
    selected=PayrollReportQuestion.objects.select_related('case','actor').filter(case=case).filter(
        Q(actor=request.user)|Q(events__kind='dispatched',events__data__owner_id=request.user.pk)).distinct().order_by('-pk')
    page=request.GET.get('page','1')
    number=min(int(page),10000) if page.isascii() and page.isdigit() else 1
    offset=max(number-1,0)*25;items=list(selected[offset:offset+26]);has_next=len(items)>25;cards=[]
    reader=domain.Reader(request.user,case)
    for item in items[:25]:
        try:cards.append(domain.projection(request.user,item,reader))
        except (PermissionDenied,ValidationError):continue
    response=render(request,'finance/payroll_questions.html',{'case':case,'create_form':create_form,
        'cards':cards,'held':held,'reply_choices':REPLIES.items(),'has_next':has_next,'page':number,
        'next_page':number+1,'previous_page':number-1})
    response['Cache-Control']='no-store';return response


class RouteForm(forms.Form):
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    head=forms.IntegerField(min_value=0,widget=forms.HiddenInput)
    owner_id=forms.TypedChoiceField(required=False,coerce=int,empty_value=None,label='HR response owner',
        help_text='Choose a currently authorised HR respondent, or leave this undecided.')
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Recorded routing decision')

    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        from apps.policy.services import active_component
        from apps.policy.hrfinance_validators import AUTHORITY
        candidates=[]
        try:
            rules=reference_values(active_component(AUTHORITY,case))[0]
            ids=[row['user_id'] for row in rules['assignments'] if row['purpose']=='respond']
            for person in get_user_model().objects.filter(pk__in=ids,is_active=True).only('pk','username','first_name','last_name').order_by('pk')[:100]:
                try:domain.owner_access(person,case)
                except (PermissionDenied,ValidationError):continue
                candidates.append((person.pk,person.get_full_name() or person.username))
        except (PermissionDenied,ValidationError):pass
        self.fields['owner_id'].choices=[('','Not decided'),*candidates]
        proofs=Evidence.objects.filter(case=case,kind='policy_decision').order_by('-pk').values('pk')[:50]
        self.fields['evidence'].queryset=Evidence.objects.defer('body').filter(pk__in=proofs).order_by('-pk')


@login_required
@require_http_methods(['GET','HEAD','POST'])
def routing(request,case_id):
    case=accessible_case(request.user,case_id)
    for action in ['policy.read','policy.configure']:require(request.user,case,action)
    latest=Configuration.objects.filter(case=case,component=QUESTION_ROUTE).order_by('-revision').first()
    initial={'revision':case.revision,'head':latest.pk if latest else 0,'owner_id':None}
    if latest:
        from apps.policy.impact import configuration
        reference=configuration(request.user,case.pk,latest.pk)
        initial['owner_id']=reference_values(reference)[0]['owner_id']
    form=RouteForm(case,request.POST if request.method=='POST' else None,initial=initial)
    if request.method=='POST' and form.is_valid():
        try:
            if set(request.POST)-set(form.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Use the displayed route review')
            with transaction.atomic():
                current=lock_case(request.user,case.pk,'policy.configure',form.cleaned_data['revision'])
                newest=Configuration.objects.filter(case=current,component=QUESTION_ROUTE).order_by('-revision').first()
                if (newest.pk if newest else 0)!=form.cleaned_data['head']:raise ValidationError('A newer routing draft exists')
                draft_payroll_policy(request.user,current.pk,QUESTION_ROUTE,{
                    'owner_id':form.cleaned_data['owner_id'],'action':'answer_aggregate_question',
                    'disclosure':'report_identity_and_topic_only','reply':'closed_codes_only'},
                    form.cleaned_data['evidence'].pk,timezone.now())
            messages.success(request,'HR question routing draft saved. Validation and activation remain separate reviews.')
            return redirect('payroll_question_routing',case_id=case.pk)
        except (PermissionDenied,ValidationError):form.add_error(None,'Current routing or authority changed. Review before saving.')
    response=render(request,'finance/payroll_question_routing.html',{'case':case,'form':form,'latest':latest})
    response['Cache-Control']='no-store';return response
