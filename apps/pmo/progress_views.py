from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from apps.core.views import accessible_case
from apps.core.evidence_access import public_evidence
from apps.pmo.delivery import dossier_for
from apps.pmo import progress
from apps.pmo.models import DeliveryProgressCorrelation, DeliveryProgressObservation


@login_required
def workbench(request,case_id,dossier_id):
    case=accessible_case(request.user,case_id);progress.readable(request.user,case)
    dossier=dossier_for(case,dossier_id,current=False)
    if request.method=='POST':
        try:
            p=request.POST;expected=int(p['revision']);action=p['action']
            optional=lambda key:int(p[key]) if p.get(key) else None
            if action=='configure':
                progress.configure(request.user,case.pk,dossier.pk,p['team'],p['identity'],p['reference'],int(p['participant']),p['mode'],int(p['evidence']),expected,max_age_seconds=optional('max_age_seconds'))
            elif action=='observe':
                # Restrict nested source IDs to this exact rendered dossier.
                source=progress.source_for(request.user,case,int(p['source']))
                if source.dossier_id!=dossier.pk:raise ValidationError('Select this dossier source')
                fields={} if p['availability']!='available' else {'activity_ref':p['activity_ref'],'dependency_ref':p.get('dependency_ref') or None,
                    'summary':p['summary'],'timeline_impact':{'unknown':None,'true':True,'false':False}[p['timeline_impact']],
                    'scope_change':{'unknown':None,'true':True,'false':False}[p['scope_change']]}
                progress.observe(request.user,case.pk,source.pk,optional('previous'),p['source_version'],p['observed_at'],p['availability'],fields,expected)
            elif action=='correlate':
                if not DeliveryProgressObservation.objects.filter(pk=int(p['observation']),source__dossier=dossier).exists():raise ValidationError('Select this dossier observation')
                progress.correlate(request.user,case.pk,int(p['observation']),optional('previous'),int(p['planning']),int(p['issue']),int(p['state']),optional('profile'),p['impact'],int(p['evidence']),expected)
            elif action=='investigate':
                from apps.agents.progress import investigate
                investigate(request.user,case.pk,dossier.pk,expected)
            else:raise ValidationError('Unsupported progress command')
            messages.success(request,'Source-bound progress recorded. No plan change, issue closure or communication dispatched.')
            return redirect('delivery_progress',case_id=case.pk,dossier_id=dossier.pk)
        except (ValidationError,ValueError,KeyError) as exc:
            messages.error(request,str(exc));case.refresh_from_db()
    result=progress.report(request.user,dossier)
    return render(request,'pmo/progress.html',{'case':case,'dossier':dossier,'result':result,
        'evidence':public_evidence(case.evidence.all()),'plans':dossier.records.filter(kind='planning_decision').order_by('-pk')[:50]})
