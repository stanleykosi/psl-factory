from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.shortcuts import render,redirect
from apps.core.views import accessible_case
from apps.core.services import lock_case
from apps.identity.services import require
from apps.policy.partner_drafts import draft_partner_policy
from apps.agents.partners import investigate
from apps.agents.models import AgentRun
from . import partner_operations as domain,partner_delivery
from .partner_forms import commands
from .models import PartnerRecord,PartnerDecision,OnboardingEvent,PartnerReport,PartnerReportReview,PartnerFollowup,PartnerFinanceJob,PartnerFinanceReceipt,PartnerBillingImport

def definition_for(report):
    # Historical context comes from the exact reviewed policy, never current policy fallback.
    from apps.policy.models import Configuration
    from apps.policy.services import reference_values
    c=Configuration.objects.filter(case=report.record.case,pk=report.snapshot.get('policy')).first()
    if not c:return None
    value=reference_values(c)[0]
    if value.get('implementation')!='partner_activity_v1':return None
    return {'policy':c.pk,'active_kinds':value['active_kinds'],'excluded_kinds':value['excluded_kinds'],'timezone':value['timezone']}

@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'baas.read');require(request.user,case,'partner.read');forms=commands(case,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            f=next((x['form'] for x in forms if x['action']==request.POST.get('action')),None)
            if not f or not f.is_valid():raise ValidationError(f.errors.as_text() if f else 'Choose a partner action')
            d=f.cleaned_data;a=request.user;c=case.pk;v=d['revision'];key=d['action']
            if key=='capture':domain.capture(a,c,d['kind'],d['reference'],d['evidence'].pk,v)
            elif key=='agreement':domain.decide_agreement(a,c,d['record'].pk,d['purpose'],d['verdict'],d['role'],d['evidence'].pk,d['reason'],v)
            elif key=='stage':domain.transition_stage(a,c,d['record'].pk,d['operation'],d['stage'],d['occurred_at'],d['role'],d['evidence'].pk,d['required_evidence_ids'],v)
            elif key=='followup':domain.followup(a,c,d['record'].pk,d['source_key'],d['owner_id'].pk,d['due_at'],d['role'],d['evidence'].pk,d['reason'],v)
            elif key=='report':domain.build_report(a,c,d['record'].pk,v)
            elif key=='review':domain.review_report(a,c,d['report'].pk,d['verdict'],d['role'],d['evidence'].pk,v)
            elif key=='reserve':domain.reserve(a,c,d['report'].pk,d['role'],v)
            elif key=='operate':partner_delivery.operate(a,c,d['job'].pk,d['operation'],d['reason'],v)
            elif key=='import':domain.import_finance_usage(a,c,d['receipt'].pk,d['role'],d['evidence'].pk,v)
            elif key=='investigate':investigate(a,c,v)
            elif key=='policy':
                with transaction.atomic():lock_case(a,c,'policy.configure',v);draft_partner_policy(a,c,d['component'],d['content'],d['evidence'].pk,d['effective_from'])
            messages.success(request,'Partner history updated');return redirect('partner_operations',case_id=c)
        except (ValidationError,ValueError,TypeError) as exc:messages.error(request,str(exc));case.refresh_from_db()
    records=list(PartnerRecord.objects.filter(case=case).order_by('-pk')[:100])
    for r in records:
        r.position=domain.agreement_position(r) if r.kind=='agreement' else domain.age(r) if r.kind=='onboarding' else None
    reports=list(PartnerReport.objects.filter(record__case=case).order_by('-pk')[:30])
    for r in reports:
        r.definition=definition_for(r)
        r.source_cutoff=r.record.payload['extracted_at']
        r.review=PartnerReportReview.objects.filter(report=r).order_by('-pk').first()
        try:domain.report_current(r);r.current=True
        except (ValidationError,PermissionDenied):r.current=False
        try:domain.approved(r);r.approved=True
        except (ValidationError,PermissionDenied):r.approved=False
    return render(request,'baas/partners.html',{'case':case,'commands':forms,'records':records,'reports':reports,'events':OnboardingEvent.objects.filter(record__case=case).order_by('-pk')[:60],'decisions':PartnerDecision.objects.filter(record__case=case).order_by('-pk')[:30],
       'followups':PartnerFollowup.objects.filter(record__case=case).select_related('action__current').order_by('-pk')[:40],'jobs':PartnerFinanceJob.objects.filter(report__record__case=case).order_by('-pk')[:30],'receipts':PartnerFinanceReceipt.objects.filter(report__record__case=case).order_by('-pk')[:30],'imports':PartnerBillingImport.objects.filter(receipt__report__record__case=case).order_by('-pk')[:30],'agents':AgentRun.objects.filter(case=case,provider='deterministic-partners-v1').order_by('-pk')[:5]})

@login_required
def inbox(request):
    receipts=[]
    for r in PartnerFinanceReceipt.objects.filter(recipient=request.user).select_related('report__record__case').order_by('-pk')[:100]:
        try:require(request.user,r.report.record.case,'partner.finance.receive');require(request.user,r.report.record.case,'finance.read');require(request.user,r.report.record.case,'case.read')
        except PermissionDenied:continue
        r.definition=definition_for(r.report)
        r.source_cutoff=r.report.record.payload['extracted_at']
        receipts.append(r)
    return render(request,'baas/partner_finance_inbox.html',{'receipts':receipts})
