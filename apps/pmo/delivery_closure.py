from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from apps.core.services import lock_case,bump,event
from apps.identity.services import require
from apps.policy.services import active_component,reference_values,decision_authority
from apps.documents.models import PublicationReceipt
from .delivery import dossier_for,ensure_open,latest,record,verified_source,valid_release
from .models import DeliveryRecord,DeliveryDocumentBinding,MeetingVersion,Milestone
from .services import subject
from .commercial import note_required
from .clocks import aware
from apps.core.read_observation import observed_fact


@observed_fact
def go_live_inputs(d,data):
    outcome=valid_release(d)
    kinds={'checklist':'deployment_checklist','incident_reporting':'incident_reporting','rollback':'rollback_plan'}
    if set(data)!=set(kinds):raise ValidationError('Exact deployment checklist, incident reporting and rollback source evidence required')
    return {'outcome_id':outcome.pk,'readiness_id':outcome.parent_id,
        'evidence':{k:subject(d.case,data[k],kind).pk for k,kind in kinds.items()}}

def go_live_requirements(d,data=None,template_id=None):
    """Independent native facts for useful preparation; no signature or acceptance inference."""
    from django.core.exceptions import PermissionDenied
    from django.utils import timezone
    from apps.documents.models import Template
    kinds={'checklist':'deployment_checklist','incident_reporting':'incident_reporting','rollback':'rollback_plan'}
    data=data if data is not None else {k:None for k in kinds}
    if not isinstance(data,dict) or set(data)!=set(kinds) or any(v is not None and (type(v) is not int or not 1<=v<=9223372036854775807) for v in [*data.values(),template_id]):
        raise ValidationError('Exact integer go-live source/template references or unprovided values required')
    checks=[]
    def check(key,title,fn,next_action,unknown=False):
        if unknown:checks.append({'key':key,'title':title,'status':'unknown','summary':next_action,'references':[]});return
        try:row=fn();checks.append({'key':key,'title':title,'status':'current','summary':'Current recorded evidence is available','references':[row.pk]})
        except (ValidationError,PermissionDenied) as exc:checks.append({'key':key,'title':title,'status':'held','summary':next_action,'references':[],'finding':str(exc)})
    def context():dossier_for(d.case,d.pk);return d
    check('context','Project scope',context,'Review the current project scope and any recorded closure')
    closed=latest(d,'closure',False)
    if closed and checks[0]['status']=='current':checks[0].update(status='closed',summary='Closure is recorded; preparation cannot reopen this delivery.',references=[d.pk,closed.pk])
    check('release','Actual release',lambda:valid_release(d),'Record the actual Infrastructure release against current readiness')
    def template():
        t=Template.objects.filter(case=d.case,pk=template_id,definition__document_type='project_artifact').first()
        if not t or not {'scope','risks','next_steps'}.issubset(t.definition['audience_fields'].get('client',[])):
            raise ValidationError('Client template must include checklist, incident reporting and rollback sections')
        return t
    check('template','Client report template',template,'Choose the controlled client report template',template_id is None)
    for key,title in [('checklist','Deployment checklist'),('incident_reporting','Incident reporting'),('rollback','Rollback plan')]:
        check(key,title,lambda key=key:subject(d.case,data[key],kinds[key]),'Provide the actual '+title.lower()+' evidence',data[key] is None)
    return {'as_of':timezone.now().isoformat(),'checks':checks,'ready_to_prepare':all(c['status']=='current' for c in checks),
        'selected':data,'template_id':template_id,'sign_off_inferred':False,'deployment_authorized':False,'financial_release_granted':False}


@observed_fact
def accepted_go_live(d):
    accepted=latest_go_live(d);require(accepted.actor,d.case,'delivery.manage')
    authority=decision_authority(accepted.actor,d.case,'PM','reaffirm_go_live' if accepted.kind=='go_live_reaffirmation' else 'approve')
    if accepted.kind=='go_live_reaffirmation' and accepted.data['authority']!=authority:raise ValidationError('Go-live evidence reaffirmation authority changed; obtain a current exact human attestation')
    receipt=PublicationReceipt.objects.get(pk=accepted.data['receipt_id'])
    from apps.documents.controlled import current_version
    current_version(d.case,receipt.publication.version_id)
    binding=DeliveryDocumentBinding.objects.get(version=receipt.publication.version)
    if binding.purpose!='go_live' or binding.snapshot!=go_live_inputs(d,binding.data) or accepted.snapshot!=binding.snapshot:
        raise ValidationError('Go-live acceptance source changed; preserve history and reconcile explicitly')
    return accepted

def latest_go_live(d,required=True):
    from .delivery_models import GO_LIVE_KINDS
    current=d.records.filter(kind__in=GO_LIVE_KINDS).order_by('-pk').first()
    if required and not current:raise ValidationError('Missing actual go-live sign-off evidence')
    return current

def go_live_evidence(case,d,receipt_id,pm_signature_id,client_signature_id):
    if any(type(pk) is not int or pk<1 for pk in [receipt_id,pm_signature_id,client_signature_id]):raise ValidationError('Exact actual receipt and signature references required')
    receipt=PublicationReceipt.objects.filter(pk=receipt_id,publication__version__deliverydocumentbinding__dossier=d,
        publication__version__deliverydocumentbinding__purpose='go_live',publication__version__audience='client').first()
    if not receipt:raise ValidationError('Select the exact delivered client go-live document')
    from apps.documents.controlled import current_version
    current_version(case,receipt.publication.version_id)
    pm=subject(case,pm_signature_id,'signature');client=subject(case,client_signature_id,'signature')
    if pm.pk==client.pk:raise ValidationError('PM and Client require distinct exact signature evidence')
    from .delivery_models import GO_LIVE_KINDS
    used=DeliveryRecord.objects.filter(kind__in=GO_LIVE_KINDS,dossier__case=case)
    if used.filter(Q(data__pm_signature_id__in=[pm.pk,client.pk])|Q(data__client_signature_id__in=[pm.pk,client.pk])).exists():
        raise ValidationError('Go-live signature evidence cannot be reused')
    binding=DeliveryDocumentBinding.objects.get(version=receipt.publication.version)
    if binding.snapshot!=go_live_inputs(d,binding.data):raise ValidationError('Go-live evidence changed; prepare a current exact report')
    return receipt,pm,client,binding


@transaction.atomic
def accept_go_live(actor,case_id,dossier_id,receipt_id,pm_signature_id,client_signature_id,note,expected):
    case=lock_case(actor,case_id,'delivery.manage',expected);d=dossier_for(case,dossier_id);ensure_open(d);decision_authority(actor,case,'PM');note_required(note)
    if latest_go_live(d,False):raise ValidationError('Go-live is already recorded; reviewed evidence changes need explicitly configured reaffirmation authority')
    receipt,pm,client,binding=go_live_evidence(case,d,receipt_id,pm_signature_id,client_signature_id)
    return record(actor,case,d,'go_live',pm,{'receipt_id':receipt.pk,'pm_signature_id':pm.pk,'client_signature_id':client.pk,'note':note},binding.snapshot,valid_release(d))

@transaction.atomic
def reaffirm_go_live(actor,case_id,dossier_id,previous_acceptance_id,receipt_id,pm_signature_id,client_signature_id,note,expected):
    """Explicitly authorised human evidence successor; never a second go-live event."""
    case=lock_case(actor,case_id,'delivery.manage',expected);d=dossier_for(case,dossier_id);ensure_open(d);note_required(note)
    authority=decision_authority(actor,case,'PM','reaffirm_go_live')
    previous=latest_go_live(d)
    if type(previous_acceptance_id) is not int or previous.pk!=previous_acceptance_id:raise ValidationError('STALE_VERSION: review the exact current go-live evidence head')
    receipt,pm,client,binding=go_live_evidence(case,d,receipt_id,pm_signature_id,client_signature_id)
    return record(actor,case,d,'go_live_reaffirmation',pm,{'receipt_id':receipt.pk,'pm_signature_id':pm.pk,'client_signature_id':client.pk,
        'previous_acceptance_id':previous.pk,'authority':authority,'note':note},binding.snapshot,previous)


@observed_fact
def hypercare_inputs(d):
    outcome=valid_release(d);accepted=accepted_go_live(d)
    config=active_component('D11.hypercare_criteria_ref',d.case);criteria=reference_values(config)[0]
    due=aware(outcome.data['released_at'])+timedelta(hours=criteria['minimum_hours'])
    sources={};findings=[];unknown=False
    for owner in criteria['confirmation_owners']:
        kind='hypercare_'+owner.lower()
        try:s,v=verified_source(d,kind)
        except ValidationError as exc:findings+=exc.messages;unknown=True;continue
        p=s.payload;sources[owner]=[s.pk,v.pk]
        if p['confirmed'] is not True:
            findings.append(owner+' stability confirmation is '+('unknown' if p['confirmed'] is None else 'negative'));unknown|=p['confirmed'] is None
        if aware(p['observed_at'])<due:findings.append(owner+' observation precedes the configured elapsed hypercare period')
        for metric in [m for m in criteria['metrics'] if m['owner']==owner]:
            actual=p['metrics'].get(metric['key'])
            if not actual or actual['value'] is None:findings.append(owner+'/'+metric['key']+' remains unknown');unknown=True;continue
            if actual['unit']!=metric['unit']:findings.append(owner+'/'+metric['key']+' unit differs');continue
            x,y=actual['value'],metric['threshold']
            ok={'lte':lambda:x<=y,'gte':lambda:x>=y,'eq':lambda:x==y}[metric['operator']]()
            if not ok:findings.append(owner+'/'+metric['key']+' fails the configured criterion')
    return {'outcome_id':outcome.pk,'acceptance_id':accepted.pk,'policy_id':config.pk,'sources':sources,
        'due_at':due.isoformat(),'qualified':None if unknown else not findings,'findings':findings}


def guard_evaluate_hypercare(actor,case,dossier_id):
    require(actor,case,'delivery.manage')
    d=dossier_for(case,dossier_id);ensure_open(d)
    return d,hypercare_inputs(d)


@transaction.atomic
def evaluate_hypercare(actor,case_id,dossier_id,evidence_id,note,expected):
    case=lock_case(actor,case_id,'delivery.manage',expected);note_required(note)
    d,snapshot=guard_evaluate_hypercare(actor,case,dossier_id)
    return record(actor,case,d,'hypercare',subject(case,evidence_id),{'note':note},snapshot,valid_release(d))


@observed_fact
def archive_inputs(d,inventory):
    outcome=valid_release(d);accepted=accepted_go_live(d)
    config=active_component('D11.template_storage_retention_rules',d.case);rules=reference_values(config)[0]
    if 'closure_inventory' not in rules:raise ValidationError('D11.template_storage_retention_rules.closure_inventory is unconfigured; storage v2 interface required')
    required=rules['closure_inventory']['required_kinds']
    if not isinstance(inventory,dict) or set(inventory)!=set(required):raise ValidationError('Supply each exact configured closure inventory kind, without unknown additions')
    refs={}
    for kind,pk in inventory.items():
        e=subject(d.case,pk,kind);refs[kind]={'id':e.pk,'version':e.version,'sha256':e.sha256}
    s,v=verified_source(d,'technical_finalization')
    if s.evidence_id!=refs['technical_document']['id']:raise ValidationError('Engineering finalization must bind the exact archived technical document')
    return {'outcome_id':outcome.pk,'acceptance_id':accepted.pk,'policy_id':config.pk,'sources':[s.pk,v.pk],
        'inventory':refs,'repository':'internal-versioned','retention_days':rules['retention_days'],'physical_purge_performed':False}


@transaction.atomic
def archive_artifacts(actor,case_id,dossier_id,inventory,evidence_id,note,expected):
    case=lock_case(actor,case_id,'delivery.manage',expected);d=dossier_for(case,dossier_id);ensure_open(d);note_required(note)
    return record(actor,case,d,'archive',subject(case,evidence_id),{'inventory':inventory,'note':note},archive_inputs(d,inventory),valid_release(d))


@observed_fact
def current_archive(d):
    r=latest(d,'archive');require(r.actor,d.case,'delivery.manage')
    if r.snapshot!=archive_inputs(d,r.data['inventory']):raise ValidationError('Archive source/policy changed; append a fresh inventory')
    return r


@observed_fact
def handover_inputs(d,data):
    archive=current_archive(d)
    if set(data)!={'support_document','escalation_document'}:raise ValidationError('Support and escalation source documents required')
    return {'archive_id':archive.pk,'acceptance_id':accepted_go_live(d).pk,
        'support_document':subject(d.case,data['support_document'],'support_document').pk,
        'escalation_document':subject(d.case,data['escalation_document'],'escalation_document').pk}


@transaction.atomic
def acknowledge_handover(actor,case_id,dossier_id,receipt_id,status,evidence_id,note,expected):
    case=lock_case(actor,case_id,'delivery.support_receive',expected);d=dossier_for(case,dossier_id);ensure_open(d);note_required(note)
    if status not in ['received','gaps']:raise ValidationError('Record receipt or specific handover gaps; this is not an approval task')
    receipt=PublicationReceipt.objects.filter(pk=receipt_id,recipient=actor,publication__version__audience='internal',
        publication__version__deliverydocumentbinding__dossier=d,publication__version__deliverydocumentbinding__purpose='handover').first()
    if not receipt:raise ValidationError('Only the actual Support/Operations recipient can acknowledge its exact delivered handover')
    require(actor,case,'document.receive:internal')
    from apps.documents.controlled import current_version
    current_version(case,receipt.publication.version_id)
    binding=DeliveryDocumentBinding.objects.get(version=receipt.publication.version)
    if binding.snapshot!=handover_inputs(d,binding.data):raise ValidationError('Handover source changed; publish a fresh version')
    return record(actor,case,d,'handover',subject(case,evidence_id),{'receipt_id':receipt.pk,'recipient_id':actor.pk,'status':status,'note':note},binding.snapshot)


@observed_fact
def finance_inputs(d):
    from apps.finance.models import Handoff
    result=[]
    milestones=list(Milestone.objects.filter(case=d.case).order_by('pk')[:201])
    if len(milestones)>200:raise ValidationError('Milestone inventory exceeds bounded closure budget')
    for m in milestones:
        receipt=Handoff.objects.filter(case=d.case,milestone=m).first()
        expected={'milestone_id':m.pk,'name':m.name,'evidence_id':m.evidence_id,'evidence_sha256':m.evidence.sha256}
        if not receipt or receipt.payload!=expected:raise ValidationError('Finance notification receipt missing or inconsistent for milestone #'+str(m.pk))
        result.append([m.pk,receipt.pk,receipt.operation_key])
    return {'milestones':result}


@transaction.atomic
def confirm_finance(actor,case_id,dossier_id,milestone_ids,inventory_complete,evidence_id,note,expected):
    case=lock_case(actor,case_id,'delivery.finance_confirm',expected);d=dossier_for(case,dossier_id);ensure_open(d);note_required(note)
    snapshot=finance_inputs(d)
    if inventory_complete is not True or not isinstance(milestone_ids,list) or any(type(i) is not int for i in milestone_ids) or sorted(milestone_ids)!=[x[0] for x in snapshot['milestones']]:
        raise ValidationError('Finance must explicitly attest the complete milestone inventory and its exact notification receipts; unknown is not empty')
    return record(actor,case,d,'finance_confirmation',subject(case,evidence_id),{'inventory_complete':True,'note':note},snapshot)


@observed_fact
def qualified_hypercare(d):
    h=latest(d,'hypercare');require(h.actor,d.case,'delivery.manage')
    if h.snapshot!=hypercare_inputs(d) or h.snapshot['qualified'] is not True:raise ValidationError('Current qualified hypercare evidence required; unknown/failed criteria cannot close')
    return h


@observed_fact
def received_handover(d):
    # Every selected Support/Operations recipient must record actual receipt without unresolved gaps.
    bindings=DeliveryDocumentBinding.objects.filter(dossier=d,purpose='handover').order_by('-pk')
    binding=bindings.first()
    if not binding or binding.snapshot!=handover_inputs(d,binding.data):raise ValidationError('Current exact Support/Operations handover required')
    from apps.documents.controlled import current_version
    current_version(d.case,binding.version_id)
    from apps.documents.models import Publication
    publication=Publication.objects.filter(version=binding.version).order_by('-pk').first()
    if not publication:raise ValidationError('Handover has not been reserved/delivered')
    acknowledgements=[]
    for recipient in publication.recipient_ids:
        receipt=PublicationReceipt.objects.filter(publication=publication,recipient_id=recipient).first()
        ack=d.records.filter(kind='handover',data__receipt_id=receipt.pk if receipt else -1).order_by('-pk').first()
        if not ack or ack.data['status']!='received' or ack.snapshot!=binding.snapshot:raise ValidationError('Support/Operations receipt or gap resolution missing')
        require(ack.actor,d.case,'delivery.support_receive');require(ack.actor,d.case,'document.receive:internal');acknowledgements.append(ack.pk)
    if not acknowledgements:raise ValidationError('No Support/Operations destination received the handover')
    return acknowledgements


@observed_fact
def current_retrospective(d,version_id):
    if type(version_id) is not int:raise ValidationError('Select the exact retrospective meeting version')
    meeting=MeetingVersion.objects.filter(pk=version_id,meeting__case=d.case,kind='retrospective').first()
    if not meeting or meeting.meeting.current_id!=meeting.pk or meeting.occurred_at<aware(valid_release(d).data['released_at']):
        raise ValidationError('Current post-release retrospective meeting required')
    from django.utils import timezone
    if meeting.occurred_at>timezone.now():raise ValidationError('Retrospective must have occurred')
    require(meeting.created_by,d.case,'meeting.record')
    return meeting


@observed_fact
def current_finance_confirmation(d):
    finance=latest(d,'finance_confirmation');require(finance.actor,d.case,'delivery.finance_confirm')
    if finance.snapshot!=finance_inputs(d):raise ValidationError('Finance notification inventory changed; obtain current coverage confirmation')
    return finance


def closure_selection(data,optional=False):
    if not isinstance(data,dict) or set(data)!={'retrospective_id','report_evidence_id'} or any(
        not (optional and v is None) and (type(v) is not int or not 1<=v<=9223372036854775807) for v in data.values()):
        raise ValidationError('Exact integer retrospective/report references'+(' or unprovided values' if optional else '')+' required')
    return data


def closure_requirements(d,data=None):
    """Independent read-only facts; never an approval, inferred event or empty-inventory attestation."""
    from django.core.exceptions import PermissionDenied
    from django.utils import timezone
    data=data if data is not None else {'retrospective_id':None,'report_evidence_id':None}
    closure_selection(data,optional=True)
    checks=[]
    def check(key,title,fn,next_action,selection=None):
        if selection and data[selection] is None:
            checks.append({'key':key,'title':title,'status':'unknown','summary':next_action,'references':[]});return
        try:
            result=fn();refs=result if isinstance(result,list) else [result.pk]
            checks.append({'key':key,'title':title,'status':'current','summary':'Current recorded evidence is available','references':refs})
        except (ValidationError,PermissionDenied) as exc:
            checks.append({'key':key,'title':title,'status':'held','summary':next_action,'references':[],
                'finding':'; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)})
    closed=latest(d,'closure',False)
    def context():
        dossier_for(d.case,d.pk);return d
    check('context','Current project scope',context,'Review the current project baseline and any recorded closure')
    if closed and checks[0]['status']=='current':
        checks[0].update(status='closed',summary='Project closure is recorded. Preparation cannot reopen this delivery.',references=[d.pk,closed.pk])
    check('go_live','Go-live acceptance',lambda:accepted_go_live(d),'Review current client delivery and actual signatures')
    check('hypercare','Release stability',lambda:qualified_hypercare(d),'Resolve current stability criteria and observations')
    check('archive','Project archive',lambda:current_archive(d),'Complete the current declared archive inventory')
    check('handover','Support handover',lambda:received_handover(d),'Resolve actual recipient receipt or handover gaps')
    check('retrospective','Retrospective',lambda:current_retrospective(d,data['retrospective_id']),'Select the current record of an actual post-release retrospective','retrospective_id')
    check('finance','Finance notification coverage',lambda:current_finance_confirmation(d),'Ask an authorised Finance person to confirm the exact milestone notification inventory')
    check('report','PM closure report',lambda:subject(d.case,data['report_evidence_id'],'closure_report'),'Select the PM closure report evidence','report_evidence_id')
    return {'as_of':timezone.now().isoformat(),'checks':checks,'ready_to_prepare':all(c['status']=='current' for c in checks),
        'selected':data,'recorded_closure_id':closed.pk if closed else None,
        'closure_approved':False,'debt_waived':False,'deployment_authorized':False}


@observed_fact
def closure_inputs(d,data):
    closure_selection(data)
    accepted=accepted_go_live(d);h=qualified_hypercare(d);archive=current_archive(d)
    acknowledgements=received_handover(d);meeting=current_retrospective(d,data['retrospective_id']);finance=current_finance_confirmation(d)
    report=subject(d.case,data['report_evidence_id'],'closure_report')
    return {'acceptance_id':accepted.pk,'hypercare_id':h.pk,'archive_id':archive.pk,'handover_ids':acknowledgements,
        'retrospective_id':meeting.pk,'finance_confirmation_id':finance.pk,'report_evidence_id':report.pk,
        'debt_waived':False,'deployment_authorized':False}


@transaction.atomic
def decide_closure(actor,case_id,version_id,verdict,evidence_id,note,expected):
    case=lock_case(actor,case_id,'delivery.closure_decide',expected);note_required(note)
    binding=DeliveryDocumentBinding.objects.filter(version_id=version_id,dossier__case=case,purpose='closure').first()
    if not binding:raise ValidationError('Select this case exact prepared closure report')
    d=dossier_for(case,binding.dossier_id);ensure_open(d)
    if verdict not in ['approve','return','reject']:raise ValidationError('Choose explicit closure verdict')
    authority=decision_authority(actor,case,'Head of PMO',verdict)
    from apps.documents.controlled import current_version
    current_version(case,version_id)
    return record(actor,case,d,'closure_decision',subject(case,evidence_id),{'verdict':verdict,'authority':authority,'note':note,'version_id':version_id},binding.snapshot)


def current_closure_approval(d,version_id=None):
    decision=latest(d,'closure_decision');require(decision.actor,d.case,'delivery.closure_decide')
    binding=DeliveryDocumentBinding.objects.filter(version_id=decision.data['version_id'],dossier=d,purpose='closure').first()
    if not binding or version_id is not None and binding.version_id!=version_id:
        raise ValidationError('Exact current closure report and prescribed decision required')
    if decision.data['verdict']!='approve' or decision.data['authority']!=decision_authority(decision.actor,d.case,'Head of PMO') or decision.snapshot!=closure_inputs(d,binding.data):
        raise ValidationError('Current Head of PMO approval of exact closure sources required')
    from apps.documents.controlled import current_version
    current_version(d.case,binding.version_id)
    return decision,binding


@transaction.atomic
def finalize_closure(actor,case_id,dossier_id,expected):
    case=lock_case(actor,case_id,'delivery.manage',expected);d=dossier_for(case,dossier_id);ensure_open(d);decision_authority(actor,case,'PM')
    decision,binding=current_closure_approval(d)
    return record(actor,case,d,'closure',decision.evidence,{'decision_id':decision.pk,'version_id':binding.version_id,'archive_state':'immutable_index_recorded'},decision.snapshot)
