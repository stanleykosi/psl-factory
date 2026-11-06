from typing import Protocol
from django.core.exceptions import ValidationError
from apps.pmo.models import EmergencyRetrospectiveDecision, EmergencyRetrospectiveRecord, EmergencyDeadlineSignal
from apps.pmo.gates import gate_manifest
from apps.policy.services import resolve


class EmergencyEvidenceAdapter(Protocol):
    def read(self,case,outcome)->dict: ...


class LocalEmergencyEvidenceAdapter:
    """Real local source projection; external authority is only as verified by its gate adapter."""
    def read(self,case,outcome):
        if outcome.profile.version.change.case_id!=case.pk:
            raise ValidationError('Outcome is outside the case')
        profile=outcome.profile
        reviews=list(outcome.reviews.order_by('pk')[:101])
        decisions=list(EmergencyRetrospectiveDecision.objects.filter(review__outcome=outcome).order_by('pk')[:201])
        if len(reviews)>100 or len(decisions)>200:
            raise ValidationError('Emergency investigation exceeds bounded history budget')
        components=['D01.emergency_glpi_relationship','D01.satisfied_gate_map','D04.clock_anchor_pause_rules',
            'D04.iana_timezone','D04.working_calendar_ref','D04.deadline_parameters','D05.role_principal_assignments','D05.decision_action_matrix','D05.revision_invalidation_rules']
        policies={}
        for key in components:
            result=resolve(key,case);policies[key]=[result.status,result.configuration.pk if result.configuration else None]
        latest_profile=profile.version.emergency_profiles.order_by('-pk').first()
        pre=list(profile.decisions.order_by('pk')[:201])
        if len(pre)>200:
            raise ValidationError('Emergency preauthorization history exceeds bounded budget')
        reconciled=EmergencyRetrospectiveRecord.objects.filter(outcome=outcome).first()
        from apps.identity.models import Grant
        from django.contrib.auth import get_user_model
        required_grants={(d.actor_id,'emergency.decide') for d in pre}
        required_grants.update((r.actor_id,'emergency.review') for r in reviews)
        required_grants.update((d.actor_id,'emergency.retrospective_decide') for d in decisions)
        if outcome.authorization_id:required_grants.add((outcome.authorization.actor_id,'emergency.authorize'))
        required_grants.add((profile.actor_id,'emergency.manage'))
        from apps.pmo.models import AuthorityRecoveryRequest,AuthorityRecoveryDecision,AuthorityRecoveryRecord,EmergencyFollowupCompletion
        recovery_requests=list(AuthorityRecoveryRequest.objects.filter(outcome=outcome).order_by('pk')[:101])
        if len(recovery_requests)>100:raise ValidationError('Recovery history exceeds source budget')
        recovery_decisions=list(AuthorityRecoveryDecision.objects.filter(request__outcome=outcome).order_by('pk')[:201])
        if len(recovery_decisions)>200:raise ValidationError('Recovery decision history exceeds source budget')
        recovery_records=list(AuthorityRecoveryRecord.objects.filter(request__outcome=outcome).order_by('pk'))
        required_grants.update((r.actor_id,'authority.request') for r in recovery_requests)
        required_grants.update((r.actor_id,'authority.decide') for r in recovery_decisions)
        required_grants.update((r.actor_id,'authority.finalize') for r in recovery_records)
        from apps.pmo.recoveries import active_recovery
        recovered=active_recovery(case,'emergency_outcome',outcome.pk)
        followups=[]
        for f in outcome.followups.select_related('version__change').order_by('pk')[:101]:
            from apps.pmo.changes import impact
            try:assessments,flags=impact(f.version);findings=[]
            except ValidationError as exc:
                assessments=[];flags={k:None for k in ['cost_impact','timeline_impact','client_facing']};findings=exc.messages
            completed=EmergencyFollowupCompletion.objects.filter(followup=f).first()
            followups.append({'id':f.pk,'supersedes_id':f.supersedes_id,'version_id':f.version_id,'current_version_id':f.version.change.current_id,
                'assessment_ids':assessments,'impact':flags,'findings':findings,
                'completion_id':completed.pk if completed else None})
        if len(followups)>100:raise ValidationError('Follow-up source budget exceeded')
        for kind in ['glpi_security','glpi_cto','glpi_ceo']:
            gate=profile.candidate.gates.filter(kind=kind).order_by('-pk').first()
            verification=gate.verifications.order_by('-pk').first() if gate else None
            if verification:required_grants.add((verification.actor_id,'pmo.gate_verify'))
        authority_grants=[[user,action,Grant.objects.filter(case=case,user_id=user,action=action,active=True).exists(),
            get_user_model().objects.filter(pk=user,is_active=True).exists()] for user,action in sorted(required_grants)]
        manifest={'profile_id':profile.pk,'current_profile_id':latest_profile.pk,'change_current_id':profile.version.change.current_id,
            'outcome_id':outcome.pk,'authorization_id':outcome.authorization_id,
            'preauthorization_decision_ids':[d.pk for d in pre],'review_ids':[r.pk for r in reviews],
            'retrospective_decision_ids':[d.pk for d in decisions],'reconciliation_id':reconciled.pk if reconciled else None,
            'gates':gate_manifest(profile.candidate),'policies':policies,'authority_grants':authority_grants,
            'recovery_request_ids':[r.pk for r in recovery_requests],'recovery_decision_ids':[r.pk for r in recovery_decisions],
            'recovery_record_ids':[r.pk for r in recovery_records],'active_recovery_id':recovered.pk if recovered else None,'followups':followups,
            'signal_ids':list(EmergencyDeadlineSignal.objects.filter(outcome=outcome).order_by('pk').values_list('pk',flat=True)[:201])}
        if len(manifest['signal_ids'])>200:
            raise ValidationError('Emergency signal history exceeds bounded source budget')
        sources=sorted({outcome.evidence_id,profile.evidence_id,profile.version.incident_id,profile.version.evidence_id,
            *[d.evidence_id for d in pre],*[r.evidence_id for r in reviews],*[d.evidence_id for d in decisions],
            *[r.evidence_id for r in recovery_requests],*[d.evidence_id for d in recovery_decisions],
            *outcome.followups.values_list('version__evidence_id',flat=True)})
        return {'manifest':manifest,'source_evidence_ids':sources,'review_count':len(reviews),'decision_count':len(decisions)}
