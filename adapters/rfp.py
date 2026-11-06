from apps.documents.models import PublicationReceipt

class LocalRFPAdapter:
    """Exact local inbox evidence. This is not an email/portal submission adapter."""
    def receipts(self,binding):
        rows=list(PublicationReceipt.objects.filter(publication__version=binding.version).order_by('pk'))
        if sorted(r.recipient_id for r in rows)!=sorted(binding.snapshot['route']['recipient_ids']):return []
        if any(r.payload_sha256!=binding.version.payload_sha256 or r.payload!=binding.version.payload for r in rows):return []
        return rows

    def read(self,rfp):
        from django.core.exceptions import ValidationError
        from apps.pmo.models import RFPOutcome,RFPDisposition
        v=rfp.current_response
        evidence={rfp.current_intake.evidence_id}
        if rfp.current_intake.deadline_evidence_id:evidence.add(rfp.current_intake.deadline_evidence_id)
        assignment=rfp.current_intake.assignments.order_by('-pk').first()
        if assignment:evidence.add(assignment.evidence_id)
        for team in ['Engineering','QA','Security','Product']:
            contribution=rfp.current_intake.contributions.filter(team=team).order_by('-pk').first()
            if contribution:evidence.add(contribution.evidence_id)
        outcomes=list(RFPOutcome.objects.filter(submission__response__rfp=rfp).order_by('-pk')[:101])
        if len(outcomes)>100:raise ValidationError('Narrow RFP investigation; outcome history exceeds the 100-record budget')
        evidence.update(o.evidence_id for o in outcomes)
        disposition=RFPDisposition.objects.filter(rfp=rfp).first()
        if disposition and disposition.lessons_id:evidence.add(disposition.lessons_id)
        if v:
            evidence.add(v.evidence_id);evidence.update(v.commercial.sources.values());evidence.update(r['evidence_id'] for r in v.matrix)
            evidence.update(x['evidence'] for x in v.snapshot['inputs'].values())
            from apps.pmo.rfp import public_terms_for
            try:evidence.add(public_terms_for(v).pk)
            except ValidationError:pass  # Legacy delivered history stays readable; new drafts require explicit terms.
            reviews=list(v.reviews.order_by('-pk')[:101])
            if len(reviews)>100:raise ValidationError('Narrow RFP investigation; review history exceeds the 100-record budget')
            evidence.update(x.evidence_id for x in reviews)
        submissions=list(v.submissions.order_by('-pk').values('id','receipt_ids','submitted_at','late')[:101]) if v else []
        if len(submissions)>100:raise ValidationError('Narrow RFP investigation; submission history exceeds the 100-record budget')
        return {'reference':rfp.reference,'response':v.pk if v else None,'citations':list(rfp.case.evidence.filter(pk__in=evidence).values('id','kind','sha256')),
            'submissions':submissions,'outcomes':[{'id':o.pk,'result':o.result,'evidence_id':o.evidence_id,'observed_at':o.observed_at.isoformat()} for o in outcomes],
            'transport':'local_recipient_inbox','external_authenticity_verified':False}


def reporting_manifest(case):
    from django.core.exceptions import ValidationError
    from apps.pmo.models import (RFPCase,RFPIntake,RFPAssignment,RFPContribution,RFPResponse,RFPReview,RFPDocumentBinding,RFPSubmission,RFPOutcome,RFPDisposition)
    from apps.policy.models import PolicyState
    from apps.identity.models import Grant
    r=RFPCase.objects.filter(case=case).first()
    if not r:return {}
    history={}
    for model,query in [(RFPIntake,{'rfp':r}),(RFPAssignment,{'intake__rfp':r}),(RFPContribution,{'intake__rfp':r}),(RFPResponse,{'rfp':r}),
            (RFPReview,{'response__rfp':r}),(RFPDocumentBinding,{'response__rfp':r}),(RFPSubmission,{'response__rfp':r}),(RFPOutcome,{'submission__response__rfp':r}),(RFPDisposition,{'rfp':r})]:
        ids=list(model.objects.filter(**query).order_by('pk').values_list('pk',flat=True)[:1001])
        if len(ids)>1000:raise ValidationError('RFP history exceeds reporting budget; narrow the operational scope')
        history[model._meta.model_name]=ids
    from apps.policy.services import resolve
    policies={}
    for component in ['D05.decision_action_matrix','D05.role_principal_assignments','D11.adapter_configuration_refs','D11.recipient_grant_refs','D11.template_storage_retention_rules']:
        resolved=resolve(component,case);policies[component]=[resolved.status,resolved.configuration.pk if resolved.configuration else None]
    states=[list(x) for x in PolicyState.objects.filter(configuration__case=case).order_by('pk').values_list('pk','state')[:1001]]
    grants=[list(x) for x in Grant.objects.filter(case=case).order_by('pk').values_list('pk','user_id','action','active','user__is_active')[:1001]]
    if max(len(states),len(grants))>1000:raise ValidationError('RFP policy/grant history exceeds reporting budget')
    history.update(current=[r.current_intake_id,r.current_response_id],policies=policies,policy_states=states,grants=grants)
    return history
