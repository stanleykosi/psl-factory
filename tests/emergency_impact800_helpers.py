"""Presigned synthetic role roster; native original authorization, never repair."""
from datetime import timedelta
from django.utils import timezone
from tests.helpers import setup_case,project_evidence,activate,rev
from tests.signature_helpers import packet_for
from tests.document_helpers import artifact
from apps.core.services import add_evidence
from apps.policy.services import register_reference,transition
from apps.policy.change_drafts import draft_standard_policy
from apps.pmo import emergencies as native,recoveries
from apps.pmo.services import prepare_baseline,decide,sign_baseline
from apps.pmo.changes import log_change
from apps.pmo.gates import register_candidate,record_gate,verify_gate

RULE={'roles':['PMO Lead'],'scope':'authority_only','original_times':'preserve','financial_release_controls':'independent'}
def policy(f):
    return artifact(f['a'],f['c'],'D05.revision_invalidation_rules','schema:psl/commercial-revision/v2',
        {'unchanged_subject_reuse_roles':[],'changed_cost_requires_full_chain':True,'historical_authority':{'emergency_outcome':RULE}},f['e']['policy_decision'])
def fixture(username='impact800',mode='authorized'):
    from adapters.pmo_gates import SyntheticGateAdapter
    from apps.pmo.approvals import candidate_requests
    from apps.pmo.models import CommercialSignatureReaffirmation,AuthorityRecoveryDecision,AuthorityRecoveryRecord,RFPCase,BaselineAdoption,EmergencyRetrospectiveRecord,EmergencyFollowup
    if SyntheticGateAdapter.read.__module__!='adapters.pmo_gates' or SyntheticGateAdapter.name!='synthetic-gate-source-v1':raise AssertionError('Canonical synthetic adapter only')
    a,c=setup_case(username=username)
    if c.synthetic is not True:raise AssertionError('Explicit synthetic case required')
    e=project_evidence(a,c);refs=[]
    for role in ['PM','Head of PMO','CEO','PMO Lead','Engineering Lead','Security Lead','CTO','Product']:
        r=register_reference(a,c.pk,'impact800:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':a.pk},e['policy_decision'].pk);refs.append(r.ref)
    activate(a,c,'D05.role_principal_assignments',refs,e['policy_decision'])
    prepare_baseline(a,c.pk,e['plan'].pk,e['costing'].pk,e['sow'].pk,rev(c))
    for role in ['PM','Head of PMO','CEO','PMO Lead']:decide(a,c.pk,role,rev(c))
    packet_for(a,c,e);sign_baseline(a,c.pk,e['signature'].pk,rev(c))
    for kind in ['incident','incident_classification','change_request','emergency_decision','change_implementation']:
        e[kind]=add_evidence(a,c.pk,kind,'Explicit synthetic '+kind,'synthetic:impact800')
    version=log_change(a,c.pk,'EM-800','Emergency','API','Synthetic incident','Explicit original evidence',e['change_request'].pk,rev(c),e['incident'].pk)
    candidate=register_candidate(a,c.pk,'impact800-candidate',e['requirements'].pk,rev(c))
    profile=native.capture_profile(a,c.pk,version.pk,candidate.pk,True,True,e['incident_classification'].pk,'Explicit synthetic P1',rev(c))
    value={'mode':'coexist','incident_lead_role':'Engineering Lead','incident_engineering_overlap':'explicit_same_person','exception_roles':[],'priority_basis':'explicit_incident_p1_attestation'}
    cfg=draft_standard_policy(a,c.pk,'D01.emergency_glpi_relationship',value,e['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
    artifact(a,c,'D01.satisfied_gate_map','schema:psl/change-satisfied-gates/v2',{'emergency':{'preauthorization_roles':['Incident Lead','Engineering Lead'],'p1_additional_roles':['CTO'],'retrospective_roles':['Product','Engineering Lead'],'financial_controls':'independent','deployment_dispatch':'not_granted'}},e['policy_decision'])
    for role in ['Incident Lead','Engineering Lead','CTO']:
        native.decide_emergency(a,c.pk,profile.pk,role,'Engineering Lead','approve',e['emergency_decision'].pk,'Explicit original synthetic approval',rev(c))
    for kind in ['glpi_security','glpi_cto','glpi_ceo']:
        if candidate_requests(candidate,kind):raise AssertionError('Never override department-owned requests')
        gate=record_gate(a,c.pk,candidate.pk,kind,'synthetic:'+kind,e['change_request'].pk,rev(c))
        verify_gate(a,c.pk,gate.pk,rev(c),adapter=SyntheticGateAdapter())
    if mode not in ('authorized','absent','late'):raise ValueError('Explicit test chronology')
    actual_before=timezone.now() if mode=='late' else None
    auth=None if mode=='absent' else native.authorize_emergency(a,c.pk,profile.pk,rev(c))
    actual=actual_before or timezone.now()
    outcome=native.capture_outcome(a,c.pk,profile.pk,auth.pk if auth else None,actual,e['change_implementation'].pk,'Synthetic reported outcome',rev(c))
    if mode=='authorized' and auth.created_at>outcome.implemented_at:raise AssertionError('Original preauthorization must precede actual outcome')
    if auth is not None and auth.snapshot!=native.preauthorization_inputs(c,profile,check_authority=False,historical=True):raise AssertionError('Original native snapshot must match unchanged structural evidence')
    f={'a':a,'c':c,'e':e,'outcome':outcome,'authorization':auth,'profile':profile,'d01':cfg};f['policy']=policy(f)
    if mode=='authorized':f['request']=recoveries.request_recovery(a,c.pk,'emergency_outcome',outcome.pk,e['policy_decision'].pk,'Request only, no recovered authority',rev(c))
    if CommercialSignatureReaffirmation.objects.filter(packet__case=c).exists() or AuthorityRecoveryDecision.objects.filter(request__case=c).exists() or AuthorityRecoveryRecord.objects.filter(request__case=c).exists():raise AssertionError('No repair or recovery finalization')
    if RFPCase.objects.filter(case=c).exists() or BaselineAdoption.objects.filter(revision__dossier__case=c).exists():raise AssertionError('No conversion or adoption fixture')
    if EmergencyRetrospectiveRecord.objects.filter(outcome=outcome).exists() or EmergencyFollowup.objects.filter(outcome=outcome).exists():raise AssertionError('No retrospective or followup fixture')
    return f
