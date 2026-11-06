"""Read-only discovery over current record grants and source-owned workflow facts."""
import uuid
from datetime import datetime
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied,ValidationError
from django.db.models import Q,F,OuterRef,Subquery
from django.db import transaction
from apps.identity.models import Grant
from apps.identity.services import visible_cases
from apps.policy.services import decision_authority
from .models import Case

CURSOR_SALT='psl.workbench.cases.v1'

def active(actor):
    if not actor.is_authenticated or not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():raise PermissionDenied('Current authenticated principal required')

def granted(actor,actions):
    query=visible_cases(actor)
    for action in actions:query=query.filter(pk__in=Grant.objects.filter(user=actor,active=True,action=action).values('case_id'))
    return query

def discover(actor,q='',tenant='',kind='',cursor=None,page_size=25,area=''):
    active(actor)
    if not all(isinstance(x,str) for x in [q,tenant,kind,area]) or len(q)>120 or len(tenant)>100 or kind not in ['', 'project','support'] or area not in ['', 'finance'] or type(page_size) is not int or not 1<=page_size<=50:raise ValidationError('Valid workspace search, organization, type, area and page size required')
    filters={'q':q.strip(),'tenant':tenant.strip(),'kind':kind,'area':area};query=granted(actor,['finance.read']) if area=='finance' else visible_cases(actor)
    if filters['tenant']:query=query.filter(tenant=filters['tenant'])
    if kind:query=query.filter(kind=kind)
    if filters['q']:
        from apps.pmo.engagement_models import ProjectIdentifier,EngagementRecord
        permitted=granted(actor,['engagement.read']).values('pk')
        from django.db.models import Case as DisplayCase,When,Value,CharField
        from .presentation import SAMPLE_LABELS
        sample=Q(synthetic=True)&(Q(title__istartswith='Synthetic')|Q(title='Test engagement')|Q(title__istartswith='AF13 synthetic ')|Q(title__istartswith='D13 synthetic '))
        aliases=[]
        for terms,label in SAMPLE_LABELS:
            matches=Q()
            for term in terms:matches|=Q(title__icontains=term)
            aliases.append(When(sample&matches,then=Value(label)))
        aliases += [When(sample&Q(kind='support'),then=Value('Customer support')),When(sample,then=Value('Project workspace'))]
        query=query.annotate(_display_title=DisplayCase(*aliases,default=F('title'),output_field=CharField()))
        term=filters['q'];match=Q(title__icontains=term)|Q(_display_title__icontains=term)
        try:match|=Q(pk=uuid.UUID(term))
        except (ValueError,AttributeError):pass
        match|=Q(pk__in=ProjectIdentifier.objects.filter(case_id__in=permitted,value__icontains=term).values('case_id'))
        match|=Q(pk__in=EngagementRecord.objects.filter(case_id__in=permitted,kind='capture',data__reference__icontains=term).values('case_id'))
        query=query.filter(match)
    if cursor:
        try:
            if not isinstance(cursor,str) or len(cursor)>4096:raise ValueError
            value=signing.loads(cursor,salt=CURSOR_SALT,max_age=3600)
            if set(value)!={'actor','filters','size','last'} or value['actor']!=actor.pk or value['filters']!=filters or value['size']!=page_size:raise ValueError
            when=datetime.fromisoformat(value['last'][0]);pk=uuid.UUID(value['last'][1])
            if when.tzinfo is None:raise ValueError
        except (signing.BadSignature,ValueError,KeyError,TypeError,IndexError):raise ValidationError('This page link is invalid or expired. Restart the search.') from None
        query=query.filter(Q(created_at__lt=when)|Q(created_at=when,id__lt=pk))
    rows=list(query.order_by('-created_at','-id')[:page_size+1]);more=len(rows)>page_size;rows=rows[:page_size]
    next_cursor=None
    if more:
        last=rows[-1];next_cursor=signing.dumps({'actor':actor.pk,'filters':filters,'size':page_size,'last':[last.created_at.isoformat(),str(last.pk)]},salt=CURSOR_SALT,compress=True)
    return {'cases':rows,'next_cursor':next_cursor,'filters':filters}

def _row(kind,case,pk,reference,status,path,**extra):
    labels={'assigned_action':'Assigned action','owned_support':'Recorded Support ownership','eligible_document_review':'Available document review','initiated_finance_intent':'Your financial intent','eligible_summary_review':'Available complaint summary review','received_department_request':'Received department request','assigned_rfp':'Assigned RFP coordination'}
    return {'kind':kind,'label':labels[kind],'case_id':str(case.pk),'case_title':case.title,'synthetic':case.synthetic,'record_id':pk,'reference':reference,'status':status,'display_status':status.replace('_',' '),'url':f'/cases/{case.pk}/{path}/',**extra}

@transaction.atomic
def work(actor,limit=25):
    active(actor)
    if type(limit) is not int or not 1<=limit<=50:raise ValidationError('Bounded work limit required')
    rows=[]
    from apps.pmo.models import ActionItem
    actions=ActionItem.objects.filter(case_id__in=granted(actor,['meeting.read','action.own']).values('pk'),current__owner=actor).exclude(current__status__in=['completed','cancelled']).select_related('case','current').order_by('current__due_at','pk')
    for item in actions[:limit]:
        rows.append(_row('assigned_action',item.case,item.pk,item.reference,item.current.status,'meetings',description=item.current.description,recorded_due_at=item.current.due_at.isoformat() if item.current.due_at else None,deadline_basis=item.current.due_basis))
    from apps.baas.support_models import SupportEvent
    eligible=granted(actor,['support.read','support.own']).filter(kind='support').annotate(latest=Subquery(SupportEvent.objects.filter(case_id=OuterRef('pk')).order_by('-version').values('pk')[:1]))
    owned=SupportEvent.objects.filter(pk__in=eligible.values('latest'),owner=actor).exclude(action__in=['resolve','cancel','merge']).select_related('case').order_by('-pk')
    from apps.baas import support
    from apps.policy.support_validators import FLOW
    for event in owned[:limit]:
        finding=''
        try:
            support.snapshot(event.case);_,flow=support.config(event.case,FLOW)
            if support.meaning(flow,event.state) in ['resolved','cancelled','merged']:continue
        except (ValidationError,PermissionDenied):finding='workflow_requires_reconciliation'
        rows.append(_row('owned_support',event.case,event.pk,'Support case',event.state,'support',finding=finding))
    from apps.workflows.models import HumanTask
    from apps.documents.controlled import current_version
    tasks=HumanTask.objects.filter(status='open',case_id__in=granted(actor,['document.read','document.review_controlled']).values('pk'),version__document__current_id=F('version_id')).exclude(version__template__definition__document_type__in=['accepted_finance_metadata','finance_report']).select_related('case','version__template','version__document').order_by('-pk')
    count=0
    for task in tasks[:100]:
        try:
            current_version(task.case,task.version_id)
            try:decision_authority(actor,task.case,'PMO Lead')
            except PermissionDenied:decision_authority(actor,task.case,'PMO Lead',delegated=True)
        except (ValidationError,PermissionDenied):continue
        rows.append(_row('eligible_document_review',task.case,task.pk,'Document version #'+str(task.version_id),'open','documents'));count+=1
        if count>=limit:break
    from apps.finance.models import InvoiceJob
    intents=InvoiceJob.objects.filter(actor=actor,invoice__case_id__in=granted(actor,['finance.read']).values('pk'),status__in=['held','unknown']).select_related('invoice__case').order_by('-pk')
    for job in intents[:limit]:rows.append(_row('initiated_finance_intent',job.invoice.case,job.pk,f'Invoice #{job.invoice_id} / {job.kind}',job.status,'finance/settlement'))
    from apps.baas import summaries
    versions=summaries.Version.objects.filter(request__case_id__in=granted(actor,['support.read','support.summary.read','support.summary.draft_read','support.summary.review']).values('pk')).select_related('request__case','actor').order_by('-pk')
    count=0
    for version in versions[:100]:
        try:
            summaries.review_controls(actor,version);summaries.current(version)
            latest=version.reviews.order_by('-pk').first()
            if latest:continue
        except (ValidationError,PermissionDenied,get_user_model().DoesNotExist):continue
        rows.append(_row('eligible_summary_review',version.request.case,version.pk,version.request.reference,'awaiting_current_reviewer','support/summaries'));count+=1
        if count>=limit:break
    from apps.pmo import rfp,approvals,approval_routing
    from apps.pmo.models import RFPCase,ApprovalRouteReceipt
    rfps=RFPCase.objects.filter(case_id__in=granted(actor,['rfp.read','rfp.prepare']).values('pk'),current_intake__assignments__pm=actor).select_related('case','current_intake').distinct().order_by('-pk')
    count=0
    for source in rfps[:100]:
        try:
            rfp.ensure_open(source);assignment=rfp.current_assignment(source)
            if assignment.pm_id!=actor.pk:continue
        except (PermissionDenied,ValidationError):continue
        intake=source.current_intake
        rows.append(_row('assigned_rfp',source.case,assignment.pk,source.reference,'recorded_pm_assignment','rfp',recorded_due_at=intake.deadline_at.isoformat() if intake.deadline_at else None,deadline_basis=intake.deadline_status));count+=1
        if count>=limit:break
    receipts=ApprovalRouteReceipt.objects.filter(recipient=actor,job__request__case_id__in=granted(actor,['approval.read','approval.receive']).values('pk')).select_related('job__request__case','job__request__candidate__requirements','job__actor').order_by('-pk')
    count=0;seen=set()
    for receipt in receipts[:100]:
        job=receipt.job;request=job.request
        if request.pk in seen:continue
        seen.add(request.pk)
        try:
            if approval_routing.intent(job.actor,request,job.purpose)!=job.intent or receipt.payload!=job.intent['public']:continue
            finding=approvals.visibility(actor,request)
            if finding['status'] in ['referenced_accepted','referenced_rejected','referenced_withdrawn']:continue
        except (PermissionDenied,ValidationError,get_user_model().DoesNotExist):continue
        rows.append(_row('received_department_request',request.case,receipt.pk,request.reference,finding['status'],'approvals',finding='source_verification_required' if finding['status']=='unavailable' else ''));count+=1
        if count>=limit:break
    return {'rows':rows,'coverage':'Bounded current accessible recorded assignments, delivered department requests, role-eligible reviews and initiated operational work; not an exhaustive task or approval claim',
        'authority_from_discovery':False,'effect_tools':[]}
