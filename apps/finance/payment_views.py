from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.shortcuts import render,redirect
from apps.core.views import accessible_case
from apps.core.services import lock_case
from apps.identity.services import require
from apps.policy.services import resolve
from apps.policy.payment_validators import SCHEMAS,ROLE,PEOPLE,DELEGATION,VALIDITY
from apps.policy.payment_drafts import draft_payment_policy
from apps.agents.payments import investigate
from apps.agents.models import AgentRun
from adapters.payment_release import LocalPaymentReleaseControls
from . import payments as domain
from .models import PaymentAssessment,PaymentException,PaymentReleaseReservation
from .payment_forms import commands

@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id)
    for action in ['payment.read','finance.read','delivery.read']:require(request.user,case,action)
    forms=commands(case,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            f=next((x['form'] for x in forms if x['action']==request.POST.get('action')),None)
            if not f or not f.is_valid():raise ValidationError(f.errors.as_text() if f else 'Choose a payment action')
            if set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Unexpected command fields; caller approval/role claims are not accepted')
            d=f.cleaned_data;k=d['action'];v=d['revision'];a=request.user;c=case.pk
            if k=='assess':domain.assess(a,c,d['dossier'].pk,d['coverage'].pk,v)
            elif k=='request':domain.request_exception(a,c,d['assessment'].pk,d['operation_key'],d['reason'],d['evidence'].pk,d['valid_from'],d['valid_until'],v)
            elif k=='decide':domain.decide(a,c,d['request'].pk,d['verdict'],d['evidence'].pk,d['reason'],v)
            elif k=='reserve':domain.reserve(a,c,d['assessment'].pk,d['operation_key'],v,d['request'].pk if d['request'] else None)
            elif k=='check':
                with transaction.atomic():
                    lock_case(a,c,'payment.release.reserve',v);LocalPaymentReleaseControls().check_for_use(a,c,d['reservation'].pk)
            elif k=='investigate':investigate(a,c,v)
            elif k=='policy':
                with transaction.atomic():lock_case(a,c,'policy.configure',v);draft_payment_policy(a,c,d['component'],d['content'],d['evidence'].pk,d['effective_from'])
            messages.success(request,'Payment control history updated; no deployment dispatched or debt waived');return redirect('payment_controls',case_id=c)
        except (ValidationError,ValueError,TypeError) as exc:messages.error(request,str(exc));case.refresh_from_db()
    assessments=list(PaymentAssessment.objects.filter(case=case).order_by('-pk')[:30])
    for r in assessments:
        # Django floatformat intentionally returns very long decimals unchanged.
        # Format the bounded decimal for presentation only; decisions use exact amounts.
        r.percentage_display=format(Decimal(r.result['percentage']),'.2f') if r.result['percentage'] is not None else 'UNKNOWN'
        try:domain.assessment_current(r);r.current=True
        except (ValidationError,PermissionDenied):r.current=False
    requests=list(PaymentException.objects.filter(assessment__case=case).select_related('actor','assessment').order_by('-pk')[:30])
    for q in requests:
        q.latest=q.decisions.order_by('-pk').first()
        q.workflow_status=q.latest.verdict if q.latest else ('awaiting_authority_configuration' if any(resolve(k,case).status!='ACTIVE' for k in [ROLE,PEOPLE,DELEGATION,VALIDITY]) else 'awaiting_human_decision')
        try:domain.usable(q);q.use_status='Current human exception; independent release checks still required'
        except (ValidationError,PermissionDenied) as exc:q.use_status=str(exc)
    reservations=list(PaymentReleaseReservation.objects.filter(assessment__case=case).order_by('-pk')[:30])
    return render(request,'finance/payments.html',{'case':case,'commands':forms,'assessments':assessments,'requests':requests,'reservations':reservations,'policies':[resolve(k,case) for k in SCHEMAS],'schemas':{k:v[1] for k,v in SCHEMAS.items()},'agents':AgentRun.objects.filter(case=case,provider='deterministic-payments-v1').order_by('-pk')[:5]})
