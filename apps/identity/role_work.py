"""Record-scoped action work and exact native decisions for role dashboards."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Exists, F, Func, JSONField, OuterRef, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from apps.core.evidence_access import public_evidence
from apps.core.models import Case
from apps.core.presentation import workspace_name
from apps.core.read_budget import ReadLimit, limit_queries
from apps.core.services import add_evidence, bump, event
from apps.documents import controlled
from apps.documents.contracts import digest
from apps.finance import hrfinance
from apps.finance.hrfinance_models import HRHandoffRecord
from apps.pmo import leadership_reporting, meetings
from apps.pmo.models import ActionItem
from apps.policy.services import decision_authority
from apps.workflows.factory_definitions import DEFINITIONS
from apps.workflows.models import FactoryWork, HumanTask

from . import intake, teams
from .services import require, subject_actions
from .team_models import StaffAssignment, StaffMembership, StaffReviewUse


OWN_ACTIONS = frozenset({'action.own', 'action.work', 'evidence.add'})
DOC_ACTIONS = frozenset({'document.read', 'document.review_controlled'})
DECISIONS = ('approve', 'return', 'reject')
ACTION_OPERATIONS = {'open': ('start', 'complete'), 'in_progress': ('complete',)}
NOTE_KIND = 'role_work_update'
SIZE = 25
STATE = {
    'open': 'Open', 'in_progress': 'In progress', 'completed': 'Completed', 'cancelled': 'Cancelled',
    'paused': 'Paused', 'returned': 'Returned', 'rejected': 'Rejected', 'withdrawn': 'Withdrawn',
}
FACTORY_LINKS = {
    'pmo-lead': {key for key in DEFINITIONS if not key.startswith(('finance-', 'pmo-finance/'))},
    'finance-lead': {key for key in DEFINITIONS if key.startswith('finance-')} | {'pmo-finance/v1'},
    'hr': {'finance-payroll/v1', 'finance-bu/v1'},
    'cto': {'pmo-issues/v1', 'pmo-change/v1', 'pmo-emergency/v1', 'delivery-release/v1', 'delivery-go-live/v1',
            'delivery-hypercare/v1', 'delivery-handover/v1'},
    'ceo': {'pmo-leadership-report/v1'},
    'admin': set(),
}
APPROVAL_DESKS = (
    ('payment_controls', 'Payment exceptions', ('payment.read','finance.read','delivery.read','payment.exception.decide')),
    ('emergencies', 'Emergency approvals', ('emergency.read','emergency.decide')),
    ('emergencies', 'Emergency retrospective', ('emergency.read','emergency.retrospective_decide')),
    ('finance_forecast', 'Forecast review', ('finance.read','finance.forecast.review')),
    ('payroll', 'Payroll review', ('payroll.read','payroll.private.read','payroll.review')),
    ('rfp', 'Bid review', ('rfp.read','rfp.review')),
    ('approvals', 'Department approvals', ('approval.read','approval.receive')),
)
DESK_PAGE_SIZE = 8


def actor_name(user):
    return user.get_full_name() or user.get_username()


def scoped_rows(actor):
    return teams.visible_assignments(actor).select_related('case', 'membership__user', 'membership__team',
        'action__current', 'review_task', 'work', 'schedule', 'hr_request').defer('work__request', 'work__finding',
        'review_task__context', 'schedule__payload', 'schedule__result', 'schedule__snapshot', 'hr_request__payload')


def entry_for(actor, assignment_id):
    return get_object_or_404(scoped_rows(actor), pk=assignment_id)


def member_for(case, member_id):
    return StaffMembership.objects.select_related('user', 'team').get(case=case, pk=member_id,
                                                                       active=True, user__is_active=True)


def choose_work(actor, member, work_id):
    if work_id is None:
        return None
    from apps.workflows.factory_views import visible

    return get_object_or_404(visible(actor, work_id=work_id, case_id=member.case_id),
                             definition__in=FACTORY_LINKS[member.role])


@transaction.atomic
def assign_action(actor, case_id, member_id, *, reference='', description='', due_at=None, reason,
                  expected, work_id=None, action_id=None):
    case = Case.objects.select_for_update().get(pk=case_id)
    member = member_for(case, member_id)
    intake.lock_users([actor.pk, member.user_id])
    teams.manageable(actor, case, OWN_ACTIONS)
    require(actor, case, 'action.manage')
    require(actor, case, 'evidence.add')
    if case.revision != expected:
        raise ValidationError('STALE_VERSION: The workspace changed. Review the assignment again.')
    intake.text(reason, 1000)
    work = choose_work(actor, member, work_id)
    existing = get_object_or_404(ActionItem.objects.select_related('current'), case=case, pk=action_id) if action_id else None
    if existing and StaffAssignment.objects.filter(action=existing).exists():
        raise ValidationError('This action is already assigned. Use its existing work page to reassign it.')
    note = add_evidence(actor, case.pk, NOTE_KIND, reason, 'role-work:assignment', expected=case.revision)
    case.refresh_from_db(fields=['revision'])
    with subject_actions(member.user, case, ['action.own']):
        if existing:
            meetings.change_action(actor, case.pk, existing.pk, 'reassign', note.pk, reason,
                                   case.revision, existing.current.number, owner_id=member.user_id)
            item = existing
        else:
            item = meetings.create_action(actor, case.pk, reference, description, member.user_id,
                                          due_at, note.pk, reason, case.revision)
    row = StaffAssignment.objects.create(case=case, membership=member, action=item, work=work, actor=actor)
    event(actor, case, 'staff.action_assigned', assignment=row.pk, member=member.pk, action_id=item.pk)
    return row


def review_task(case, task_id):
    return get_object_or_404(HumanTask.objects.select_related('version__document', 'version__template'),
        pk=task_id, case=case, version__document__case=case, kind='document_review',
        version__template__definition__document_type='status_report', version__audience__in=['internal','management','client'])


@transaction.atomic
def assign_review(actor, case_id, member_id, task_id, expected):
    case = Case.objects.select_for_update().get(pk=case_id)
    member = member_for(case, member_id)
    intake.lock_users([actor.pk, member.user_id])
    teams.manageable(actor, case, DOC_ACTIONS)
    require(actor, case, 'document.read')
    if case.revision != expected:
        raise ValidationError('STALE_VERSION: The workspace changed. Review the assignment again.')
    task = review_task(case, task_id)
    if task.status != 'open' or task.version.document.current_id != task.version_id:
        raise ValidationError('Choose a current open document review.')
    row, created = StaffAssignment.objects.get_or_create(case=case, membership=member, review_task=task,
                                                        defaults={'actor': actor})
    if created:
        event(actor, case, 'staff.review_assigned', assignment=row.pk, member=member.pk, task=task.pk)
        bump(case)
    return row


def review_options(actor, row):
    """Resolve the native decision and disclose only its exact audience projection."""
    if row.membership.user_id != actor.pk:
        return None
    if row.factory_kind:
        from .role_factory_decisions import options

        return options(actor,row)
    if row.schedule_id or row.hr_request_id:
        from .role_native_decisions import options

        return options(actor, row)
    return document_options(actor,row)


def permitted_document_projection(actor, case, version):
    source_ids = {item['id'] for item in version.source_manifest}
    if source_ids != set(public_evidence(case.evidence.filter(pk__in=source_ids)).values_list('pk',flat=True)):
        return False
    leadership_reporting.binding_access(actor,version)
    return True


def document_options(actor,row,*,exact_factory=False):
    task = row.review_task if exact_factory else review_task(row.case,row.review_task_id)
    if task.status != 'open' or actor.pk in (task.created_by_id, task.version.created_by_id) or (
            task.claimed_by_id not in (None, actor.pk)):
        return None
    try:
        version = controlled.current_version(row.case, task.version_id)
        role, _ = leadership_reporting.review_context(version)
        if role != task.required_role:
            return None
        if exact_factory:
            from .role_factory_decisions import document_projection

            accessible = document_projection(actor,row,version)
        else:
            accessible = permitted_document_projection(actor,row.case,version)
        if not accessible:
            return None
        from apps.pmo.rfp_submission_pack import require_independent_review

        allowed = {}
        for verdict in DECISIONS:
            for delegated in (False, True):
                try:
                    require_independent_review(actor, version, verdict=verdict)
                    allowed[verdict] = (delegated, decision_authority(actor, row.case, role, verdict, delegated))
                except (PermissionDenied, ValidationError):
                    continue
                break
    except (PermissionDenied, ValidationError):
        return None
    if not allowed:
        return None
    token = digest({'assignment': row.pk, 'revision': row.revision, 'case_revision': row.case.revision,
                    'task': task.pk, 'version': version.pk, 'hash': version.payload_sha256, 'authority': allowed})
    return {'title': version.document.title, 'version': version.number, 'task': task, 'role': role,
            'sections': [{'heading': section['heading'], 'text': section['text']} for section in version.payload['sections']],
            'verdicts': list(allowed), 'authority': allowed, 'token': token}


def card(row, actor):
    item = row.action
    mine = row.membership.user_id == actor.pk
    if item:
        title, state = item.current.description, item.current.status
    elif row.factory_kind:
        from .role_factory_decisions import LABELS

        title, state = LABELS[row.factory_kind], 'open'
    elif row.schedule_id:
        title, state = 'Finance schedule review', 'open'
    elif row.hr_request_id:
        title, state = 'Staff matching correction', 'open'
    else:
        title, state = 'Assigned document review', row.review_task.status
    return {'id': row.pk, 'case_id': row.case_id, 'workspace': workspace_name(row.case),
            'role': row.membership.role, 'owner': actor_name(row.membership.user), 'mine': mine,
            'title': title,
            'due': item.current.due_at if item else None, 'state': STATE.get(state, state),
            'url': reverse('role_work_detail', args=[row.pk]),
            'line': DEFINITIONS[row.work.definition]['title'] if row.work and row.work.definition in DEFINITIONS else None}


def workspace_decisions(actor, page):
    """Reuse the current native decision queue for independently granted workspaces."""
    from apps.core.workbench import granted
    from apps.workflows.factory_views import queue_context
    from apps.workflows.screen_focus import SCREENS

    if not granted(actor, ['factory.read']).exists():
        return [], False, False
    try:
        queue = queue_context(actor, {'queue':'decisions','page':str(page)})
    except (Http404,PermissionDenied,ValidationError):
        return [], False, True
    if queue['candidates'].number != page:
        return [], False, False
    rows = []
    for item in queue['rows']:
        if not item.get('needs_me'):
            continue
        work = item['work']
        focused = 'decision' in SCREENS.get(work.definition,{})
        url = reverse('factory_invoice_decision' if focused else 'factory_detail',args=[work.pk])
        rows.append({'work_id':work.pk,'title':item.get('title') or DEFINITIONS[work.definition]['title'],
                     'workspace':workspace_name(work.case),'state':item['state'],'url':url})
    return rows, queue['candidates'].has_next(), queue['limited']


def approval_desks(actor, page):
    """Link to specialist desks where the reader has the native entry permissions."""
    allowed, eligible = {}, Q()
    for index, (_, _, actions) in enumerate(APPROVAL_DESKS):
        key = f'permissions_{index}'
        required = ('case.read',*actions)
        allowed[key] = Count('grant__action',filter=Q(grant__user=actor,grant__active=True,grant__action__in=required),distinct=True)
        eligible |= Q(**{key:len(required)})
    offset = (page-1)*DESK_PAGE_SIZE
    granted_cases = Case.objects.filter(grant__user=actor,grant__user__is_active=True,grant__active=True)
    cases = list(granted_cases.annotate(**allowed).filter(eligible).order_by('title','pk')[offset:offset+DESK_PAGE_SIZE+1])
    desks = []
    for case in cases[:DESK_PAGE_SIZE]:
        for index, (route, title, actions) in enumerate(APPROVAL_DESKS):
            if getattr(case,f'permissions_{index}') == len(actions)+1:
                desks.append({'title':title,'workspace':workspace_name(case),'url':reverse(route,args=[case.pk])})
    return desks,len(cases)>DESK_PAGE_SIZE


def dashboard(actor, page):
    from time import monotonic

    memberships = teams.memberships(actor).select_related('case', 'team').order_by('role', 'case__title', 'pk')
    positions = [{'role': item.role, 'mode': item.mode, 'name': teams.scope_label(item.role, item.mode),
                  'area': teams.FOCUS[item.role][0], 'focus': teams.FOCUS[item.role][1],
                  'workspace': workspace_name(item.case), 'team': item.team.name if item.team else None}
                 for item in memberships[:51]]
    offset = (page - 1) * SIZE
    query = scoped_rows(actor)
    rows = list(query.filter(action__isnull=False).order_by('action__current__due_at', '-pk')[offset:offset+SIZE+1])
    correction_closed = HRHandoffRecord.objects.filter(contract_id=OuterRef('hr_request__contract_id'),
        kind__in=['response','correction_return','correction_reject'],
        payload__request_id=Func(OuterRef('hr_request_id'),function='to_jsonb',output_field=JSONField()))
    pending = query.filter(Q(review_task__status='open') |
        Q(schedule__isnull=False, schedule__reviews__isnull=True) |
        (Q(hr_request__isnull=False) & ~Exists(correction_closed)) |
        (~Q(factory_kind='') & Q(stafffactoryreviewuse__isnull=True,work__cancel_requested=False) &
         ~Q(work__status__in=['verified','cancelled','followup_needed']))).order_by('-pk')
    decision_rows = list(pending.filter(membership__user=actor)[offset:offset+SIZE+1])
    team_decisions = list(pending.exclude(membership__user=actor)[offset:offset+SIZE+1])
    decisions = []
    limited = False
    # Verify the actionable decisions as each page is read. Return no private packets in a list.
    try:
        with limit_queries(900, deadline=monotonic()+8):
            for row in decision_rows[:SIZE]:
                if review_options(actor, row):
                    decisions.append(card(row, actor))
    except ReadLimit:
        limited = True
    native_rows, native_next, native_limited = workspace_decisions(actor,page)
    desks, desks_next = approval_desks(actor,page)
    return {'positions': positions[:50], 'actions': [card(row, actor) for row in rows[:SIZE]], 'decisions': decisions,
            'team_decisions': [card(row, actor) for row in team_decisions[:SIZE]], 'limited': limited or native_limited,
            'workspace_decisions':native_rows, 'approval_desks':desks,
            'has_teams': any(item['mode'] == 'lead' for item in positions), 'page': page,
            'has_next': native_next or desks_next or max(len(rows),len(decision_rows),len(team_decisions)) > SIZE, 'as_of': timezone.now()}


def detail(actor, row):
    value = card(row, actor)
    value.update(revision=row.revision, case_revision=row.case.revision, review=None, operations=[], conclusion=None)
    if not row.action_id:
        packet = review_options(actor, row)
        if packet:
            value['review'] = {key: packet[key] for key in ('title','version','role','sections','verdicts','token')}
        elif row.membership.user_id == actor.pk:
            if row.factory_kind:
                from .team_models import StaffFactoryReviewUse

                value['conclusion'] = StaffFactoryReviewUse.objects.filter(assignment=row).values_list('verdict',flat=True).first()
            elif row.schedule_id:
                value['conclusion'] = row.schedule.reviews.filter(actor=actor).values_list('verdict',flat=True).order_by('-pk').first()
            elif row.hr_request_id:
                kind = hrfinance.correction_disposition(row.hr_request).filter(actor=actor).values_list('kind',flat=True).first()
                value['conclusion'] = {'response':'approve','correction_return':'return','correction_reject':'reject'}.get(kind)
            else:
                value['conclusion'] = row.review_task.version.reviews.filter(actor=actor).values_list('verdict',flat=True).order_by('-pk').first()
            if value['conclusion']:
                value['state'] = 'Decision recorded'
        return value
    state = row.action.current
    if value['mine']:
        value['operations'] = list(ACTION_OPERATIONS.get(state.status, ()))
    value['action_revision'] = state.number
    value['conclusion'] = state.reason if state.status == 'completed' else None
    return value


def locked_entry(actor, assignment_id, expected, case_expected):
    current = entry_for(actor, assignment_id)
    if current.factory_kind:
        FactoryWork.objects.select_for_update().only('pk').get(pk=current.work_id)
    Case.objects.select_for_update().get(pk=current.case_id)
    intake.lock_users([actor.pk])
    row = entry_for(actor, assignment_id)
    if row.revision != expected or row.case.revision != case_expected:
        raise ValidationError('STALE_VERSION: The assignment changed. Open the current work again.')
    return row


@transaction.atomic
def act(actor, assignment_id, operation, reason, expected, case_expected, action_revision):
    row = locked_entry(actor, assignment_id, expected, case_expected)
    if row.action is None or actor.pk != row.membership.user_id:
        raise PermissionDenied('Only the current assignee can update this action.')
    state = row.action.current
    if operation not in ACTION_OPERATIONS.get(state.status, ()) or state.number != action_revision:
        raise ValidationError('STALE_VERSION: Choose an available action on the current record.')
    intake.text(reason, 1000)
    with subject_actions(actor, row.case, OWN_ACTIONS):
        evidence = add_evidence(actor, row.case_id, NOTE_KIND, reason, f'role-work:{row.pk}', expected=case_expected)
        return meetings.change_action(actor, row.case_id, row.action_id, operation, evidence.pk, reason,
                                      case_expected+1, action_revision)


@transaction.atomic
def decide(actor, assignment_id, verdict, note, expected, case_expected, token):
    row = locked_entry(actor, assignment_id, expected, case_expected)
    if row.action_id is not None or actor.pk != row.membership.user_id:
        raise PermissionDenied('Only a currently eligible assignee can record this decision.')
    packet = review_options(actor, row)
    if not packet or verdict not in packet['verdicts']:
        raise PermissionDenied('Current native decision authority is required.')
    if token != packet['token']:
        raise ValidationError('STALE_VERSION: The decision packet changed. Review the current version.')
    intake.text(note, 1000)
    if row.factory_kind:
        from .role_factory_decisions import perform

        return perform(actor,row,packet,verdict,note,case_expected)
    if row.schedule_id or row.hr_request_id:
        from .role_native_decisions import perform

        return {'review_id':perform(actor,row,verdict,note,case_expected), 'verdict':verdict}
    with subject_actions(actor, row.case, DOC_ACTIONS):
        review = controlled.review_version(actor, row.case_id, packet['task'].version_id, verdict, note, case_expected,
                                            delegated=packet['authority'][verdict][0])
    StaffReviewUse.objects.create(assignment=row, review=review)
    return {'review_id':review.pk, 'verdict':review.verdict}


def recorded_review_access(case, version, review):
    return StaffReviewUse.objects.filter(review=review, assignment__case=case,
        assignment__review_task__version=version, assignment__membership__user_id=review.actor_id,
        assignment__membership__user__is_active=True, assignment__membership__active=True).exists()


@transaction.atomic
def transfer(actor, case_id, assignment_id, member_id, reason, expected):
    case = Case.objects.select_for_update().get(pk=case_id)
    row = get_object_or_404(StaffAssignment.objects.select_related('action__current','membership'),
                            case=case, pk=assignment_id, action__isnull=False)
    member = member_for(case, member_id)
    intake.lock_users([actor.pk, member.user_id])
    teams.manageable(actor, case, OWN_ACTIONS)
    require(actor, case, 'action.manage')
    require(actor, case, 'evidence.add')
    if case.revision != expected:
        raise ValidationError('STALE_VERSION: The workspace changed. Review this transfer again.')
    if member.pk == row.membership_id or member.role != row.membership.role:
        raise ValidationError('Choose a different assignee in the same base role.')
    intake.text(reason, 1000)
    note = add_evidence(actor, case.pk, NOTE_KIND, reason, f'role-work:{row.pk}', expected=case.revision)
    with subject_actions(member.user, case, ['action.own']):
        meetings.change_action(actor, case.pk, row.action_id, 'reassign', note.pk, reason,
                               expected+1, row.action.current.number, owner_id=member.user_id)
    previous = row.membership_id
    row.membership = member
    row.revision = F('revision') + 1
    row.save(update_fields=['membership', 'revision'])
    event(actor, case, 'staff.action_reassigned', assignment=row.pk, previous=previous, member=member.pk)
