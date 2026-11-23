"""Bind the role desk to current native factory decisions and their source packets."""
from contextlib import nullcontext

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.core.evidence_access import public_evidence
from apps.core.models import Case, Evidence
from apps.core.services import add_evidence, bump, event
from apps.documents.contracts import digest
from apps.workflows.factory_definitions import DEFINITIONS
from apps.workflows.models import HumanTask

from . import intake, teams
from .services import require, subject_actions
from .team_models import StaffAssignment, StaffFactoryReviewUse, StaffReviewUse


LABELS = {'invoice':'Invoice review','accounting':'Accounting review','document':'Document review',
          'planning':'Planning exit','closure':'Project closure','escalation':'Client escalation'}
VERDICTS = ('approve','return','reject')
LINES = {'invoice':'pmo-finance/v1','accounting':'finance-accounts/v1','planning':'delivery-release/v1',
         'closure':'delivery-closure/v1','escalation':'pmo-escalation/v1'}
ACTIONS = {'invoice':{'finance.invoice.review','evidence.add'},'accounting':{'finance.review','evidence.add'},
           'planning':{'delivery.planning_decide'},'closure':{'delivery.closure_decide'},
           'escalation':{'issue.escalation_decide'},'document':{'document.read','document.review_controlled'}}


def document_handlers():
    from apps.core.factory_api.reviews import DOCUMENTS
    from apps.workflows import factory_change, factory_closure, factory_emergency, factory_escalation, factory_go_live
    from apps.workflows import factory_handover, factory_leadership, factory_minutes, factory_reporting

    def minutes_version(work):
        binding = factory_minutes.document(work)
        return binding.version if binding else None

    sources = {'pmo-weekly-report/v1':factory_reporting.document,'pmo-leadership-report/v1':factory_leadership.document,
        'pmo-minutes/v1':minutes_version,'pmo-emergency/v1':factory_emergency.document,
        'pmo-change/v1':lambda work: [factory_change.document(work,kind) for kind in ('notice','go_live')],
        'pmo-escalation/v1':factory_escalation.document,'delivery-go-live/v1':factory_go_live.document,
        'delivery-closure/v1':factory_closure.document,'delivery-handover/v1':factory_handover.document}
    return sources, {**DOCUMENTS,'delivery-handover/v1':factory_handover.review}


def document_projection(actor, row, version):
    from .role_work import permitted_document_projection

    if row.work.definition!='pmo-weekly-report/v1':
        return permitted_document_projection(actor,row.case,version)
    from apps.workflows import factory_reporting

    # Read the existing outward projection only after the original source owner
    # still passes the native source, coverage and provenance checks.
    _, outward, _ = factory_reporting.bound_document(row.work,row.work.source_head.created_by)
    return outward.pk==version.pk


def permissions(work, kind):
    return {'case.read','factory.read',DEFINITIONS[work.definition]['read']} | ACTIONS[kind]


def subject_pin(work, kind, target, *, accounting=None):
    data = {'work':work.pk,'kind':kind,'subject':target,'head':work.source_head_id,'intake':work.request_hash}
    if kind == 'invoice':
        data['invoice_sha256'] = work.invoice.sha256
    if kind == 'accounting':
        data.update(purpose=accounting['purpose'],subject_type=accounting['subject'])
    return digest(data)


def document_target(work, target):
    sources, _ = document_handlers()
    source = sources.get(work.definition)
    if source is None:
        raise Http404
    versions = source(work)
    for version in versions if isinstance(versions,list) else [versions]:
        if version and version.pk==target and version.document.case_id==work.case_id:
            return version
    raise Http404


@transaction.atomic
def assign(actor, case_id, member_id, work_id, kind, target, evidence_id, expected):
    from apps.workflows.factory_views import visible
    from .role_work import FACTORY_LINKS, member_for

    case = Case.objects.select_for_update().get(pk=case_id)
    member = member_for(case,member_id)
    intake.lock_users([actor.pk,member.user_id])
    work = get_object_or_404(visible(actor,work_id=work_id,case_id=case_id))
    if kind not in ACTIONS or work.definition not in FACTORY_LINKS[member.role] or (
            kind != 'document' and work.definition != LINES.get(kind)):
        raise ValidationError('Choose a decision from this person’s current department and workspace.')
    teams.manageable(actor,case,permissions(work,kind))
    if case.revision!=expected or work.cancel_requested or work.status in ('verified','cancelled','followup_needed'):
        raise ValidationError('STALE_VERSION: Review the active work and current decision.')
    task = evidence = None
    accounting = None
    if kind == 'invoice':
        target = target or work.invoice_id
        if not work.invoice_id or work.invoice_id!=target:
            raise ValidationError('Choose the current invoice version on this work.')
        from apps.finance import invoices

        invoices.current(work.invoice)
    elif kind == 'accounting':
        if target is None:
            waiting = list(HumanTask.objects.filter(case=case,kind='factory_accounting_review',status='open',
                                                   context__work=work.pk).values_list('pk',flat=True)[:2])
            if len(waiting)==1:
                target = waiting[0]
        task = get_object_or_404(HumanTask,case=case,pk=target,kind='factory_accounting_review',status='open',context__work=work.pk)
        accounting = task.context['packet']
        target = accounting['target']
        task = None
    elif kind in ('document','closure'):
        if target is None:
            sources, _ = document_handlers()
            versions = sources[work.definition](work)
            choices = [version for version in (versions if isinstance(versions,list) else [versions]) if version is not None]
            if len(choices)==1:
                target = choices[0].pk
        version = document_target(work,target)
        if kind=='document':
            require(actor,case,'document.read')
            if version.audience not in ('client','internal','management'):
                raise ValidationError('Use the source-owned review for this document audience.')
            task = get_object_or_404(HumanTask,case=case,version=version,kind='document_review',status='open')
            previous = StaffAssignment.objects.filter(membership=member,review_task=task).first()
            if previous:
                return previous
    elif kind=='planning':
        target = target or work.request.get('dossier')
        if work.request.get('dossier')!=target:
            raise ValidationError('Choose the current Planning dossier on this work.')
    else:
        from apps.workflows import factory_escalation

        current,_=factory_escalation.source(work,actor)
        target = target or current.pk
        if current.pk!=target:
            raise ValidationError('Choose the current client escalation request on this work.')
    if kind in ('planning','closure'):
        evidence = get_object_or_404(public_evidence(Evidence.objects.filter(case=case)),pk=evidence_id)
    elif evidence_id is not None:
        raise ValidationError('The exact review packet owns the evidence for this decision.')
    row, created = StaffAssignment.objects.get_or_create(case=case,membership=member,work=work,
        factory_kind=kind,factory_subject=target,factory_pin=subject_pin(work,kind,target,accounting=accounting),
        defaults={'actor':actor,'review_task':task,'decision_evidence':evidence})
    if created:
        event(actor,case,'staff.factory_decision_assigned',assignment=row.pk,work=work.pk,member=member.pk,kind=kind)
        bump(case)
        if kind in ('invoice','accounting'):
            from apps.workflows.factory_progress import wake_waiting

            wake_waiting(work.pk)
    return row


def assigned_reviewers(work, kind, target, accounting=None):
    pinned = StaffAssignment.objects.filter(case=work.case,work=work,factory_kind=kind,factory_subject=target,
        factory_pin=subject_pin(work,kind,target,accounting=accounting),membership__active=True,membership__user__is_active=True)
    return set(pinned.values_list('membership__user_id',flat=True))


def review_candidates(work, kind, target, accounting=None):
    scoped = assigned_reviewers(work,kind,target,accounting)
    grant = 'finance.invoice.review' if kind=='invoice' else 'finance.review'
    users = get_user_model().objects.filter(is_active=True).filter(
        Q(grant__case=work.case,grant__active=True,grant__action=grant) | Q(pk__in=scoped)).distinct().order_by('pk')
    return users, scoped


def invoice_scope(invoice, actor):
    """Re-enter invoice validation for the current exact assigned reviewer."""
    from apps.workflows.models import FactoryWork

    work = FactoryWork.objects.filter(case=invoice.case,invoice=invoice,definition=LINES['invoice']).first()
    if work and actor.pk in assigned_reviewers(work,'invoice',invoice.pk):
        return subject_actions(actor,invoice.case,permissions(work,'invoice'))
    return nullcontext()


def recorded_access(case, actor, kind, native_id, action, *, accounting=None):
    try:
        require(actor,case,action)
    except PermissionDenied:
        receipts = StaffFactoryReviewUse.objects.select_related('assignment__work').filter(
            assignment__case=case,assignment__factory_kind=kind,native_id=native_id,
            assignment__membership__user=actor,assignment__membership__active=True,assignment__membership__user__is_active=True,
            assignment__work__cancel_requested=False).exclude(assignment__work__status='cancelled')
        if not any(receipt.assignment.factory_pin==subject_pin(receipt.assignment.work,kind,
                   receipt.assignment.factory_subject,accounting=accounting) for receipt in receipts):
            raise


def current_task(actor, row):
    work, kind = row.work, row.factory_kind
    kind_name = 'factory_review' if kind=='invoice' else 'factory_accounting_review'
    tasks = HumanTask.objects.filter(case=row.case,kind=kind_name,context__work=work.pk,status='open').filter(
        Q(claimed_by__isnull=True) | Q(claimed_by=actor)).order_by('-pk')[:30]
    for task in tasks:
        if not task.factory_key or not task.factory_key.startswith(f'factory:{work.pk}:'):
            continue
        try:
            if kind=='invoice':
                from apps.workflows import factory, factory_routing

                if work.invoice_id!=row.factory_subject:
                    return None
                factory.assert_review_task_current(work,task)
                verdicts = factory_routing.review_capabilities(work,actor)['verdicts']
            else:
                from apps.workflows import factory, factory_accounting

                packet = task.context.get('packet',{})
                if packet.get('target')!=row.factory_subject or row.factory_pin!=subject_pin(work,kind,row.factory_subject,accounting=packet):
                    continue
                _, profile = factory.profile(work,recovery=True)
                selected = factory_accounting.review_task(work,task,profile,reader=actor)
                verdicts = list(next((item['decisions'] for item in factory_accounting.route(work,selected,profile)
                                     if item['id']==actor.pk),{}))
        except (PermissionDenied,ValidationError):
            continue
        if verdicts:
            return task, verdicts
    return None


def native_panel(actor, row):
    from apps.workflows import factory_closure, factory_delivery, factory_escalation
    from apps.policy.services import decision_authority

    kind, work = row.factory_kind,row.work
    if kind=='planning':
        panel = factory_delivery.projection(actor,work)
        issue = panel.get('return_issue')
        # Linked remedy decisions keep the native issue reader and exact issue check.
        if issue:
            return None
        return panel['allowed_verdicts'],'PMO Lead',panel['decision_packet']
    if kind=='closure':
        panel = factory_closure.projection(actor,work,include_execution=False)
        if not panel['document'] or panel['document'].pk!=row.factory_subject or panel['decision']:
            return None
        return panel['verdicts'],'Head of PMO',panel['document'].payload_sha256
    request,_ = factory_escalation.source(work,actor)
    factory_escalation.settled(work)
    if request.pk!=row.factory_subject or request.target!='Client' or request.decisions.exists():
        return None
    for role in ('PMO Lead','Head of PMO'):
        verdicts = []
        pins = {}
        for verdict in VERDICTS:
            try:pins[verdict] = decision_authority(actor,row.case,role,verdict)
            except (PermissionDenied,ValidationError):continue
            verdicts.append(verdict)
        if verdicts:
            return verdicts,role,digest(pins)
    return None


def options(actor, row):
    work, kind = row.work,row.factory_kind
    if (work.cancel_requested or work.status in ('verified','cancelled','followup_needed') or
            work.lease_until and work.lease_until>timezone.now() or StaffFactoryReviewUse.objects.filter(assignment=row).exists()):
        return None
    if kind=='invoice' and work.invoice_id!=row.factory_subject:
        return None
    if kind!='accounting' and row.factory_pin!=subject_pin(work,kind,row.factory_subject):
        return None
    try:
        with subject_actions(actor,row.case,permissions(work,kind)):
            if kind=='document':
                from .role_work import document_options

                document_target(work,row.factory_subject)
                packet = document_options(actor,row,exact_factory=True)
                if packet:
                    packet['token'] = digest({'document':packet['token'],'work_revision':work.revision,'assignment':row.factory_pin})
                return packet
            if kind in ('invoice','accounting'):
                current = current_task(actor,row)
                if not current:
                    return None
                task, verdicts = current
                sections = [{'heading':'Review subject','text':DEFINITIONS[work.definition]['title']}]
                if kind=='invoice':
                    sections.append({'heading':'Invoice reference','text':work.invoice.reference})
                    sections.append({'heading':'Invoice total','text':f'{work.invoice.amount} {work.invoice.currency}'})
                    due = work.invoice.due_date
                    sections.append({'heading':'Due date','text':due.isoformat() if due else 'Unrecorded'})
                else:
                    sections.append({'heading':'Decision purpose','text':task.context['packet']['purpose'].replace('_',' ').capitalize()})
                version = work.invoice.version if kind=='invoice' else None
                role, pin = 'Finance',{'task':task.pk,'revision':task.revision,'packet':task.context.get('packet')}
            else:
                current = native_panel(actor,row)
                if not current:
                    return None
                verdicts,role,pin = current
                task,version = None,None
                sections = [{'heading':'Review subject','text':DEFINITIONS[work.definition]['title']}]
                if kind=='planning':
                    proof = get_object_or_404(public_evidence(Evidence.objects.filter(case=row.case)),pk=row.decision_evidence_id)
                    sections.append({'heading':'Selected decision evidence','text':proof.body[:4000]})
                if kind=='closure':
                    from apps.documents.controlled import current_version
                    from .role_work import permitted_document_projection

                    version_record = current_version(row.case,row.factory_subject)
                    if not permitted_document_projection(actor,row.case,version_record):
                        return None
                    sections = [{key:part[key] for key in ('heading','text')} for part in version_record.payload['sections']]
                    version = version_record.number
    except (Http404,ValidationError,PermissionDenied):
        return None
    if not verdicts:
        return None
    return {'title':LABELS[kind],'sections':sections,'role':role,'version':version,'verdicts':verdicts,'task':task,'pin':pin,
        'token':digest({'assignment':row.pk,'case':row.case.revision,'work':work.revision,'pin':pin,'verdicts':verdicts})}


def perform(actor,row,packet,verdict,note,expected):
    from apps.workflows import factory, factory_accounting, factory_closure, factory_delivery, factory_escalation

    work, kind = row.work,row.factory_kind
    with subject_actions(actor,row.case,permissions(work,kind)):
        if kind in ('invoice','accounting'):
            task = packet['task']
            claim, decide = (factory.claim_task,factory.decide) if kind=='invoice' else (factory_accounting.claim,factory_accounting.decide)
            if task.claimed_by_id is None:
                task = claim(actor,task.pk,task.revision)
            proof = add_evidence(actor,row.case_id,'invoice_review' if kind=='invoice' else 'finance_review',note,
                                 f'role-work:{row.pk}',expected=expected)
            decision = decide(actor,task.pk,task.revision,verdict,proof.pk,note)
        elif kind=='document':
            _, handlers = document_handlers()
            context = {'scoped':True} if work.definition=='pmo-weekly-report/v1' else {}
            decision = handlers[work.definition](actor,work.pk,work.revision,expected,row.factory_subject,verdict,note,**context)
            StaffReviewUse.objects.create(assignment=row,review=decision)
        elif kind=='planning':
            decision = factory_delivery.decide(actor,work.pk,work.revision,verdict,row.decision_evidence_id,note,expected,packet['pin'])
        elif kind=='closure':
            decision = factory_closure.decide(actor,work.pk,work.revision,expected,row.factory_subject,verdict,row.decision_evidence_id,note)
        else:
            decision = factory_escalation.decide(actor,work.pk,work.revision,expected,row.factory_subject,packet['role'],verdict,note)
    StaffFactoryReviewUse.objects.create(assignment=row,native_id=decision.pk,verdict=verdict)
    from apps.workflows.factory_progress import wake_waiting

    wake_waiting(work.pk)
    return {'review_id':decision.pk,'verdict':verdict}
