from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render,redirect
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.policy.services import resolve
from apps.policy.recognition_validators import SCHEMAS
from apps.policy.recognition_drafts import draft_recognition_policy
from apps.agents.recognition import investigate
from apps.agents.models import AgentRun
from adapters.recognition import LocalRecognitionInbox
from .recognition_forms import commands
from .recognition_models import ProgressPacket
from . import recognition as domain

@login_required
def workbench(request,case_id):
 case=accessible_case(request.user,case_id);require(request.user,case,'recognition.read')
 forms=commands(case,request.POST if request.method=='POST' else None)
 if request.method=='POST':
  try:
   f=next((x['form'] for x in forms if x['action']==request.POST.get('action')),None)
   if not f or not f.is_valid():raise ValidationError(f.errors.as_text() if f else 'Choose a command')
   if set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Unexpected fields; authority claims are not accepted')
   d=f.cleaned_data;k=d['action'];a=request.user;c=case.pk;v=d['revision']
   if k=='prepare':domain.prepare(a,c,d['reference'],d['payload'],d['evidence'].pk,v)
   elif k=='preview_input':
    from .recognition_preview import capture
    row=capture(a,c,d['packet'].pk,d['operation_key'],d['evidence'].pk,d['note'],v)
    messages.info(request,'Private proposed input #'+str(row.pk)+' hash '+row.sha256+'; unbound observation, not attestation')
   elif k=='investigate':investigate(a,c,v)
   elif k=='policy':
    from django.db import transaction
    with transaction.atomic():
     domain.locked(a,c,'policy.configure',v);draft_recognition_policy(a,c,d['component'],d['content'],d['evidence'].pk,d['effective_from'])
   else:domain.record(a,c,d['packet'].pk,k,d['operation_key'],d['evidence'].pk,d['note'],v,d.get('verdict'),d['decision_evidence'].pk if d.get('decision_evidence') else None)
   messages.success(request,'F33 evidence/review history recorded');return redirect('recognition',case_id=c)
  except (ValidationError,ValueError,TypeError) as exc:messages.error(request,str(exc));case.refresh_from_db()
 packets=list(ProgressPacket.objects.filter(case=case).order_by('-pk')[:30])
 for p in packets:p.position=domain.position(p)
 return render(request,'finance/recognition.html',{'case':case,'commands':forms,'packets':packets,'policies':[resolve(k,case) for k in SCHEMAS],'schemas':SCHEMAS,'packet_schema':domain.PACKET,'agents':AgentRun.objects.filter(case=case,provider='deterministic-recognition-v1').order_by('-pk')[:5]})

@login_required
def export(request,case_id,packet_id):
 case=accessible_case(request.user,case_id)
 from django.shortcuts import get_object_or_404
 get_object_or_404(ProgressPacket,case=case,pk=packet_id)
 return JsonResponse(LocalRecognitionInbox().report(request.user,packet_id))
