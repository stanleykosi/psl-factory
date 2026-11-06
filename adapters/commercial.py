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
        }
