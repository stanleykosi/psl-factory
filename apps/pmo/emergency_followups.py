"""Link Emergency actuals to new ordinary scope/cost work without retroactive authority."""
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.services import lock_case,event,bump
from apps.policy.services import decision_authority
from .emergencies import outcome_for
from .commercial import note_required
from .changes import log_change,impact,current_change,require_open_version
from .change_execution import validate_authorization
from .models import EmergencyFollowup,EmergencyFollowupCompletion,ChangeClosure,BaselineAdoption,ChangeRequest


@transaction.atomic
def create_followup(actor,case_id,outcome_id,reference,category,module,description,reason,evidence_id,expected):
    case=lock_case(actor,case_id,'emergency.followup',expected);outcome=outcome_for(case,outcome_id)
    if category not in ['Normal','Standard']:raise ValidationError('Follow-up must use an ordinary Normal or Standard change')
    decision_authority(actor,case,'PM');note_required(reason)
    if ChangeRequest.objects.filter(case=case,reference=reference).exists():raise ValidationError('Use a new unique follow-up reference')
    version=log_change(actor,case.pk,reference,category,module,description,reason,evidence_id,case.revision)
    result=EmergencyFollowup.objects.create(outcome=outcome,version=version,note=reason,actor=actor)
    event(actor,case,'emergency.ordinary_followup_created',followup=result.pk,outcome=outcome.pk,version=version.pk,
        historical_implementation_reused=False)
    return result


@transaction.atomic
def link_followup_revision(actor,case_id,followup_id,version_id,note,expected):
    case=lock_case(actor,case_id,'emergency.followup',expected);decision_authority(actor,case,'PM');note_required(note)
    old=EmergencyFollowup.objects.filter(pk=followup_id,outcome__profile__version__change__case=case).first()
    if not old or EmergencyFollowupCompletion.objects.filter(followup=old).exists() or EmergencyFollowup.objects.filter(supersedes=old).exists():
        raise ValidationError('Select an open unsuperseded follow-up')
    version=current_change(case,version_id);require_open_version(version)
    if version.change_id!=old.version.change_id or version.number<=old.version.number or version.category not in ['Normal','Standard']:
        raise ValidationError('Select a newer ordinary revision of the same follow-up request')
    if EmergencyFollowup.objects.filter(version=version).exists():raise ValidationError('Revision already linked')
    result=EmergencyFollowup.objects.create(outcome=old.outcome,version=version,supersedes=old,note=note,actor=actor)
    event(actor,case,'emergency.followup_revision_linked',followup=result.pk,supersedes=old.pk,version=version.pk);bump(case);return result


@transaction.atomic
def complete_followup(actor,case_id,followup_id,closure_id,note,expected):
    case=lock_case(actor,case_id,'emergency.followup',expected);decision_authority(actor,case,'PM');note_required(note)
    followup=EmergencyFollowup.objects.filter(pk=followup_id,outcome__profile__version__change__case=case).first()
    closure=ChangeClosure.objects.select_related('authorization__version__change','authorization__commercial').filter(pk=closure_id).first()
    if not followup or not closure or closure.authorization.version_id!=followup.version_id:
        raise ValidationError('Select the exact ordinary follow-up closure in this case')
    if EmergencyFollowupCompletion.objects.filter(followup=followup).exists():raise ValidationError('Follow-up completion already recorded')
    if EmergencyFollowup.objects.filter(supersedes=followup).exists():raise ValidationError('Follow-up was superseded; complete its current linked revision')
    validate_authorization(case,closure.authorization)
    _,flags=impact(followup.version)
    if flags['cost_impact'] and not BaselineAdoption.objects.filter(revision_id=closure.authorization.commercial_id).exists():
        raise ValidationError('Cost follow-up requires the ordinary approved and signed commercial adoption')
    result=EmergencyFollowupCompletion.objects.create(followup=followup,closure=closure,note=note,actor=actor)
    event(actor,case,'emergency.ordinary_followup_completed',completion=result.pk,closure=closure.pk,
        retrospective_obligations_unchanged=True);bump(case);return result
