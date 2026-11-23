"""Recipient questions through a current HR owner, without expanding disclosure."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction

from adapters.payroll_questions import command,PACKET,TOPICS,REPLIES
from apps.core.services import lock_case,bump,event
from apps.documents.contracts import validate
from apps.identity.services import require
from apps.policy.payroll_validators import QUESTION_ROUTE
from apps.policy.services import active_component,reference_values
from apps.agents.payroll import prepare_report_question
from .hr_scope import owner_access
from . import payroll as native
from .payroll_models import PayrollPublication
from .payroll_question_models import PayrollReportQuestion,PayrollReportQuestionEvent


def active_actor(actor,case,action):
    fresh=get_user_model().objects.get(pk=actor.pk)
    require(fresh,case,'case.read');require(fresh,case,action)
    return fresh


def route(case):
    config=active_component(QUESTION_ROUTE,case);value=reference_values(config)[0]
    if value['owner_id'] is None:raise ValidationError('An HR response owner has not been selected')
    owner=get_user_model().objects.get(pk=value['owner_id']);authority=owner_access(owner,case)
    return {'route_id':config.pk,'owner_id':owner.pk,'authority':authority}


def source(question):
    validate(PACKET,question.packet)
    actor=active_actor(question.actor,question.case,'payroll.report.read')
    publication=PayrollPublication.objects.defer('payload').select_related('request').get(pk=question.publication_id)
    if publication.request.case_id!=question.case_id:raise ValidationError('Report belongs to a different workspace')
    current=prepare_report_question(actor,publication,question.packet['topic'])
    if current!=question.packet:raise ValidationError('The report changed; record a new question')
    return publication


def head(question):
    return question.events.order_by('-pk').first()


class StaleQuestion(ValidationError):
    """The response history has advanced since the submitted review."""


def check_head(question,expected):
    latest=head(question)
    if (latest.pk if latest else 0)!=expected:raise StaleQuestion('This question changed. Review it again.')
    return latest


def assigned(question):
    dispatched=question.events.filter(kind='dispatched').first()
    if dispatched is None or dispatched.data!=route(question.case):
        raise ValidationError('HR ownership changed. Cancel this question and record a successor.')
    return dispatched


class Reader:
    """Request-local reuse under the same native case lock; never a reusable grant."""
    def __init__(self,actor,case):
        self.case=lock_case(actor,case.pk,'case.read');self.sources={};self.routing=None;self.route_checked=False

    def admit_publication(self,actor,publication):
        if publication.request.case_id!=self.case.pk:raise PermissionDenied('Report belongs to another workspace')
        packet=prepare_report_question(actor,publication,'report_coverage')
        self.sources[(actor.pk,publication.pk)]=packet

    def source(self,question):
        if question.case_id!=self.case.pk:raise PermissionDenied('Question belongs to another workspace')
        validate(PACKET,question.packet);key=(question.actor_id,question.publication_id)
        if key not in self.sources:
            try:source(question);self.sources[key]=question.packet
            except (PermissionDenied,ValidationError) as exc:self.sources[key]=exc
        if isinstance(self.sources[key],Exception):raise self.sources[key]
        expected={**self.sources[key],'topic':question.packet['topic']}
        if question.packet!=expected:raise ValidationError('Question report identity differs')

    def configured_route(self):
        if not self.route_checked:
            try:self.routing=route(self.case)
            except (PermissionDenied,ValidationError):self.routing=None
            self.route_checked=True
        if self.routing is None:raise ValidationError('Current HR response owner needed')
        return self.routing

    def assigned(self,question):
        self.configured_route()
        dispatched=question.events.filter(kind='dispatched').first()
        if dispatched is None or dispatched.data!=self.routing:raise ValidationError('Question ownership changed')
        return dispatched


@transaction.atomic
def record(actor,case_id,publication_id,topic,operation_key,expected):
    case=lock_case(actor,case_id,'payroll.report.read',expected)
    actor=active_actor(actor,case,'payroll.report.read')
    publication=native.exact(case,PayrollPublication,publication_id)
    packet=prepare_report_question(actor,publication,topic)
    old=PayrollReportQuestion.objects.filter(operation_key=operation_key).first()
    if old:
        if old.case_id!=case.pk or old.actor_id!=actor.pk or old.packet!=packet:
            raise ValidationError('This question key has already been used for a different request')
        return old
    question=PayrollReportQuestion.objects.create(case=case,publication=publication,actor=actor,
        operation_key=operation_key,packet=packet)
    event(actor,case,'payroll.question_recorded',question=question.pk,publication=publication.pk,
          agent_tool='A04.payroll_report_question/v1',private_payloads_read=False)
    bump(case);return question


@transaction.atomic
def advance(actor,case_id,question_id,kind,expected_head,expected,reply=None):
    # All competing transitions and configuration/grant updates serialize on the case.
    case=lock_case(actor,case_id,'case.read',expected)
    question=PayrollReportQuestion.objects.select_for_update().select_related('case','actor').get(pk=question_id,case=case)
    last=check_head(question,expected_head)
    if last and last.kind in ['cancelled','received']:raise ValidationError('This question is already closed')
    data={}
    if kind=='cancelled':
        if actor.pk!=question.actor_id:raise PermissionDenied('Only the requester may cancel this question')
        active_actor(actor,case,'case.read')
    else:
        source(question)
        if kind=='dispatched':
            if last is not None:raise ValidationError('This question has already been sent')
            if actor.pk!=question.actor_id:raise PermissionDenied('Only the requester may send this question')
            data=route(case)
        elif kind=='answered':
            if last is None or last.kind!='dispatched':raise ValidationError('Choose a current question awaiting HR')
            dispatch=assigned(question)
            if actor.pk!=dispatch.data['owner_id']:raise PermissionDenied('Only the current assigned HR owner may answer')
            owner_access(active_actor(actor,case,'hrfinance.respond'),case)
            data=command('answer',{'reply':reply})
        elif kind=='received':
            if last is None or last.kind!='answered':raise ValidationError('Read a current HR reply first')
            if actor.pk!=question.actor_id:raise PermissionDenied('Only the requester may acknowledge this reply')
            assigned(question);command('answer',last.data)
        else:raise ValidationError('Choose a displayed question action')
    row=PayrollReportQuestionEvent.objects.create(question=question,actor=actor,kind=kind,data=data)
    event(actor,case,'payroll.question_'+kind,question=question.pk,record=row.pk);bump(case)
    return row


def projection(actor,question,reader=None):
    if reader is not None:return _projection(actor,question,reader)
    with transaction.atomic():
        lock_case(actor,question.case_id,'case.read')
        return _projection(actor,question,None)


def _projection(actor,question,reader):
    active_actor(actor,question.case,'case.read')
    own=actor.pk==question.actor_id
    if not own:
        dispatch=reader.assigned(question) if reader else assigned(question)
        if actor.pk!=dispatch.data['owner_id']:raise PermissionDenied('This question is private to its participants')
        owner_access(actor,question.case)
    last=head(question)
    result={'id':question.pk,'head':last.pk if last else 0,'question':TOPICS[question.packet['topic']],
            'period':question.packet['period'],'publication':question.publication_id,'state':'recorded',
            'can_cancel':own,'can_send':False,'can_answer':False,'can_receive':False,'reply':None,'owner_name':None}
    if last and last.kind=='cancelled':
        result.update(state='cancelled',can_cancel=False);return result
    try:
        reader.source(question) if reader else source(question)
        dispatch=(reader.assigned(question) if reader else assigned(question)) if last else None
    except (PermissionDenied,ValidationError):
        result['state']='held';return result
    if last is None:
        try:reader.configured_route() if reader else route(question.case);result['can_send']=own
        except (PermissionDenied,ValidationError):result['state']='owner_needed'
    else:
        result['state']=last.kind
        result['can_answer']=actor.pk==dispatch.data['owner_id'] and last.kind=='dispatched'
        if last.kind in ['answered','received']:
            answer=question.events.get(kind='answered');command('answer',answer.data)
            result['reply']=REPLIES[answer.data['reply']]
            result['can_receive']=own and last.kind=='answered'
        if last.kind=='received':result['can_cancel']=False
    if result['state']!='owner_needed':
        current_route=reader.configured_route() if reader else route(question.case)
        person=get_user_model().objects.only('first_name','last_name','username').get(pk=current_route['owner_id'])
        result['owner_name']=person.get_full_name() or person.username
    return result


def deferred_projection(actor,question):
    """No source or ownership assertion when the engineering read limit fires."""
    active_actor(actor,question.case,'case.read')
    own=actor.pk==question.actor_id
    if own:validate(PACKET,question.packet)
    return {'id':question.pk,'question':TOPICS[question.packet['topic']] if own else 'A question needs current access checks',
            'period':question.packet['period'] if own else None,'publication':None,'state':'read_limited',
            'can_cancel':False,'can_send':False,'can_answer':False,'can_receive':False,'reply':None,'owner_name':None}


@transaction.atomic
def inbox(actor,limit=25,*,queue=None,search=''):
    """Bounded current participant waits for the shared operator queue."""
    from django.db.models import OuterRef,Subquery,Q
    from apps.core.models import Case
    from apps.core.workbench import granted,active
    active(actor)
    if type(limit) is not int or not 1<=limit<=50:raise ValidationError('Choose a bounded question queue')
    latest=PayrollReportQuestionEvent.objects.filter(question_id=OuterRef('pk')).order_by('-pk')
    query=PayrollReportQuestion.objects.filter(case_id__in=granted(actor,[]).values('pk')).filter(
        Q(actor=actor)|Q(events__kind='dispatched',events__data__owner_id=actor.pk)).distinct().annotate(
        last_kind=Subquery(latest.values('kind')[:1]))
    if queue=='verified':query=query.filter(last_kind='received')
    else:query=query.filter(Q(last_kind__isnull=True)|~Q(last_kind__in=['cancelled','received']))
    if queue in ['needs_me','decisions']:
        needs_hr=Q(last_kind='dispatched',events__kind='dispatched',events__data__owner_id=actor.pk)
        query=query.filter(needs_hr if queue=='decisions' else needs_hr|Q(actor=actor,last_kind='answered')|Q(actor=actor,last_kind__isnull=True))
    elif queue=='waiting':query=query.filter(actor=actor,last_kind='dispatched')
    elif queue=='mine':query=query.filter(actor=actor)
    if search:
        topics=[key for key,value in TOPICS.items() if search.lower() in value.lower()]
        query=query.filter(Q(case__title__icontains=search)|Q(packet__topic__in=topics))
    selected=list(query.select_related('case','actor').order_by('-pk')[:limit])
    list(Case.objects.select_for_update().filter(pk__in={row.case_id for row in selected}).order_by('pk'))
    readers={};result=[]
    for question in selected:
        try:
            if question.case_id not in readers:readers[question.case_id]=Reader(actor,question.case)
            value=projection(actor,question,readers[question.case_id])
        except (PermissionDenied,ValidationError):continue
        result.append((question.case,value))
    return result


def queue_cards(actor,queue,search='',line=''):
    from time import monotonic
    from apps.core.read_budget import limit_queries,ReadLimit
    result={'rows':[],'held':False,'limit':8}
    if line not in ['', 'finance-payroll/v1']:return result
    try:
        with limit_queries(2200,deadline=monotonic()+5):
            entries=inbox(actor,8,queue=queue,search=search)
    except ReadLimit:
        result['held']=True;return result
    for case,value in entries:
        if queue=='verified' and value['state']!='received':continue
        if queue=='exceptions' and value['state'] not in ['owner_needed','held']:continue
        if queue=='unassigned' and value['state']!='owner_needed':continue
        if queue=='needs_me' and not (value['can_send'] or value['can_answer'] or value['can_receive'] or value['state']=='owner_needed'):continue
        result['rows'].append({'case':case,**value})
    return result
