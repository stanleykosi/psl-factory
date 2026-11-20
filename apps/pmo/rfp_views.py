from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, render, redirect
from django.http import FileResponse, Http404
from django.views.decorators.http import require_safe
from django.views.decorators.cache import never_cache
from adapters import case_uploads
from apps.core.evidence_access import restricted
from apps.core.views import accessible_case
from apps.identity.services import active_case_grants, require
from apps.policy.change_drafts import draft_standard_policy
from apps.agents.rfp import investigate_rfp
from apps.agents.models import AgentRun
from . import rfp, rfp_documents, rfp_portal, rfp_intake_upload
from .models import RFPCase, RFPResponse, RFPSubmission, RFPOutcome, RFPDisposition, RFPIntake
from .rfp_forms import forms_for

@login_required
@never_cache
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'rfp.read')
    upload_grants = ['rfp.intake', 'evidence.add', 'document.read']
    available=active_case_grants(request.user,[case.pk],actions=upload_grants+[f'rfp.contribute:{team}' for team in rfp.TEAMS])
    teams=[team for team in rfp.TEAMS if (case.pk,f'rfp.contribute:{team}') in available]
    uploads_allowed = all((case.pk, action) in available for action in upload_grants)
    forms=forms_for(case,request.POST if request.method=='POST' else None,team_choices=teams,
                    uploads_allowed=uploads_allowed,files=request.FILES)
    if request.method=='POST':
        try:
            command=next((x for x in forms if x['action']==request.POST.get('action')),None)
            if not command or not command['form'].is_valid():raise ValidationError(command['form'].errors.as_text() if command else 'Select a supported RFP action')
            d=command['form'].cleaned_data;a=request.user;c=case.pk;v=d['revision'];action=d['action']
            if request.FILES and (action != 'intake' or not uploads_allowed or set(request.FILES) != {'rfp_file'}
                                  or len(request.FILES.getlist('rfp_file')) != 1):
                raise ValidationError('Attach only one bid document using the received bid form.')
            if action=='intake':
                deadline = d['deadline_evidence'].pk if d['deadline_evidence'] else None
                facts = (d['received_at'], d['deadline_status'], d['deadline_at'], deadline, d['note'], v)
                if d.get('rfp_file'):
                    rfp_intake_upload.record(a, c, d['reference'], *facts, d['rfp_file'])
                else:
                    rfp.intake(a, c, d['reference'], d['evidence'].pk, *facts)
            elif action=='assign':rfp.assign(a,c,d['pm'],d['role'],d['evidence'].pk,d['note'],v)
            elif action=='contribute':
                rfp.record_team_input(a,c,d['team'],d['evidence'].pk,v,received_at=d['received_at'],source_party=d['source_party'],
                                      summary=d['summary'],person_days=d['person_days'],attested=d['attested'])
            elif action=='prepare':rfp.prepare_response(a,c,d['evidence'].pk,d['matrix'],{k:d[k].pk for k in ['requirements','plan','costing']},v,public_terms_id=d['public_terms'].pk)
            elif action=='review':rfp.review(a,c,d['response'].pk,d['role'],d['verdict'],d['evidence'].pk,d['note'],v)
            elif action=='draft':rfp_documents.draft(a,c,d['response'].pk,d['template'].pk,d['route_key'],v)
            elif action=='capture':rfp_documents.capture_submission(a,c,d['version'].version_id,v)
            elif action=='portal':rfp_portal.record(a,c,d['version'].version_id,d['evidence'].pk,d['note'],v)
            elif action=='outcome':rfp.outcome(a,c,d['submission'].pk,d['result'],d['observed_at'],d['role'],
                d['evidence'].pk if d['evidence'] else None,d['note'],v,followup_on=d['followup_on'],
                award_amount=d['award_amount'] or None,award_currency=d['award_currency'] or None,
                customer_expected_on=d['customer_expected_on'],remind_at=d['remind_at'])
            elif action=='dispose':rfp.dispose(a,c,d['outcome'].pk,d['lessons'].pk if d['lessons'] else None,v)
            elif action=='policy':draft_standard_policy(a,c,d['component'],d['content'],d['evidence'].pk,d['effective_from'])
            elif action=='investigate':investigate_rfp(a,c,v)
            messages.success(request,'RFP history updated');return redirect('rfp',case_id=c)
        except (ValidationError,ValueError,KeyError) as exc:messages.error(request,str(exc));case.refresh_from_db()
    r=RFPCase.objects.filter(case=case).select_related('current_intake').first()
    current_inputs = []
    current_attachment = None
    if r and r.current_intake_id:
        rows = r.current_intake.contributions.filter(team__in=rfp.TEAMS).order_by('team', '-pk').distinct('team')
        current_inputs = [row for row in rows.select_related('evidence').defer('evidence__body') if not restricted(row.evidence)]
        if (case.pk,'document.read') in available:
            try:
                current_attachment = rfp_intake_upload.attachment_for(request.user, case, r.current_intake)
            except PermissionDenied:
                pass
    return render(request,'pmo/rfp.html',{'case':case,'rfp':r,'commands':forms,'current_inputs':current_inputs,
        'current_attachment':current_attachment,
        'responses':RFPResponse.objects.filter(rfp=r).order_by('-pk'),
        'submissions':RFPSubmission.objects.filter(response__rfp=r).select_related('portal_receipt'),'outcomes':RFPOutcome.objects.filter(submission__response__rfp=r),
        'disposition':RFPDisposition.objects.filter(rfp=r).first(),'runs':AgentRun.objects.filter(case=case,provider='deterministic-rfp-investigation-v1').order_by('-pk')[:5]})


@login_required
@never_cache
@require_safe
def intake_attachment(request, case_id, intake_id):
    case = accessible_case(request.user, case_id)
    rfp_intake_upload.require_read(request.user, case)
    intake = get_object_or_404(RFPIntake.objects.select_related('rfp', 'actor').defer('actor__password'),
                               rfp__case=case, pk=intake_id)
    attachment = rfp_intake_upload.attachment_for(request.user, case, intake)
    if attachment is None:
        raise Http404('Bid document unavailable.')
    try:
        data = case_uploads.read(attachment)
    except (OSError, ValidationError) as exc:
        raise Http404('Bid document unavailable.') from exc
    return FileResponse(BytesIO(data), as_attachment=True, filename=attachment.name, content_type='application/octet-stream')
