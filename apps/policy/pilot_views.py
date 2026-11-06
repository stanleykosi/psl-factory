import json
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.http import JsonResponse
from django.shortcuts import render,redirect
from apps.identity.models import Grant
from . import pilot,pilot_validators
from .models import PilotContract,PilotObservation


class SelectionForm(forms.Form):
    predecessor=forms.IntegerField(required=False,widget=forms.HiddenInput)
    process_ids=forms.MultipleChoiceField(choices=[])
    operations=forms.MultipleChoiceField(choices=[])
    participants=forms.MultipleChoiceField(choices=[])
    actions=forms.MultipleChoiceField(choices=[],label='Selected actions to check for each participant')
    integrations=forms.CharField(required=False,max_length=200,label='Integration contract IDs (comma separated)')
    jobs=forms.CharField(required=False,max_length=1000,label='Selected jobs: family:id, separated by commas')
    acceptance_reviews=forms.MultipleChoiceField(required=False,choices=[],label='Existing source-owned AF13 acceptance decisions')

    def __init__(self,actor,case,*args,**kwargs):
        from pathlib import Path
        from django.conf import settings
        super().__init__(*args,**kwargs)
        rows=json.loads((settings.BASE_DIR/'contracts/process-map.json').read_text(encoding='utf-8'))['rows']
        self.fields['process_ids'].choices=[(r['id'],r['id']) for r in rows]
        self.fields['operations'].choices=[(s,s) for s in pilot_validators.operations()]
        users=Grant.objects.filter(case=case,action='case.read').values_list('user_id',flat=True).distinct()
        self.fields['participants'].choices=[(str(pk),'Participant #'+str(pk)) for pk in users]
        self.fields['actions'].choices=[(s,s) for s in sorted(set(pilot_validators.ACTIONS))]
        self.case=case
        if Grant.objects.filter(case=case,user=actor,action='validation.export',active=True).exists():
            from apps.documents.validation_models import ValidationReview
            from apps.documents.validation import _private_access
            decisions=[]
            for review in ValidationReview.objects.filter(package__case=case,kind='acceptance').select_related('package'):
                try:_private_access(actor,review.package)
                except PermissionDenied:continue
                decisions.append((str(review.pk),'AF13 review #'+str(review.pk)))
            self.fields['acceptance_reviews'].choices=decisions

    def clean(self):
        v=super().clean()
        if self.errors:return v
        try:
            integrations=[int(x.strip()) for x in v['integrations'].split(',') if x.strip()]
            jobs=[]
            for item in v['jobs'].split(','):
                if item.strip():
                    family,pk=item.strip().split(':');jobs.append({'family':family,'id':int(pk)})
            v['payload']={'format':'psl.pilot-contract/v1','case_id':str(self.case.pk),'read_only':True,
                'process_ids':v['process_ids'],'operations':v['operations'],
                'participants':[{'user_id':int(pk),'actions':v['actions']} for pk in v['participants']],
                'integrations':integrations,'jobs':jobs}
            if v['acceptance_reviews']:
                v['payload'].update(format='psl.pilot-contract/v2',acceptance_reviews=[int(pk) for pk in v['acceptance_reviews']])
            pilot_validators.validate(self.case,v['payload'])
        except (ValueError,ValidationError):raise forms.ValidationError('Use valid bounded selected IDs and family:id jobs; arbitrary URLs and effect instructions are not accepted')
        return v


@login_required
def workbench(request,case_id):
    case=pilot.context(request.user,case_id)
    latest=PilotContract.objects.filter(case=case).order_by('-version').first()
    form=SelectionForm(request.user,case,request.POST if request.method=='POST' else None,initial={'predecessor':latest.pk if latest else None})
    error=None
    if request.method=='POST' and form.is_valid():
        try:
            row=pilot.configure(request.user,case_id,form.cleaned_data['payload'],form.cleaned_data['predecessor'])
            return redirect('pilot_contract',case_id=case_id,pk=row.pk)
        except ValidationError as exc:error=str(exc)
    response=render(request,'pilot_selection.html',{'case':case,'form':form,'error':error,'latest':latest})
    response['Cache-Control']='no-store';return response


@login_required
def contract(request,case_id,pk):
    case,row=pilot.contract(request.user,case_id,pk)
    current=pilot.observation(request.user,case,row.payload,row);error=None
    if request.method=='POST':
        try:
            result=pilot.capture(request.user,case_id,pk)
            return redirect('pilot_observation',case_id=case_id,pk=result.pk)
        except ValidationError as exc:error=str(exc)
    records=PilotObservation.objects.filter(contract=row).order_by('-pk')[:30]
    response=render(request,'pilot_contract.html',{'case':case,'contract':row,'current':current,'records':records,'error':error})
    response['Cache-Control']='no-store';return response


@login_required
def report(request,case_id,pk):
    from apps.agents.pilot import investigate
    case=pilot.context(request.user,case_id)
    value=pilot.inspect(request.user,case_id,pk)
    if request.GET.get('export')=='1':
        return JsonResponse(value,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
            'Content-Disposition':f'attachment; filename="pilot-preflight-{pk}.json"'})
    agent=None
    if Grant.objects.filter(case=case,user=request.user,action='agent.pilot',active=True).exists():agent=investigate(request.user,case_id,pk)
    response=render(request,'pilot_observation.html',{'case':case,'report':value,'agent':agent})
    response['Cache-Control']='no-store';return response
