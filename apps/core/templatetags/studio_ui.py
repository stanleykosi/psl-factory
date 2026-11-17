"""Presentation only: stored records, evidence and authority remain unchanged."""
from decimal import Decimal

from django import template
register=template.Library()

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


@register.inclusion_tag('factory/background_status.html', takes_context=True)
def factory_background_status(context, work):
    from apps.workflows.factory import TERMINAL
    from apps.workflows.factory_execution import can_control
    from apps.workflows.factory_progress import ACTIVE
    from apps.workflows.models import FactoryProgress, FactoryWork

    if not isinstance(work, FactoryWork):
        return {}
    job = FactoryProgress.objects.filter(work=work).first()
    return {'work': work, 'job': job, 'active': bool(job and job.status in ACTIVE),
            'can_control': can_control(context['user'], work), 'csrf_token': context.get('csrf_token'),
            'can_continue': not work.cancel_requested and work.status not in TERMINAL | {'waiting_effect'}}


from apps.core.presentation import workspace_name
register.filter('workspace_name',workspace_name)

@register.filter
def readable(value):return str(value or '').replace('_',' ').replace('.',' · ').strip().capitalize()


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
        'design_overview':'Factory overview','design_agents':'Assistant','design_project':'Project journey',
        'design_project_tab':'Project journey','design_company_month_end':'Month-end','design_project_action':'Project action',
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
        ('policy','Business rules','policy.read'),('project_view_configuration','Sharing and audiences','policy.read'),('integration_readiness','Connections','integration.read'),
        ('operations','Business continuity','ops.read'),('private_evidence','Restricted documents','agent.data.read')])]
    sections=[]
    for title,description,items in specs:
        links=[{'label':label,'url':reverse(route,args=[case.pk])} for route,label,grant in items
               if all(key in actions for key in (grant if isinstance(grant,tuple) else (grant,)))]
        if title=='Workspace settings' and can_manage_access:links.append({'label':'People and access','url':reverse('case_access',args=[case.pk])})
        if links:sections.append({'title':title,'description':description,'links':links})
    return sections
