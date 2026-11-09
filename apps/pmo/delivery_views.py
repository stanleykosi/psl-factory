from apps.pmo.go_live_attestations import parse_attestation
import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.policy.change_drafts import draft_standard_policy
from apps.agents.delivery import investigate_delivery
from apps.agents.models import AgentRun
from apps.documents.models import Template,PublicationReceipt
from .delivery import (SOURCE_OWNERS,open_dossier,capture_source,verify_source,decide_planning,record_progress,
    record_release_request,prepare_readiness,capture_release)
from .delivery_closure import (accept_go_live,reaffirm_go_live,latest_go_live,evaluate_hypercare,archive_artifacts,acknowledge_handover,confirm_finance,decide_closure,finalize_closure)
from .delivery_documents import draft_delivery_document
from .models import DeliveryDossier,DeliveryRecord,DeliveryCandidate,MeetingVersion,DeliveryDocumentBinding


def optional_bool(value):return {'true':True,'false':False,'unknown':None}.get(value)


@login_required
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'delivery.read')
    if request.method=='POST':
        try:
            p=request.POST;action=p['action'];expected=int(p['revision']);d=int(p.get('dossier') or 0)
            evidence=int(p.get('evidence') or 0);note=p.get('note','')
            if action=='open':open_dossier(request.user,case.pk,int(p['candidate']),evidence,note,expected)
            elif action=='source':
                kind=p['kind'];payload={}
                if kind=='ui_applicability':payload={k:optional_bool(p[k]) for k in ['requires_ui','client_signoff_required']}
                elif kind in ['ui_target','ui_design','ui_client']:
                    artifact={k:p[k] for k in ['artifact_ref','artifact_version','artifact_sha256']}
                    if kind=='ui_target':
                        from .services import subject
                        source=subject(case,int(p['artifact_evidence'])) if p.get('artifact_evidence') else None
                        payload=dict({k:value or None for k,value in artifact.items()},protocol='ui-target/v1',
                            artifact_evidence={'id':source.pk,'version':source.version,'sha256':source.sha256} if source else None)
                    else:payload={'protocol':'ui-approval/v1','approved_ui_target':artifact,
                        'source_version':p['source_version'],'signatory_ref':p['signatory_ref'],'decided_at':p['decided_at']}
                elif kind.startswith('hypercare_'):payload={'observed_at':p['observed_at'],'confirmed':optional_bool(p['confirmed']),'metrics':json.loads(p['metrics'])}
                capture_source(request.user,case.pk,d,kind,p['external_ref'],evidence,payload,expected)
            elif action=='verify':verify_source(request.user,case.pk,int(p['source']),expected)
            elif action=='plan':decide_planning(request.user,case.pk,d,p['verdict'],evidence,note,expected)
            elif action=='progress':record_progress(request.user,case.pk,d,p['kind'],evidence,note,expected,int(p['meeting']) if p.get('meeting') else None)
            elif action=='request':record_release_request(request.user,case.pk,d,p['external_ref'],evidence,note,expected)
            elif action=='ready':prepare_readiness(request.user,case.pk,d,expected)
            elif action=='release':capture_release(request.user,case.pk,d,int(p['readiness']) if p.get('readiness') else None,p['released_at'],p['external_ref'],evidence,note,expected)
            elif action=='draft':
                purpose=p['purpose'];keys={'go_live':['checklist','incident_reporting','rollback'],'handover':['support_document','escalation_document'],'closure':['retrospective_id','report_evidence_id']}
                if purpose not in keys:raise ValidationError('Unsupported delivery document')
                draft_delivery_document(request.user,case.pk,d,purpose,int(p['template']),{k:int(p[k]) for k in keys[purpose]},expected)
            elif action=='accept':accept_go_live(request.user,case.pk,d,int(p['receipt']),int(p['pm_signature']),int(p['client_signature']),note,expected,attestation=parse_attestation(p.get('attestation','')))
            elif action=='reaffirm':reaffirm_go_live(request.user,case.pk,d,int(p['previous_acceptance']),int(p['receipt']),int(p['pm_signature']),int(p['client_signature']),note,expected,attestation=parse_attestation(p.get('attestation','')),mode=p.get('mode','fresh_signatures'))
            elif action=='hypercare':evaluate_hypercare(request.user,case.pk,d,evidence,note,expected)
            elif action=='archive':archive_artifacts(request.user,case.pk,d,json.loads(p['inventory']),evidence,note,expected)
            elif action=='handover':acknowledge_handover(request.user,case.pk,d,int(p['receipt']),p['status'],evidence,note,expected)
            elif action=='finance':confirm_finance(request.user,case.pk,d,json.loads(p['milestone_ids']),p.get('inventory_complete')=='on',evidence,note,expected)
            elif action=='closure_decision':decide_closure(request.user,case.pk,int(p['version']),p['verdict'],evidence,note,expected)
            elif action=='close':finalize_closure(request.user,case.pk,d,expected)
            elif action=='investigate':investigate_delivery(request.user,case.pk,d,expected)
            elif action=='scan':
                from django.db import transaction
                from apps.core.services import lock_case
                from .delivery_obligations import scan_delivery
                with transaction.atomic():
                    lock_case(request.user,case.pk,'delivery.manage',expected);scan_delivery(request.user,case.pk,d)
            elif action=='policy':draft_standard_policy(request.user,case.pk,p['component'],json.loads(p['value']),evidence,p['effective_from'])
            else:raise ValidationError('Unsupported delivery command')
            messages.success(request,'Delivery evidence recorded; no deployment or financial transaction was dispatched')
            return redirect('delivery',case_id=case.pk)
        except (ValidationError,ValueError,KeyError) as exc:messages.error(request,str(exc));case.refresh_from_db()
    dossiers=list(DeliveryDossier.objects.filter(case=case).select_related('candidate').order_by('-pk')[:50])
    from .delivery import planning_inputs,readiness_inputs,dossier_for
    from .delivery_closure import hypercare_inputs
    for d in dossiers:
        d.go_live_head=latest_go_live(d,False);d.can_reaffirm_go_live=False
        if d.go_live_head and not d.records.filter(kind='closure').exists():
            try:
                from apps.policy.services import decision_authority
                require(request.user,case,'delivery.manage');decision_authority(request.user,case,'PM','reaffirm_go_live');d.can_reaffirm_go_live=True
            except (ValidationError,PermissionDenied):pass
        d.go_live_receipts=PublicationReceipt.objects.filter(publication__version__deliverydocumentbinding__dossier=d,
            publication__version__deliverydocumentbinding__purpose='go_live',publication__version__audience='client').order_by('-pk')[:100]
        from .go_live_attestations import declaration_draft
        d.go_live_receipts=list(d.go_live_receipts)
        for receipt in d.go_live_receipts:receipt.attestation_draft=declaration_draft(d,receipt,request.user)
        d.go_live_legacy=bool(d.go_live_head and not d.go_live_head.data.get('attestation'))
        d.checks={}
        d.lifecycle='Closure recorded; immutable archive index preserved' if d.records.filter(kind='closure').exists() else 'Release outcome recorded' if d.records.filter(kind='release_outcome').exists() else 'Planning and delivery evidence in progress'
        for key,fn in [('Planning',planning_inputs),('Release evidence',readiness_inputs),('Hypercare',hypercare_inputs)]:
            try:dossier_for(case,d.pk);d.checks[key]={'state':'Source evidence available','details':fn(d)}
            except (ValidationError,PermissionDenied) as exc:d.checks[key]={'state':'Needs attention','details':str(exc)}
    return render(request,'pmo/delivery.html',{'case':case,'dossiers':dossiers,'kinds':SOURCE_OWNERS,
        'candidates':DeliveryCandidate.objects.filter(case=case),'evidence':case.evidence.all(),
        'meetings':MeetingVersion.objects.filter(meeting__case=case).order_by('-pk')[:100],
        'templates':Template.objects.filter(case=case,definition__document_type='project_artifact'),
        'receipts':PublicationReceipt.objects.filter(publication__version__deliverydocumentbinding__dossier__case=case),
        'bindings':DeliveryDocumentBinding.objects.filter(dossier__case=case).order_by('-pk')[:100],
        'runs':AgentRun.objects.filter(case=case,provider='deterministic-delivery-investigation-v1').order_by('-pk')[:10]})
