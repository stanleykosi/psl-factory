"""Connected closure preparation over native prerequisites; no inferred decision/effect."""
from urllib.parse import urlencode
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import F
from django.shortcuts import render,redirect
from django.http import Http404
from django.views.decorators.http import require_http_methods
from django.utils import timezone,formats
from django.utils.dateparse import parse_datetime
from apps.core.views import accessible_case
from apps.core.evidence_access import public_evidence
from apps.core.models import Evidence
from apps.core.workbench import granted
from apps.identity.services import require
from apps.agents.delivery import investigate_delivery
from apps.agents.models import AgentRun
from adapters.delivery import LocalDeliveryAdapter
from .delivery import dossier_for
from .models import MeetingVersion


class SelectionForm(forms.Form):
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['retrospective_id']=forms.ModelChoiceField(required=False,label='Recorded retrospective',empty_label='Not yet selected',
            queryset=MeetingVersion.objects.filter(meeting__case=case,kind='retrospective',meeting__current_id=F('pk')).order_by('-occurred_at'))
        self.fields['retrospective_id'].label_from_instance=lambda m:'Retrospective · '+formats.date_format(timezone.localtime(m.occurred_at),'d M Y, H:i T')+f' · revision {m.number}'
        self.fields['report_evidence_id']=forms.ModelChoiceField(required=False,label='PM closure report',empty_label='Not yet provided',
            queryset=public_evidence(Evidence.objects.filter(case=case,kind='closure_report')).order_by('-version'))
        self.fields['report_evidence_id'].label_from_instance=lambda e:f'Closure report · version {e.version} · reference {e.pk}'

    def selected(self):return {key:self.cleaned_data[key].pk if self.cleaned_data[key] else None for key in self.fields}


@login_required
@require_http_methods(['GET','HEAD','POST'])
def preparation(request,case_id,dossier_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'delivery.read')
    try:d=dossier_for(case,dossier_id,current=False)
    except ValidationError:raise Http404 from None
    form=SelectionForm(case,request.POST if request.method=='POST' else request.GET)
    selected={'retrospective_id':None,'report_evidence_id':None}
    valid=form.is_valid()
    if valid:selected=form.selected()
    if request.method=='POST':
        operation=request.POST.get('action')
        if operation=='investigate':require(request.user,case,'agent.delivery')
        if operation not in ['check','investigate']:form.add_error(None,'Choose an available preparation action.')
        elif valid:
            try:
                if operation=='investigate':
                    investigate_delivery(request.user,case.pk,d.pk,int(request.POST.get('revision','0')),selected)
                    messages.success(request,'Current closure requirements investigated. Decisions and completion remain separate.')
                query=urlencode({key:value for key,value in selected.items() if value is not None})
                return redirect(request.path+('?' + query if query else ''))
            except ValidationError as exc:form.add_error(None,'; '.join(exc.messages))
            except ValueError:form.add_error(None,'Refresh this page before requesting investigation.')
    report=LocalDeliveryAdapter().read_closure(d,selected)
    runs=AgentRun.objects.filter(case=case,provider='deterministic-delivery-investigation-v1',result__dossier_id=d.pk).order_by('-pk')[:5]
    actions={'can_investigate':granted(request.user,['delivery.read','agent.delivery']).filter(pk=case.pk).exists(),
        'can_start_closure':granted(request.user,['factory.start','delivery.read','evidence.add']).filter(pk=case.pk).exists() and not d.records.filter(kind='closure').exists(),
        'can_record_meeting':granted(request.user,['meeting.read','meeting.record']).filter(pk=case.pk).exists(),
        'can_open_delivery':granted(request.user,['delivery.read','delivery.manage']).filter(pk=case.pk).exists()}
    response=render(request,'pmo/closure_preparation.html',{'case':case,'dossier':d,'form':form,'report':report,'checked_at':parse_datetime(report['as_of']),'runs':runs,**actions})
    response['Cache-Control']='no-store';return response
