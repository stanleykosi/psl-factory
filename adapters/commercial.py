from apps.core.models import Evidence


class LocalCommercialAdapter:
    """Read only exact local immutable evidence; no signature-provider authenticity claim."""
    def submission_fields(self, case, revision):
        sow = Evidence.objects.get(case=case, pk=revision.sources['sow'])
        plan = Evidence.objects.get(case=case, pk=revision.sources['plan'])
        return {
            'executive_summary': {'text': 'Commercial proposal revision '+str(revision.number)+'. '+revision.reason, 'evidence_ids': [revision.context_id]},
            'scope': {'text': sow.body, 'evidence_ids': [sow.pk]},
            'timeline': {'text': plan.body, 'evidence_ids': [plan.pk]},
            'risks': {'text': 'Unknown: this commercial packet does not capture a risk assessment. Human review must preserve this coverage limit.', 'evidence_ids': [sow.pk, plan.pk]},
            'dependencies': {'text': 'Unknown: dependencies have not been captured in this commercial packet. Human review must preserve this coverage limit.', 'evidence_ids': [sow.pk, plan.pk]},
            'status': {'text': 'Commercial proposal revision ' + str(revision.number) + ' prepared for outward review. Client acceptance and delivery progress are not established by this document.', 'evidence_ids': [revision.context_id]},
        }
