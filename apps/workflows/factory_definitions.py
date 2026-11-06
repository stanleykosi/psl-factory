"""Closed engineering envelopes; native departments retain decision authority."""
from django.core.exceptions import ValidationError

DEFINITIONS={
    'finance-ppe/v1':{'component':'OPS.factory_ppe_execution','read':'ppe.read','title':'Asset schedule and reviewed accounting note'},
    'finance-forecast/v1':{'component':'OPS.factory_forecast_execution','read':'finance.read','title':'Reviewed cash forecast and actual follow-up'},
    'finance-payroll/v1':{'component':'OPS.factory_payroll_execution','read':'payroll.read','title':'Restricted payroll and BU staff-cost receipt'},
    'pmo-emergency/v1':{'component':'OPS.factory_emergency_execution','read':'emergency.read','title':'Emergency preauthorization and retrospective evidence'},
    'pmo-change/v1':{'component':'OPS.factory_change_execution','read':'change.read','title':'Controlled change and signed closure'},
    'rfp-response/v1':{'component':'OPS.factory_rfp_execution','read':'rfp.read','title':'RFP response and project handoff'},
    'finance-accounts/v1':{'component':'OPS.factory_accounting_execution','read':'finance.read','title':'Accounting preparation and reviewed reports'},
    'pmo-finance/v1':{'component':'OPS.factory_execution','read':'finance.read','title':'Invoice preparation and delivery'},
    'planning/v1':{'component':'OPS.factory_planning_execution','read':'planning.read','title':'Planning and delivery handoff'},
    'commercial/v1':{'component':'OPS.factory_commercial_execution','read':'case.read','title':'Costing and commercial submission'},
    'delivery-release/v1':{'component':'OPS.factory_delivery_execution','read':'delivery.read','title':'Delivery gates and release evidence'},
    'delivery-hypercare/v1':{'component':'OPS.factory_hypercare_execution','read':'delivery.read','title':'Release observations and hypercare'},
    'delivery-archive/v1':{'component':'OPS.factory_archive_execution','read':'delivery.read','title':'Project artifact archive'},
    'delivery-handover/v1':{'component':'OPS.factory_handover_execution','read':'delivery.read','title':'Support and Operations handover'},
    'delivery-closure/v1':{'component':'OPS.factory_closure_execution','read':'delivery.read','title':'Project closure'},
    'delivery-go-live/v1':{'component':'OPS.factory_go_live_execution','read':'delivery.read','title':'Go-live acceptance'},
}

def definition(name):
    try:return DEFINITIONS[name]
    except KeyError:raise ValidationError('unknown_case: no registered factory definition')
