from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.services import lock_case, event, bump
from apps.pmo.services import subject
from .models import Review

@transaction.atomic
def review_document(actor, case_id, evidence_id, verdict, note, expected):
    case = lock_case(actor, case_id, 'document.review', expected)
    evidence = subject(case, evidence_id)
    if verdict not in ['accepted', 'returned'] or not note.strip():
        raise ValidationError('Review needs a verdict and rationale')
    review = Review.objects.create(case=case, evidence=evidence, actor=actor, verdict=verdict, note=note)
    event(actor, case, 'document.reviewed', review=review.pk, evidence=evidence.pk, sha256=evidence.sha256, verdict=verdict)
    bump(case)
    return review
