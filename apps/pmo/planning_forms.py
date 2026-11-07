"""Bounded human selectors; all authority and current-source checks stay in services."""
from django import forms
from django.contrib.auth import get_user_model
from django.forms import formset_factory
from apps.core.evidence_access import public_evidence
from apps.policy.planning_validators import TEAMS,STATES
from adapters.planning_packet import SOURCE_KINDS
from .models import ActionItem
from .planning_sources import FIELDS

def capture_forms(case,data=None,initial=None,predecessor=None):
    initial=initial or {}
    sources=public_evidence(case.evidence.all()).exclude(source='psl:planning-request-subject-v1').order_by('-pk')
    people=get_user_model().objects.filter(is_active=True,grant__case=case,grant__active=True,grant__action='planning.participate').distinct().order_by('username','pk')
    class Sources(forms.Form):
        predecessor=forms.IntegerField(min_value=1,required=False,widget=forms.HiddenInput)
    labels={'prd_id':'Product PRD / requirements source','scope_id':'Scope baseline source','engineering_estimate_id':'Engineering estimate source','security_estimate_id':'Security estimate source'}
    for key,kinds in SOURCE_KINDS.items():Sources.base_fields[key]=forms.ModelChoiceField(sources.filter(kind__in=kinds),required=False,empty_label='Unknown / not supplied',label=labels[key])
    class Stakeholder(forms.Form):
        team=forms.ChoiceField(choices=[(t,t) for t in TEAMS],widget=forms.HiddenInput)
        contact_id=forms.ModelChoiceField(people,required=False,empty_label='Contact unknown / not recorded',label='Current case participant')
        evidence_id=forms.ModelChoiceField(sources,required=False,empty_label='Supporting source unknown',label='Contact / team evidence')
    class Question(forms.Form):
        key=forms.RegexField(regex=r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}\Z',max_length=100,label='Question key')
        detail=forms.CharField(max_length=1000,widget=forms.Textarea(attrs={'rows':2}),label='Question or clarification')
        state=forms.ChoiceField(choices=[('','Choose recorded state')]+[(s,s) for s in STATES])
        action_id=forms.ModelChoiceField(ActionItem.objects.filter(case=case,current__isnull=False).order_by('reference','pk'),required=False,empty_label='No action linked / unknown',label='Existing case action')
        evidence_id=forms.ModelChoiceField(sources,required=False,empty_label='Supporting source unknown',label='Question / disposition evidence')
    class Correlation(forms.Form):
        key=forms.RegexField(regex=r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}\Z',max_length=100,label='Correlation key')
        source_field=forms.ChoiceField(choices=[(k,labels[k]) for k in FIELDS],label='Source type')
        source_id=forms.ModelChoiceField(sources.filter(kind__in=set(k for f in FIELDS for k in SOURCE_KINDS[f])),label='Exact source document')
        document_version=forms.CharField(required=False,max_length=100,label='Version declared by this document (not compared to other documents)')
        target_prd_id=forms.ModelChoiceField(sources.filter(kind__in=SOURCE_KINDS['prd_id']),required=False,empty_label='Target PRD unknown',label='Exact PRD targeted by the source')
        target_scope_id=forms.ModelChoiceField(sources.filter(kind__in=SOURCE_KINDS['scope_id']),required=False,empty_label='Target scope unknown',label='Exact scope targeted by the source')
        evidence_id=forms.ModelChoiceField(sources,required=False,empty_label='Interpretation evidence unknown',label='Source-backed interpretation evidence')
        state=forms.ChoiceField(choices=[('current','Declared current source'),('conflicting','Conflicting source, preserve for clarification'),('excluded','Retained source excluded by exact owner response')])
        detail=forms.CharField(max_length=500,widget=forms.Textarea(attrs={'rows':2}),label='Declared assumptions or exact conflict')
        resolution_id=forms.IntegerField(required=False,min_value=1,label='Native owner response ID (required for exclusion)')
    Correlations=formset_factory(Correlation,extra=1,max_num=50,validate_max=True,absolute_max=50)
    Teams=formset_factory(Stakeholder,extra=0,min_num=4,max_num=4,validate_min=True,validate_max=True,absolute_max=4)
    Questions=formset_factory(Question,extra=1,max_num=100,validate_max=True,absolute_max=100,can_delete=True)
    current={row['team']:row for row in initial.get('stakeholders',[])}
    return (Sources(data,prefix='packet',initial={'predecessor':predecessor,**{k:initial.get(k) for k in SOURCE_KINDS}}),
        Teams(data,prefix='stakeholders',initial=[current.get(team,{'team':team,'contact_id':None,'evidence_id':None}) for team in TEAMS]),
        Questions(data,prefix='questions',initial=initial.get('questions',[])),
        Correlations(data,prefix='correlations',initial=initial.get('source_correlations',[])))

def payload(sources,teams,questions,correlations):
    identity=lambda obj:obj.pk if obj is not None else None
    value={key:identity(sources.cleaned_data[key]) for key in SOURCE_KINDS}
    value['stakeholders']=[{'team':f.cleaned_data['team'],'contact_id':identity(f.cleaned_data['contact_id']),'evidence_id':identity(f.cleaned_data['evidence_id'])} for f in teams]
    value['questions']=[]
    for form in questions:
        row=form.cleaned_data
        if not row or row.get('DELETE'):continue
        value['questions'].append({**{k:row[k] for k in ['key','detail','state']},'action_id':identity(row['action_id']),'evidence_id':identity(row['evidence_id'])})
    value['source_correlations']=[]
    for form in correlations:
        row=form.cleaned_data
        if not row:continue
        value['source_correlations'].append({**{k:row[k] for k in ['key','source_field','state','detail','resolution_id']},
            **{k:identity(row[k]) for k in ['source_id','target_prd_id','target_scope_id','evidence_id']},'document_version':row['document_version'] or None})
    return value
