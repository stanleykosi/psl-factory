from .change_impacts import assessment_form, execution_form
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.documents.models import Template, PublicationReceipt
from apps.agents.commercial import investigate_proposal
from apps.agents.models import AgentRun
from .models import CommercialCase, CommercialRevision, ChangeRequest, ChangeVersion, ChangeAuthorization, ChangeDocumentBinding
from .change_execution import record_execution, draft_change_document, close_change
from .commercial_forms import ProposalForm, CommercialDecisionForm
from .commercial import SOURCE_KINDS, propose, decide_proposal, draft_submission, capture_response, adopt_signed
from .changes import log_change, assess_change, decide_change, authorize_change, CONTRIBUTORS, DECISION_ROLES


@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'commercial.read')
    form=ProposalForm(case=case,auto_id='proposal_%s')
    if request.method=='POST':
        try:
            p=request.POST;expected=int(p['revision']);action=p['action']
            if action=='propose':
                form=ProposalForm(p,case=case,auto_id='proposal_%s')
                if not form.is_valid():raise ValidationError(form.errors.as_text())
                d=form.cleaned_data
                propose(request.user,case.pk,{k:d[k].pk for k in SOURCE_KINDS},d['context'].pk,d['reason'],expected,d['reuse'])
            elif action=='decide':
                f=CommercialDecisionForm(p)
                if not f.is_valid():raise ValidationError(f.errors.as_text())
                d=f.cleaned_data;decide_proposal(request.user,case.pk,int(p['proposal']),d['role'],d['verdict'],d['note'],expected,d['delegated'])
            elif action=='draft':draft_submission(request.user,case.pk,int(p['proposal']),int(p['template']),expected)
            elif action=='response':capture_response(request.user,case.pk,int(p['proposal']),int(p['receipt']),p['kind'],int(p['evidence']),p['note'],expected,**execution_form(p))
            elif action=='adopt':adopt_signed(request.user,case.pk,int(p['proposal']),int(p['response']),expected)
            elif action=='investigate':investigate_proposal(request.user,case.pk,int(p['proposal']),expected)
            else:raise ValidationError('Unsupported commercial command')
            messages.success(request,'Commercial history updated')
            return redirect('commercial',case_id=case.pk)
        except (ValidationError,ValueError,KeyError) as exc:
            messages.error(request,str(exc));case.refresh_from_db()
    dossier=CommercialCase.objects.filter(case=case).select_related('current').first()
    from .models import RFPCase,RFPDisposition,RFPResponse
    rfp_workspace=RFPCase.objects.filter(case=case).first()
    converted=bool(rfp_workspace and RFPDisposition.objects.filter(rfp=rfp_workspace,kind='route_a').exists())
    return render(request,'pmo/commercial.html',{'case':case,'form':form,'dossier':dossier,'rfp_workspace':rfp_workspace,'rfp_converted':converted,
        'is_rfp_proposal':bool(dossier and RFPResponse.objects.filter(commercial_id=dossier.current_id).exists()),
        'revisions':CommercialRevision.objects.filter(dossier__case=case).order_by('-number'),
        'decision_form':CommercialDecisionForm(auto_id='decision_%s'),
        'templates':Template.objects.filter(case=case,definition__document_type='sow'),
        'receipts':PublicationReceipt.objects.filter(publication__version__commercialdocumentbinding__revision__dossier__case=case),
        'evidence':case.evidence.filter(kind__in=['client_feedback','signature']),
        'runs':AgentRun.objects.filter(case=case,provider='deterministic-commercial-investigation-v1').order_by('-pk')[:10]})


@login_required
def changes(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'change.read')
    from .standard_changes import preapprove, bind_standard, catalogue
    from .standard_forms import StandardPolicyForm
    from apps.policy.change_drafts import draft_standard_policy
    from apps.agents.standard_changes import investigate_standard
    from .models import StandardPreapproval, StandardBinding
    policy_form=StandardPolicyForm(auto_id='standard_policy_%s')
    policy_form.fields['evidence'].queryset=case.evidence.filter(kind='policy_decision')
    if request.method=='POST':
        try:
            p=request.POST;expected=int(p['revision']);action=p['action']
            if action=='log':log_change(request.user,case.pk,p['reference'],p['category'],p['module'],p['description'],p['reason'],int(p['evidence']),expected,int(p['incident']) if p.get('incident') else None)
            elif action=='assess':
                def flag(key):
                    if p.get(key) not in ['unknown','true','false']:raise ValidationError('Select true, false or unknown')
                    return {'unknown':None,'true':True,'false':False}[p[key]]
                assess_change(request.user,case.pk,int(p['version']),p['contributor'],flag('cost_impact'),flag('timeline_impact'),flag('client_facing'),int(p['evidence']),p['note'],expected,**assessment_form(p))
            elif action=='decide':decide_change(request.user,case.pk,int(p['version']),p['role'],p['verdict'],int(p['evidence']),p['note'],expected)
            elif action=='authorize':authorize_change(request.user,case.pk,int(p['version']),int(p['commercial']) if p.get('commercial') else None,expected)
            elif action=='execution':record_execution(request.user,case.pk,int(p['authorization']),p['kind'],int(p['evidence']),p['note'],expected,**execution_form(p))
            elif action=='draft_change':draft_change_document(request.user,case.pk,int(p['authorization']),int(p['template']),p['purpose'],expected,p.get('audience','client'))
            elif action=='close':close_change(request.user,case.pk,int(p['authorization']),int(p['receipt']),int(p['pm_signature']),int(p['client_signature']),p['note'],expected)
            elif action=='standard_approve':preapprove(request.user,case.pk,p['catalogue_key'],p['role'],p['verdict'],int(p['evidence']),p['note'],expected)
            elif action=='standard_bind':bind_standard(request.user,case.pk,int(p['version']),p['catalogue_key'],int(p['evidence']),p['note'],expected)
            elif action=='standard_investigate':investigate_standard(request.user,case.pk,int(p['version']),expected)
            elif action=='standard_policy':
                policy_form=StandardPolicyForm(p,auto_id='standard_policy_%s')
                policy_form.fields['evidence'].queryset=case.evidence.filter(kind='policy_decision')
                if not policy_form.is_valid():raise ValidationError(policy_form.errors.as_text())
                d=policy_form.cleaned_data
                draft_standard_policy(request.user,case.pk,d['component'],d['value'],d['evidence'].pk,d['effective_from'])
            else:raise ValidationError('Unsupported change command')
            messages.success(request,'Change history updated')
            return redirect('changes',case_id=case.pk)
        except (ValidationError,ValueError,KeyError) as exc:
            messages.error(request,str(exc));case.refresh_from_db()
    versions=ChangeVersion.objects.filter(change__case=case).order_by('-pk')
    try:entries,gates,policies=catalogue(case);catalogue_error=''
    except ValidationError as exc:entries={};gates=[];policies={};catalogue_error=str(exc)
    return render(request,'pmo/changes.html',{'case':case,'versions':versions,'evidence':case.evidence.order_by('-pk'),
        'standard_entries':entries,'standard_gates':gates,'standard_policies':policies,'standard_error':catalogue_error,
        'standard_policy_form':policy_form,'preapprovals':StandardPreapproval.objects.filter(case=case).order_by('-pk')[:100],
        'standard_bindings':StandardBinding.objects.filter(version__change__case=case).order_by('-pk')[:100],
        'standard_runs':AgentRun.objects.filter(case=case,provider='deterministic-standard-investigation-v1').order_by('-pk')[:10],
        'contributors':CONTRIBUTORS,'roles':DECISION_ROLES,'commercial':CommercialRevision.objects.filter(dossier__case=case),
        'authorizations':ChangeAuthorization.objects.filter(version__change__case=case),
        'templates':Template.objects.filter(case=case,definition__document_type__in=['status_report','project_artifact']),
        'change_receipts':PublicationReceipt.objects.filter(publication__version__changedocumentbinding__authorization__version__change__case=case)})
