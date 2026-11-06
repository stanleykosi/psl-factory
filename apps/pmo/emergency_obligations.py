import hashlib
import json
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import lock_case, event
from .models import EmergencyOutcome,EmergencyDeadlineSignal,EmergencyScanCursor
from .emergencies import outcome_for,timing,aware


@transaction.atomic
def scan_outcome(actor,case_id,outcome_id):
    case=lock_case(actor,case_id,'emergency.manage');outcome=outcome_for(case,outcome_id)
    clock=timing(case,outcome);kinds=[]
    if not outcome.authorization_id or outcome.authorization.created_at>outcome.implemented_at:kinds.append('missing_preauthorization')
    if clock['log_late']:kinds.append('late_emergency_log')
    review=outcome.reviews.order_by('-pk').first()
    decisions=[]
    for role in ['Product','Engineering Lead']:
        decision=review.decisions.filter(role=role).order_by('-pk').first() if review else None
        decisions.append(decision)
    due=aware(clock['retrospective_due_at']) if clock['retrospective_due_at'] else None
    if due and timezone.now()>due and any(not d or d.verdict!='approve' or d.created_at>due for d in decisions):
        kinds.append('retrospective_deadline_exception')
    source={'policies':clock['policies'],'review_id':review.pk if review else None,
        'decision_ids':[d.pk if d else None for d in decisions]}
    key=hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    created=[]
    for kind in kinds:
        signal,new=EmergencyDeadlineSignal.objects.get_or_create(outcome=outcome,kind=kind,source_key=key,
            defaults={'snapshot':{'source':source,'timing':clock}})
        if new:
            event(actor,case,'emergency.obligation_signal',signal=signal.pk,outcome=outcome.pk,kind=kind)
            created.append(signal)
    return created


@transaction.atomic
def scan_due(limit=100):
    if type(limit) is not int or not 1<=limit<=1000:raise ValidationError('Emergency scan limit must be 1–1000')
    cursor,_=EmergencyScanCursor.objects.get_or_create(name='emergency-obligations-v1')
    cursor=EmergencyScanCursor.objects.select_for_update().get(pk=cursor.pk)
    outcomes=list(EmergencyOutcome.objects.filter(pk__gt=cursor.last_outcome_id).select_related('profile__version__change','profile__actor').order_by('pk')[:limit])
    if not outcomes and cursor.last_outcome_id:
        cursor.last_outcome_id=0
        outcomes=list(EmergencyOutcome.objects.select_related('profile__version__change','profile__actor').order_by('pk')[:limit])
    count=0
    from django.core.exceptions import PermissionDenied
    for outcome in outcomes:
        try:
            with transaction.atomic():count+=len(scan_outcome(outcome.profile.actor,outcome.profile.version.change.case_id,outcome.pk))
        except (ValidationError,PermissionDenied):pass  # The cursor still advances; UI exposes the source/configuration gap.
        cursor.last_outcome_id=outcome.pk
    cursor.save(update_fields=['last_outcome_id']);return count
