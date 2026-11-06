from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import render
from . import workbench

class SearchForm(forms.Form):
    q=forms.CharField(max_length=120,required=False,label='Search workspaces',widget=forms.TextInput(attrs={'placeholder':'Search workspaces…','aria-label':'Search workspaces'}))
    tenant=forms.CharField(max_length=100,required=False,label='Organization')
    kind=forms.ChoiceField(required=False,label='Workspace type',choices=[('','All workspaces'),('project','Projects'),('support','Customer support')],widget=forms.Select(attrs={'aria-label':'Workspace type'}))
    cursor=forms.CharField(max_length=4096,required=False,widget=forms.HiddenInput,error_messages={'max_length':'This page link is invalid. Restart the search.'})
    area=forms.ChoiceField(required=False,choices=[('','All areas'),('finance','Finance')],widget=forms.HiddenInput)

@login_required
def home(request):
    form=SearchForm(request.GET);result={'cases':[],'next_cursor':None,'filters':{'q':'','tenant':'','kind':''}}
    if form.is_valid():
        try:result=workbench.discover(request.user,**form.cleaned_data)
        except ValidationError as exc:form.add_error(None,str(exc))
    response=render(request,'home.html',{'search_form':form,'sample_mode':bool(result['cases']) and all(c.synthetic for c in result['cases']),**result});response['Cache-Control']='no-store';return response

@login_required
def inbox(request):
    result=workbench.work(request.user)
    response=render(request,'workbench_inbox.html',{'sample_mode':bool(result['rows']) and all(row['synthetic'] for row in result['rows']),**result});response['Cache-Control']='no-store';return response
