from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import render,redirect
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.policy.change_drafts import draft_standard_policy
from apps.agents.rfp import investigate_rfp
from apps.agents.models import AgentRun
from . import rfp,rfp_documents
from .models import RFPCase,RFPResponse,RFPSubmission,RFPOutcome,RFPDisposition
from .rfp_forms import forms_for

@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'rfp.read');forms=forms_for(case,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            command=next((x for x in forms if x['action']==request.POST.get('action')),None)
            if not command or not command['form'].is_valid():raise ValidationError(command['form'].errors.as_text() if command else 'Select a supported RFP action')
            d=command['form'].cleaned_data;a=request.user;c=case.pk;v=d['revision'];action=d['action']
            if action=='intake':rfp.intake(a,c,d['reference'],d['evidence'].pk,d['received_at'],d['deadline_status'],d['deadline_at'],d['deadline_evidence'].pk if d['deadline_evidence'] else None,d['note'],v)
            elif action=='assign':rfp.assign(a,c,d['pm'],d['role'],d['evidence'].pk,d['note'],v)
            elif action=='contribute':rfp.contribute(a,c,d['team'],d['evidence'].pk,v)
            elif action=='prepare':rfp.prepare_response(a,c,d['evidence'].pk,d['matrix'],{k:d[k].pk for k in ['requirements','plan','costing']},v,public_terms_id=d['public_terms'].pk)
            elif action=='review':rfp.review(a,c,d['response'].pk,d['role'],d['verdict'],d['evidence'].pk,d['note'],v)
            elif action=='draft':rfp_documents.draft(a,c,d['response'].pk,d['template'].pk,d['route_key'],v)
            elif action=='capture':rfp_documents.capture_submission(a,c,d['version'].version_id,v)
            elif action=='outcome':rfp.outcome(a,c,d['submission'].pk,d['result'],d['observed_at'],d['role'],d['evidence'].pk,d['note'],v)
            elif action=='dispose':rfp.dispose(a,c,d['outcome'].pk,d['lessons'].pk if d['lessons'] else None,v)
            elif action=='policy':draft_standard_policy(a,c,d['component'],d['content'],d['evidence'].pk,d['effective_from'])
            elif action=='investigate':investigate_rfp(a,c,v)
            messages.success(request,'RFP history updated');return redirect('rfp',case_id=c)
        except (ValidationError,ValueError,KeyError) as exc:messages.error(request,str(exc));case.refresh_from_db()
    r=RFPCase.objects.filter(case=case).first()
    return render(request,'pmo/rfp.html',{'case':case,'rfp':r,'commands':forms,'responses':RFPResponse.objects.filter(rfp=r).order_by('-pk'),
        'submissions':RFPSubmission.objects.filter(response__rfp=r),'outcomes':RFPOutcome.objects.filter(submission__response__rfp=r),
        'disposition':RFPDisposition.objects.filter(rfp=r).first(),'runs':AgentRun.objects.filter(case=case,provider='deterministic-rfp-investigation-v1').order_by('-pk')[:5]})
