from django.core.exceptions import ValidationError, PermissionDenied
from apps.pmo.changes import current_change, impact, required_roles
from apps.pmo.standard_changes import evaluate_standard


class LocalStandardChangeAdapter:
    """Exact local projection; PM attestation is not remote verification."""
    def investigate(self, case, version_id):
        version = current_change(case, version_id)
        if version.category != 'Standard':
            raise ValidationError('Select a Standard change revision')
        result = {'version_id': version.pk, 'source_evidence_ids': [version.evidence_id],
            'findings': [], 'covered_roles': [], 'remaining_roles': [], 'snapshot': None}
        try:
            ids, flags = impact(version)
            result['assessment_ids'] = ids
            result['impact'] = flags
            result['source_evidence_ids'] += list(version.assessments.filter(pk__in=ids).values_list('evidence_id', flat=True))
            result['remaining_roles'] = required_roles(flags)
            covered, snapshot = evaluate_standard(case, version, flags)
            result['covered_roles'] = covered
            result['snapshot'] = snapshot
            result['source_evidence_ids'].append(snapshot['procedure_evidence_id'])
            from apps.pmo.models import StandardBinding, StandardPreapproval
            result['source_evidence_ids'] += list(StandardPreapproval.objects.filter(pk__in=snapshot['preapproval_ids']).values_list('evidence_id',flat=True))
            result['source_evidence_ids'].append(StandardBinding.objects.get(pk=snapshot['binding_id']).evidence_id)
            result['remaining_roles'] = [r for r in required_roles(flags) if r not in covered]
        except (ValidationError, PermissionDenied) as exc:
            result['findings'] = exc.messages if isinstance(exc,ValidationError) else [str(exc)]
        result['source_evidence_ids'] = sorted(set(result['source_evidence_ids']))
        return result
