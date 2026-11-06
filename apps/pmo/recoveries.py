"""Explicit present authority for unchanged historical evidence, never retroactive approval."""
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from apps.core.services import lock_case, event, bump
from apps.identity.services import require
from apps.policy.services import active_component, reference_values, decision_authority, resolve
from apps.documents.controlled import baseline_manifest
from .models import (AuthorityRecoveryRequest, AuthorityRecoveryDecision, AuthorityRecoveryRecord,
    BaselineAdoption, CommercialDocumentBinding, ChangeAuthorization)
from .commercial import note_required, valid_approvals, latest_decisions, terminal
from .services import subject

KINDS = {'emergency_outcome':'outcome', 'signed_adoption':'adoption'}


def recovery_policy(case,kind):
    config=active_component('D05.revision_invalidation_rules',case)
    rules=reference_values(config)[0].get('historical_authority',{})
    if kind not in rules:raise ValidationError('Historical authority policy is unconfigured for '+kind)
    return config,rules[kind]


def structural_source(case,kind,pk):
    """Checks all non-authority predicates. These may never be recovered by a roster decision."""
    if kind=='emergency_outcome':
        from .emergencies import outcome_for,preauthorization_inputs
        o=outcome_for(case,pk);a=o.authorization
        if not a or a.created_at>o.implemented_at:
            raise ValidationError('Originally missing preauthorization cannot be recovered or backdated')
        inputs=preauthorization_inputs(case,o.profile,check_authority=False,historical=True)
        if inputs!=a.snapshot:raise ValidationError('Emergency source or D01 policy changed; authority recovery cannot replace evidence')
        decisions=list(o.profile.decisions.filter(pk__in=a.snapshot['decision_ids']).order_by('pk'))
        people=[(o.profile.actor,'emergency.manage','PM'),(a.actor,'emergency.authorize',None)]
        people += [(d.actor,'emergency.decide',d.authority_role) for d in decisions]
        return {'kind':kind,'id':o.pk,'authorization_id':a.pk,'authorization':a.snapshot,
            'implemented_at':o.implemented_at.isoformat(),'logged_at':o.created_at.isoformat(),
            'evidence_ids':sorted({o.evidence_id,o.profile.evidence_id,o.profile.version.evidence_id,o.profile.version.incident_id,*[d.evidence_id for d in decisions]})},people
    if kind!='signed_adoption':raise ValidationError('Unsupported recovery target')
    a=BaselineAdoption.objects.select_related('revision__dossier','response__receipt__publication__version').filter(pk=pk,revision__dossier__case=case).first()
    if not a:raise ValidationError('Choose this case signed adoption')
    if a.after!=baseline_manifest(case):raise ValidationError('Signed baseline changed; historical recovery cannot replace the active baseline')
    revision=a.revision
    binding=CommercialDocumentBinding.objects.get(version=a.response.receipt.publication.version)
    ids=valid_approvals(revision,check_authority=False)
    if terminal(revision) or binding.revision_id!=revision.pk or binding.decision_ids!=ids:
        raise ValidationError('Signed commercial evidence changed; authority recovery cannot replace approvals')
    people=[(d.actor,'commercial.decide',d.role) for d in latest_decisions(revision).values()]
    people += [(a.actor,'baseline.sign',None)]
    auth=ChangeAuthorization.objects.filter(commercial=revision).first()
    change=None
    if auth:
        from .changes import authorization_inputs
        from .standard_changes import validate_snapshot
        assessment_ids,flags,decision_ids=authorization_inputs(case,auth.version,a.after,check_authority=False)
        validate_snapshot(case,auth,flags)  # Standard catalogue authority has its own controls.
        if assessment_ids!=auth.assessment_ids or decision_ids!=auth.decision_ids:
            raise ValidationError('Change evidence changed; obtain a new change revision')
        people += [(d.actor,'change.decide',d.role) for d in auth.version.decisions.filter(pk__in=decision_ids)]
        people += [(auth.actor,'change.authorize',None)]
        change={'authorization_id':auth.pk,'assessment_ids':assessment_ids,'decision_ids':decision_ids,'preapproval':auth.preapproval_snapshot}
    return {'kind':kind,'id':a.pk,'after':a.after,'sources':revision.sources,'decision_ids':ids,
        'response_id':a.response_id,'receipt_id':a.response.receipt_id,'signed_at':a.created_at.isoformat(),
        'change':change,'evidence_ids':sorted({*revision.sources.values(),a.response.evidence_id})},people


def target_snapshot(case,kind,pk):
    source,people=structural_source(case,kind,pk)
    config,rule=recovery_policy(case,kind)
    from apps.identity.models import Grant
    states=[]
    for actor,action,role in people:
        try:authority=decision_authority(actor,case,role) if role else None;finding=None
        except (ValidationError,PermissionDenied) as exc:authority=None;finding=str(exc)
        states.append({'user_id':actor.pk,'action':action,'role':role,'active':actor.is_active,
            'granted':Grant.objects.filter(case=case,user=actor,action=action,active=True).exists(),
            'authority':authority,'finding':finding})
    policies={}
    for component in ['D05.role_principal_assignments','D05.delegation_rules','D05.decision_action_matrix']:
        r=resolve(component,case);policies[component]=[r.status,r.configuration.pk if r.configuration else None]
    return {'source':source,'authority_state':states,'authority_policies':policies,
        'recovery_policy_id':config.pk,'required_roles':rule['roles']}


def request_for(case,pk):
    r=AuthorityRecoveryRequest.objects.filter(case=case,pk=pk).first()
    if not r:raise ValidationError('Recovery request must belong to this case')
    return r


def request_target(r):return ('emergency_outcome',r.outcome_id) if r.outcome_id else ('signed_adoption',r.adoption_id)


def current_request(case,r):
    kind,pk=request_target(r)
    if r.snapshot!=target_snapshot(case,kind,pk):raise ValidationError('Recovery source, authority or policy changed; capture a fresh request')


@transaction.atomic
def request_recovery(actor,case_id,kind,pk,evidence_id,note,expected):
    case=lock_case(actor,case_id,'authority.request',expected);note_required(note)
    if kind not in KINDS:raise ValidationError('Choose a supported historical target')
    snapshot=target_snapshot(case,kind,pk)
    result=AuthorityRecoveryRequest.objects.create(case=case,**{KINDS[kind]+'_id':pk},snapshot=snapshot,
        evidence=subject(case,evidence_id),note=note,actor=actor)
    event(actor,case,'authority.recovery_requested',request=result.pk,kind=kind,target=pk);bump(case);return result


@transaction.atomic
def decide_recovery(actor,case_id,request_id,role,verdict,evidence_id,note,expected):
    case=lock_case(actor,case_id,'authority.decide',expected);r=request_for(case,request_id);current_request(case,r)
    if AuthorityRecoveryRecord.objects.filter(request=r).exists():raise ValidationError('Recovery is recorded; preserve its decisions')
    if role not in r.snapshot['required_roles'] or verdict not in ['approve','return','reject']:raise ValidationError('Use a configured recovery role and explicit verdict')
    authority=decision_authority(actor,case,role,verdict);note_required(note)
    d=AuthorityRecoveryDecision.objects.create(request=r,role=role,verdict=verdict,authority=authority,evidence=subject(case,evidence_id),note=note,actor=actor)
    event(actor,case,'authority.recovery_decision',decision=d.pk,request=r.pk,role=role,verdict=verdict);bump(case);return d


def recovery_decisions(case,r):
    latest={d.role:d for d in r.decisions.order_by('pk')}
    result=[]
    for role in r.snapshot['required_roles']:
        d=latest.get(role)
        if not d or d.verdict!='approve':raise ValidationError('Current recovery approval required: '+role)
        require(d.actor,case,'authority.decide')
        if decision_authority(d.actor,case,role)!=d.authority:raise ValidationError('Recovery decision authority changed')
        result.append(d.pk)
    return result


@transaction.atomic
def finalize_recovery(actor,case_id,request_id,expected):
    case=lock_case(actor,case_id,'authority.finalize',expected);r=request_for(case,request_id);current_request(case,r)
    if AuthorityRecoveryRecord.objects.filter(request=r).exists():raise ValidationError('Recovery already recorded')
    result=AuthorityRecoveryRecord.objects.create(request=r,decision_ids=recovery_decisions(case,r),actor=actor)
    event(actor,case,'authority.recovered_for_current_evidence',record=result.pk,request=r.pk,backdated=False);bump(case);return result


def active_recovery(case,kind,pk):
    if kind not in KINDS:return None
    # A later request explicitly supersedes prior recovery, including an unresolved/rejected request.
    r=AuthorityRecoveryRequest.objects.filter(case=case,**{KINDS[kind]+'_id':pk}).order_by('-pk').first()
    if not r:return None
    record=AuthorityRecoveryRecord.objects.filter(request=r).first()
    if not record:return None
    try:
        current_request(case,r);require(record.actor,case,'authority.finalize');require(r.actor,case,'authority.request')
        if recovery_decisions(case,r)!=record.decision_ids:return None
    except (ValidationError,PermissionDenied):return None
    return record
