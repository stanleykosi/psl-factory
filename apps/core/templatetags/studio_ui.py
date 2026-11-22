"""Presentation only: stored records, evidence and authority remain unchanged."""
from decimal import Decimal
from urllib.parse import urlencode

from django import template
register=template.Library()


@register.simple_tag(takes_context=True)
def work_queue_query(context, work, include_work=False):
    from apps.workflows.factory_views import work_queue_params

    request = context.get('request')
    params = work_queue_params(request.GET if request else context, work=work)
    if include_work:
        params = {'work': work.pk, **params}
    return '?' + urlencode(params)


@register.filter
def recorded_time(value):
    """Display a retained aware instant in the operator's configured time zone."""
    from datetime import datetime
    from django.utils import timezone
    from django.utils.dateparse import parse_datetime
    if isinstance(value,str):
        try:value=parse_datetime(value)
        except ValueError:return 'Unknown'
    if not isinstance(value,datetime) or timezone.is_naive(value):return 'Unknown'
    return timezone.localtime(value).strftime('%d %b %Y, %H:%M:%S %Z')

@register.inclusion_tag('factory/execution_status.html',takes_context=True)
def factory_execution_status(context,work):
    from apps.workflows.factory import access
    from apps.workflows.factory_execution import available_actor
    from django.core.exceptions import PermissionDenied
    try:access(context['user'],work.case,'factory.manage',work.definition)
    except PermissionDenied:return {}
    return {'recovery_work':work,'current_worker':available_actor(work)}

@register.inclusion_tag('factory/coordinator_status.html',takes_context=True)
def factory_coordination_status(context,work):
    from apps.workflows.models import FactoryWork
    if not isinstance(work,FactoryWork):return {}
    from apps.agents.factory_coordinator import presentation
    from django.core.exceptions import PermissionDenied
    try:state=presentation(context['user'],work)
    except PermissionDenied:return {}
    return {'planning':state,'csrf_token':context.get('csrf_token')}


@register.simple_tag
def department_handoffs_available(user, case):
    from apps.workflows.native_station_access import project_scope
    return case.kind == "project" and project_scope(user).filter(pk=case.pk).exists()


@register.inclusion_tag('factory/background_status.html', takes_context=True)
def factory_background_status(context, work):
    from django.utils import timezone
    from apps.workflows.factory import TERMINAL
    from apps.workflows.factory_execution import can_control
    from apps.workflows.factory_progress import ACTIVE
    from apps.workflows.models import FactoryProgress, FactoryWork

    if not isinstance(work, FactoryWork):
        return {}
    job = FactoryProgress.objects.filter(work=work).first()
    watching=bool(job and not work.cancel_requested and work.status not in TERMINAL and
        (job.status in ['queued','running'] or job.status=='waiting' and not job.observation))
    request=context.get('request')
    return_query = (work_queue_query(context, work) if request and {'queue', 'q', 'line'}.intersection(request.GET)
                    else '')
    from apps.agents.specialist_memory import sources_for
    from apps.agents.specialist_packets import review_for
    from apps.agents.specialist_coordination import retry_candidate
    readings=sources_for(context['user'],[work.case_id],[work.definition],work_id=work.pk,review=True)
    can_manage = can_control(context['user'], work)
    return {'work': work, 'job': job, 'readings':readings, 'source_review':review_for(work, context['user']),
            'coordinator_retry': retry_candidate(work) if can_manage else None,
            'active': bool(job and job.status in ACTIVE),
            'watching':watching,'preserve_form':bool(request and request.method=='POST'),'work_query':return_query,
            'current_claim': bool(job and job.status == 'running' and job.available_at > timezone.now()),
            'can_control': can_manage, 'csrf_token': context.get('csrf_token'),
            'can_continue': not work.cancel_requested and work.status not in TERMINAL | {'waiting_effect'}}


from apps.core.presentation import workspace_name
register.filter('workspace_name',workspace_name)


@register.filter
def role_name(value):
    return {'PM': 'Project manager', 'PMO': 'Project management',
            'PMO Lead': 'Project management lead', 'Head of PMO': 'Head of project management',
            'CEO': 'Chief executive', 'CTO': 'Chief technology officer',
            'HR': 'Human resources', 'QA': 'Quality assurance',
            'BaaS': 'Banking as a service'}.get(value, value)

@register.filter
def readable(value):return str(value or '').replace('_',' ').replace('.',' · ').strip().capitalize()


@register.filter
def business_finding(value):
    text=str(value or '')
    prefix,separator,detail=text.partition(':')
    return detail.strip() if separator and prefix in ['owner_needed','configuration_needed','STALE_VERSION','CONFLICT'] else text


@register.filter
def decimal_display(value):
    if not isinstance(value, Decimal):
        return value
    whole, _, fraction = format(value, 'f').partition('.')
    return whole + '.' + fraction.rstrip('0').ljust(2, '0')


@register.filter
def page_name(value):
    names={'home':'Work queue','workspace_overview':'Workspaces','factory_detail':'Work item','factory_create':'Start work','factory_intake':'Start work','factory_configuration':'Execution profile','case':'Workspace','work_inbox':'My work','project_views':'Project reports','document_inbox':'Documents',
        'login':'Sign in','planning':'Project planning','costing':'Project costing','finance_analysis':'Financial analysis',
        'finance_settlement':'Invoices and receipts','finance_billing':'Billing','meetings':'Meetings and actions','policy':'Workspace settings',
        'integration_readiness':'Connections','operations':'Business continuity','case_create':'New workspace','coverage':'Process directory','closure_preparation':'Prepare for closure',
        'design_overview':'Factory overview','design_agents':'Assistant','design_project':'Project journey','design_setup':'Setup',
        'design_project_tab':'Project journey','design_company_month_end':'Month-end','design_payments':'Payments and follow-up','design_project_action':'Project action',
        'design_clients':'Clients','design_client_project':'Client details','design_document_review':'Document review',
        'design_template_upload':'Upload a template','design_alerts':'Alerts','design_alert_preferences':'Alert preferences',
        'design_payroll_inputs':'Payroll inputs','design_payroll_matching':'Payroll matching','design_payroll_corrections':'Payroll corrections'}
    return names.get(value,str(value or 'Workspace').replace('_',' ').capitalize())


@register.simple_tag
def workspace_sections(case,actions,can_manage_access=False):
    from django.urls import reverse
    specs=[('Projects','Plan, deliver and follow through.',[
        ('planning','Project planning','planning.read'),('engagement','Project details','engagement.read'),('costing','Costing','costing.read'),
        ('commercial','Proposals and agreements','commercial.read'),('rfp','Opportunities','rfp.read'),('delivery','Delivery and closure','delivery.read'),
        ('meetings','Meetings and actions','meeting.read'),('issues','Issues and risks','issue.read'),('changes','Change requests','change.read'),
        ('emergencies','Urgent changes','emergency.read'),('authority_recovery','Approval recovery','authority.read')]),
        ('Finance','Billing, accounts and financial reporting.',[
        ('finance_billing','Billing','finance.read'),('finance_settlement','Invoices and receipts','finance.read'),('finance_corrections','Credits and corrections','finance.read'),
        ('finance_forecast','Cash forecast','finance.read'),('finance_analysis','Financial analysis','finance.read'),('finance_performance','Budgets and performance','finance.read'),
        ('finance_schedules','Income and schedules',('finance.read','schedules.read')),('ppe','Assets and depreciation',('finance.read','ppe.read')),('payroll','Payroll and staff costs','payroll.read'),
        ('bu','Business unit costs','bu.read'),('hrfinance','HR information','hrfinance.read'),('recognition','Revenue recognition','recognition.read'),
        ('payment_controls','Payment review','payment.read'),('billing_evidence','Billing documents','d03.read'),
        ('finance_receipt_followup','Payment follow-up',('finance.read','finance.receipt_followup.read')),
        ('ledger','Ledger references',('finance.read','ledger.read')),('ledger_agents','Transaction evidence','ledger.agent.read')]),
        ('Customers','Support cases, partners and service activity.',[
        ('support_flow','Customer support','support.read'),('support_agents','Response drafts','support.agent.read'),('complaint_summaries','Service reports','support.summary.read'),
        ('partner_operations','Partner services','partner.read'),('baas_reconciliation','Reconciliation','baas.read')]),
        ('Documents','Prepare, review and share the right information.',[
        ('documents','Documents and reviews','document.read'),('validation','Readiness reviews','validation.read'),('migration_readiness','Migration planning','migration.read'),
        ('approvals','Department approvals','approval.read')]),
        ('Workspace settings','People, business rules and connected services.',[
        ('workspace_settings','Roles and operating rules','policy.read'),('policy','Business rules','policy.read'),('project_view_configuration','Sharing and audiences','policy.read'),('integration_readiness','Connections','integration.read'),
        ('operations','Business continuity','ops.read'),('private_evidence','Restricted documents','agent.data.read')])]
    sections=[]
    for title,description,items in specs:
        links=[{'label':label,'url':reverse(route,args=[case.pk])} for route,label,grant in items
               if all(key in actions for key in (grant if isinstance(grant,tuple) else (grant,)))]
        if title=='Workspace settings' and can_manage_access:links.append({'label':'People and access','url':reverse('case_access',args=[case.pk])})
        if links:sections.append({'title':title,'description':description,'links':links})
    return sections
