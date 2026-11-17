"""Source-bound bid follow-up drafts and the assigned PM's internal review."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.urls import reverse
from django.utils import timezone

from apps.agents.models import AgentRun
from apps.core.models import Audit, Evidence
from apps.core.services import add_evidence, event, lock_case
from apps.core.workbench import granted
from apps.documents.contracts import digest
from apps.identity.services import require

from .models import RFPOutcome
from .rfp import current_assignment
from .rfp_outcomes import historical_submission


PROVIDER = 'deterministic-rfp-followup-v1'
SOURCE_KIND = 'agent_private_rfp_followup'


def current(case, outcome):
    latest = RFPOutcome.objects.filter(submission__response__rfp__case=case).order_by('-pk').first()
    return (latest is not None and latest.pk == outcome.pk and latest.result in {'unknown','pending'} and
            not hasattr(outcome.submission.response.rfp, 'rfpdisposition'))


def authorize(actor, case, outcome):
    require(actor, case, 'case.read')
    require(actor, case, 'rfp.read')
    require(actor, case, 'rfp.prepare')
    if current_assignment(outcome.submission.response.rfp).pm_id != actor.pk:
        raise PermissionDenied('The current assigned project manager reviews this follow-up.')
    if not current(case, outcome):
        raise ValidationError('This outcome no longer needs a customer follow-up.')


def latest_run(actor, case, outcome):
    return AgentRun.objects.filter(case=case,actor=actor,provider=PROVIDER,result__outcome=outcome.pk).order_by('-pk').first()


@transaction.atomic
def draft(actor, case_id, outcome_id, expected):
    case = lock_case(actor, case_id, 'evidence.add', expected)
    require(actor, case, 'agent.rfp')
    outcome = for_case(case, outcome_id)
    authorize(actor, case, outcome)
    if existing := latest_run(actor, case, outcome):
        return existing
    submission = outcome.submission
    response = historical_submission(case, submission)
    text = (f'Hello, could you share an update on bid {response.rfp.reference} and let us know if you need '
            'any further information about the submitted response? Thank you.')
    source = add_evidence(actor, case.pk, SOURCE_KIND, text, 'derived:rfp-followup')
    return AgentRun.objects.create(case=case,actor=actor,evidence=source,provider=PROVIDER,process_id='P49',
        result={'outcome':outcome.pk,'submission':submission.pk,'version':submission.version_id,'dispatched':False})


def for_case(case, outcome_id):
    outcome = RFPOutcome.objects.filter(pk=outcome_id, submission__response__rfp__case=case).select_related('submission__response__rfp').first()
    if outcome is None:
        raise ValidationError('Select a pending or unconfirmed outcome for this bid.')
    return outcome


def reviews(case, run):
    return Audit.objects.filter(case=case,actor_id=run.actor_id,action='rfp.followup_reviewed',data__run=run.pk)


@transaction.atomic
def review(actor, case_id, outcome_id, run_id, text, predecessor, expected):
    case = lock_case(actor, case_id, 'evidence.add', expected)
    outcome = for_case(case, outcome_id)
    authorize(actor, case, outcome)
    run = latest_run(actor,case,outcome)
    if not run or run.pk != run_id or run.result['submission'] != outcome.submission_id:
        raise ValidationError('Review the current draft for this submission.')
    previous = reviews(case,run).order_by('-pk').first()
    if (previous.pk if previous else 0) != predecessor:
        raise ValidationError('The draft already changed. Reload the current reviewed text.')
    if not isinstance(text,str) or not text.strip() or len(text)>4000:
        raise ValidationError('Enter the reviewed follow-up wording.')
    evidence = add_evidence(actor,case.pk,SOURCE_KIND,text.strip(),'human:rfp-followup')
    return event(actor,case,'rfp.followup_reviewed',run=run.pk,source=evidence.pk,outcome=outcome.pk,dispatched=False)


def panel(actor, case, outcome):
    if outcome is None or outcome.result not in {'pending','unknown'}:
        return None
    try:
        authorize(actor,case,outcome)
        require(actor,case,'evidence.add')
    except (ValidationError,PermissionDenied):
        return None
    run = latest_run(actor,case,outcome)
    view = {'outcome':outcome,'run':run}
    if run:
        previous = reviews(case,run).order_by('-pk').first()
        source = Evidence.objects.get(case=case,kind=SOURCE_KIND,pk=previous.data['source']) if previous else run.evidence
        view.update(text=source.body,reviewed=previous)
    return view


def reminders(actor):
    cases = granted(actor, ['rfp.read','rfp.prepare'])
    later = RFPOutcome.objects.filter(submission__response__rfp=OuterRef('submission__response__rfp'),pk__gt=OuterRef('pk'))
    rows = RFPOutcome.objects.filter(submission__response__rfp__case__in=cases,
        submission__response__rfp__current_intake__assignments__pm=actor,
        result__in=['pending','unknown'],followup_on__lte=timezone.localdate()).filter(~Exists(later)).select_related(
        'submission__response__rfp__case').distinct().order_by('followup_on','pk')[:8]
    for outcome in rows:
        rfp = outcome.submission.response.rfp
        try:
            authorize(actor,rfp.case,outcome)
        except (ValidationError,PermissionDenied):
            continue
        yield {'key':digest(['rfp-check',outcome.pk]),'label':'Bid follow-up due','subject':rfp.reference,
               'detail':outcome.followup_on.isoformat(),'url':reverse('rfp',args=[rfp.case_id]),'group':'action'}
