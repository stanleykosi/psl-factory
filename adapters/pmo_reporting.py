from typing import Protocol
from django.core.exceptions import ValidationError
from apps.pmo.models import Meeting, ActionItem, Milestone, GateRecord, Issue, ChangeRequest
from apps.pmo.models import EmergencyDeadlineSignal, EmergencyProfile, EmergencyDecision, EmergencyAuthorization, EmergencyOutcome, EmergencyReview, EmergencyRetrospectiveDecision, EmergencyRetrospectiveRecord, StandardPreapproval, StandardBinding, ChangeAssessment, ChangeDecision, ChangeAuthorization, ChangeExecutionEvent, ChangeClosure
from apps.pmo.models import EscalationProfile, EscalationRequest, EscalationDecision, EscalationSignal
from apps.documents.models import PublicationReceipt
from apps.pmo.meetings import action_timing

class PMOReportingAdapter(Protocol):
    def read(self,case,start_at,end_at,as_of): ...

class LocalPMOReportingAdapter:
    """Actual local PMO records only; no claim of complete Engineering/Finance source coverage."""
    def read_client_facts(self,case,start_at,end_at,as_of):
        """Explicit P41 fact subset; no optional delivery/RFP/escalation authority histories."""
        meetings=list(Meeting.objects.filter(case=case,current__occurred_at__gte=start_at,current__occurred_at__lt=end_at).select_related('current').order_by('pk')[:201])
        actions=list(ActionItem.objects.filter(case=case).select_related('current__owner').order_by('pk')[:1001])
        milestones=list(Milestone.objects.filter(case=case,completed_at__gte=start_at,completed_at__lt=end_at).order_by('pk')[:1001])
        issues=list(Issue.objects.filter(case=case).select_related('current').order_by('pk')[:1001])
        changes=list(ChangeRequest.objects.filter(case=case).select_related('current').order_by('pk')[:1001])
        if len(meetings)>200 or max(len(actions),len(milestones),len(issues),len(changes))>1000:
            raise ValidationError('Client fact snapshot exceeds its bounded source budget; narrow the operational scope')
        manifest={'source_mode':'weekly_client_facts/v1','meetings':[[m.pk,m.current_id] for m in meetings],
            'actions':[[a.pk,a.current_id] for a in actions],'milestones':[m.pk for m in milestones],
            'issues':[[i.pk,i.current_id] for i in issues],'changes':[[c.pk,c.current_id] for c in changes]}
        return {'manifest':manifest,'meetings':meetings,'actions':actions,'milestones':milestones,'issues':issues,'changes':changes,
            'timings':{a.pk:action_timing(a.current,as_of) for a in actions}}

    def read(self,case,start_at,end_at,as_of):
        meetings=list(Meeting.objects.filter(case=case,current__occurred_at__gte=start_at,current__occurred_at__lt=end_at).select_related('current').order_by('pk')[:201])
        actions=list(ActionItem.objects.filter(case=case).select_related('current__owner').order_by('pk')[:1001])
        milestones=list(Milestone.objects.filter(case=case,completed_at__gte=start_at,completed_at__lt=end_at).order_by('pk')[:1001])
        gates=list(GateRecord.objects.filter(candidate__case=case).order_by('pk')[:1001])
        issues=list(Issue.objects.filter(case=case).select_related('current').order_by('pk')[:1001])
        changes=list(ChangeRequest.objects.filter(case=case).select_related('current').order_by('pk')[:1001])
        change_history={
            'emergency_signals':list(EmergencyDeadlineSignal.objects.filter(outcome__profile__version__change__case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'emergency_profiles':list(EmergencyProfile.objects.filter(version__change__case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'emergency_decisions':list(EmergencyDecision.objects.filter(profile__version__change__case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'emergency_authorizations':list(EmergencyAuthorization.objects.filter(profile__version__change__case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'emergency_outcomes':list(EmergencyOutcome.objects.filter(profile__version__change__case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'emergency_reviews':list(EmergencyReview.objects.filter(outcome__profile__version__change__case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'emergency_retrospective_decisions':list(EmergencyRetrospectiveDecision.objects.filter(review__outcome__profile__version__change__case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'emergency_reconciliations':list(EmergencyRetrospectiveRecord.objects.filter(outcome__profile__version__change__case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'standard_preapprovals':list(StandardPreapproval.objects.filter(case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'standard_bindings':list(StandardBinding.objects.filter(version__change__case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'assessments':list(ChangeAssessment.objects.filter(version__change__case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'decisions':list(ChangeDecision.objects.filter(version__change__case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'authorizations':list(ChangeAuthorization.objects.filter(version__change__case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'execution':list(ChangeExecutionEvent.objects.filter(authorization__version__change__case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'closures':list(ChangeClosure.objects.filter(authorization__version__change__case=case).order_by('pk').values_list('pk',flat=True)[:1001])}
        escalation_history={
            'profiles':list(EscalationProfile.objects.filter(state__issue__case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'requests':list(EscalationRequest.objects.filter(profile__state__issue__case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'decisions':list(EscalationDecision.objects.filter(request__profile__state__issue__case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'signals':list(EscalationSignal.objects.filter(profile__state__issue__case=case).order_by('pk').values_list('pk',flat=True)[:1001]),
            'receipts':list(PublicationReceipt.objects.filter(publication__version__escalationdocumentbinding__request__profile__state__issue__case=case).order_by('pk').values_list('pk',flat=True)[:1001])}
        if len(meetings)>200 or max(len(actions),len(milestones),len(gates),len(issues),len(changes))>1000:
            raise ValidationError('PMO snapshot exceeds its bounded source budget; narrow the operational scope')
        if any(len(ids)>1000 for ids in change_history.values()):
            raise ValidationError('PMO change history exceeds its bounded reporting source budget')
        if any(len(ids)>1000 for ids in escalation_history.values()):
            raise ValidationError('PMO escalation history exceeds its bounded reporting source budget')
        latest_gates={}
        for gate in gates:
            verified=gate.verifications.order_by('-pk').first()
            latest_gates[(gate.candidate_id,gate.kind)]={'record':gate.pk,'verification':verified.pk if verified else None}
        from .delivery import reporting_manifest
        delivery_history=reporting_manifest(case)
        from .rfp import reporting_manifest as rfp_manifest
        rfp_history=rfp_manifest(case)
        from apps.pmo.change_impacts import timeline_snapshot
        change_timeline=timeline_snapshot(case)
        manifest={'normal_change_timeline':change_timeline,'rfp_history':rfp_history,'delivery_history':delivery_history,'meetings':[[m.pk,m.current_id] for m in meetings],'actions':[[a.pk,a.current_id] for a in actions],
            'milestones':[m.pk for m in milestones],'gates':list(latest_gates.values()),
            'issues':[[i.pk,i.current_id] for i in issues],'changes':[[c.pk,c.current_id] for c in changes], 'change_history':change_history,
            'escalation_history':escalation_history}
        return {'change_timeline':change_timeline,'rfp_history':rfp_history,'manifest':manifest,'meetings':meetings,'actions':actions,'milestones':milestones,'issues':issues,'changes':changes,
            'escalation_history':escalation_history,'delivery_history':delivery_history,
            'timings':{a.pk:action_timing(a.current,as_of) for a in actions}}
