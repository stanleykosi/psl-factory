from apps.core.evidence_access import public_evidence,restricted
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import render, redirect
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.identity.models import Grant
from apps.workflows.models import HumanTask
from apps.agents.documents import draft_document, check_document, check_candidate
from .models import Template, Document, Version, PublicationJob, PublicationReceipt
from .forms import TemplateForm, DraftForm, ReviewForm, CandidateForm, GateForm
from apps.pmo.models import DeliveryCandidate
from apps.pmo.gates import register_candidate, record_gate, verify_gate, draft_gate_packet, gate_summary
from .controlled import register_template, create_version, request_review, review_version, reserve_publication, withdraw_review, preflight
from .delivery import operate_publication

@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id)
    require(request.user,case,'document.read')
    templates=Template.objects.filter(case=case).exclude(definition__document_type='accepted_finance_metadata').order_by('name','-version')
    versions=Version.objects.filter(document__case=case).exclude(template__definition__document_type='accepted_finance_metadata').select_related('document','template').order_by('-pk')
    finance_reader=Grant.objects.filter(case=case,user=request.user,action='finance.read',active=True).exists()
    if not finance_reader:
        versions=versions.filter(forecastbinding__isnull=True)
        templates=templates.exclude(definition__document_type='finance_group_report').exclude(pk__in=Version.objects.filter(document__case=case,forecastbinding__isnull=False).values('template_id'))
    evidence=public_evidence(case.evidence.all()).order_by('-pk')
    tf=TemplateForm();df=DraftForm();rf=ReviewForm();cf=CandidateForm();gf=GateForm()
    candidates=DeliveryCandidate.objects.filter(case=case)
    cf.fields['requirements'].queryset=evidence.filter(kind='requirements')
    gf.fields['candidate'].queryset=candidates;gf.fields['evidence'].queryset=evidence
    tf.fields['evidence'].queryset=evidence.filter(kind='policy_decision')
    df.fields['template'].queryset=templates;df.fields['sources'].queryset=evidence
    rf.fields['version'].queryset=versions
    if request.method=='POST':
        try:
            action=request.POST.get('action');expected=int(request.POST['revision'])
            if action=='candidate':
                cf=CandidateForm(request.POST);cf.fields['requirements'].queryset=evidence.filter(kind='requirements')
                if not cf.is_valid():raise ValidationError(cf.errors.as_text())
                d=cf.cleaned_data;register_candidate(request.user,case.pk,d['reference'],d['requirements'].pk,expected)
            elif action=='gate':
                gf=GateForm(request.POST);gf.fields['candidate'].queryset=candidates;gf.fields['evidence'].queryset=evidence
                if not gf.is_valid():raise ValidationError(gf.errors.as_text())
                d=gf.cleaned_data;record_gate(request.user,case.pk,d['candidate'].pk,d['kind'],d['external_ref'],d['evidence'].pk,expected)
            elif action=='gate_verify':
                verify_gate(request.user,case.pk,int(request.POST['record']),expected)
            elif action=='gate_packet':
                draft_gate_packet(request.user,case.pk,int(request.POST['candidate']),int(request.POST['template']),request.POST['audience'],expected)
            elif action=='gate_check':
                check_candidate(request.user,case.pk,int(request.POST['candidate']))
            elif action=='template':
                tf=TemplateForm(request.POST);tf.fields['evidence'].queryset=evidence.filter(kind='policy_decision')
                if not tf.is_valid():raise ValidationError(tf.errors.as_text())
                d=tf.cleaned_data;register_template(request.user,case.pk,d['name'],d['definition'],d['evidence'].pk,expected)
            elif action in ['draft','agent_draft']:
                df=DraftForm(request.POST);df.fields['template'].queryset=templates;df.fields['sources'].queryset=evidence
                if not df.is_valid():raise ValidationError(df.errors.as_text())
                d=df.cleaned_data
                if action=='agent_draft':
                    draft_document(request.user,case.pk,d['template'].pk,d['title'],d['audience'],[e.pk for e in d['sources']],expected,d['document_id'])
                else:
                    create_version(request.user,case.pk,d['template'].pk,d['title'],d['audience'],d['fields'] or {},expected,d['document_id'])
            elif action=='review':
                rf=ReviewForm(request.POST);rf.fields['version'].queryset=versions
                if not rf.is_valid():raise ValidationError(rf.errors.as_text())
                d=rf.cleaned_data;review_version(request.user,case.pk,d['version'].pk,d['verdict'],d['note'],expected,d['delegated'])
            elif action in ['request','publish','check','withdraw']:
                version_id=int(request.POST['version'])
                if action=='request':request_review(request.user,case.pk,version_id,expected)
                elif action=='publish':reserve_publication(request.user,case.pk,version_id,expected)
                elif action=='withdraw':withdraw_review(request.user,case.pk,version_id,request.POST.get('reason',''),expected)
                else:check_document(request.user,case.pk,version_id)
            elif action in ['retry','cancel']:
                operate_publication(request.user,case.pk,int(request.POST['job']),action,request.POST.get('reason',''),expected)
            else:raise ValidationError('Unknown document operation')
            messages.success(request,'Document work recorded. Delivery runs through the publication worker.')
            return redirect('documents',case_id=case.pk)
        except (ValidationError,ValueError,KeyError) as exc:
            messages.error(request,str(exc));case.refresh_from_db()
    for form,field,queryset in [(tf,'evidence',evidence.filter(kind='policy_decision')),(df,'template',templates),(df,'sources',evidence),(rf,'version',versions)]:
        form.fields[field].queryset=queryset
    actions=set(Grant.objects.filter(user=request.user,case=case,active=True).values_list('action',flat=True))
    items=list(versions)
    from apps.finance.presentation import present
    for version in items:
        version.findings=preflight(version);version.finance_presentation=present(version.payload)
    candidate_rows=list(candidates)
    from apps.pmo.models import ApprovalGateBinding
    for candidate in candidate_rows:
        candidate.summary=gate_summary(candidate,request.user);candidate.visible_gates=[]
        for gate in candidate.gates.all():
            binding=ApprovalGateBinding.objects.filter(verification__record=gate).select_related('observation__receipt').order_by('-pk').first()
            if binding:
                try:require(request.user,case,'approval.source.read:'+binding.observation.receipt.system)
                except (PermissionDenied,ValidationError):continue
            candidate.visible_gates.append(gate)
    visible_jobs=PublicationJob.objects.filter(publication__version__document__case=case).exclude(publication__version__template__definition__document_type='accepted_finance_metadata')
    if not finance_reader:visible_jobs=visible_jobs.filter(publication__version__forecastbinding__isnull=True)
    return render(request,'documents/workbench.html',{'case':case,'actions':actions,'template_form':tf,'draft_form':df,'review_form':rf,
        'candidate_form':cf,'gate_form':gf,'candidates':candidate_rows,'templates':templates,'versions':items,'tasks':HumanTask.objects.filter(case=case).exclude(version__template__definition__document_type='accepted_finance_metadata').select_related('version__document').order_by('-pk'),
        'jobs':visible_jobs.select_related('publication__version__document').order_by('-pk'),
        'agent_runs':case.agentrun_set.filter(process_id__in=['P52','P53','P31']).order_by('-pk')[:20] if 'agent.document' in actions or 'agent.gates' in actions else []})

@login_required
def inbox(request):
    receipts=[]
    for receipt in PublicationReceipt.objects.filter(recipient=request.user).select_related('publication__version__document__case').order_by('-pk')[:100]:
        try:
            version=receipt.publication.version
            from apps.finance.accepted_documents import recipient_access
            recipient_access(request.user,receipt)
            require(request.user,version.document.case,'document.receive:'+version.audience)
            if version.audience=='group':
                from apps.finance.group_forecast import recipient_access
                recipient_access(request.user,receipt)
            if version.template.definition.get('document_type')=='finance_report':
                require(request.user,version.document.case,'finance.read')
        except (PermissionDenied,ValidationError):continue
        from apps.finance.presentation import present
        receipt.finance_presentation=present(receipt.payload)
        receipts.append(receipt)
    response=render(request,'documents/inbox.html',{'receipts':receipts});response['Cache-Control']='no-store';return response
