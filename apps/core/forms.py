from django import forms

EVIDENCE_KINDS = ['usage_intake_source','usage_intake_controls','usage_intake_withdrawal','engagement_source','engagement_assignment','engagement_registration','ppe_register','ppe_opening','ppe_classification','ppe_event','ppe_policy','ppe_basis_explanation','income_detail','schedule_inventory','schedule_workbook','bu_pool_contract','bu_source_contract','bu_design_decision','bu_review','payroll_need','payroll_source_contract','payroll_review','hr_finance_need','hr_contract_source','hr_disclosure_decision','hr_correction_request','hr_correction_response','progress_estimate','progress_acceptance','progress_price','progress_packet','recognition_policy','recognition_decision','procedure_source','owner_validation','validation_example','validation_result','validation_acceptance','payment_exception_request','payment_exception_decision','partner_agreement','partner_onboarding','partner_activity','partner_decision','partner_stage','reconciliation_input','reconciliation_attestation','corrective_request','corrective_decision','engineering_outcome','engineering_outcome_verification','forecast_input','forecast_opening','forecast_review','forecast_actual','forecast_actual_verification','forecast_match','forecast_oracle','invoice_credit_note','invoice_debit_note','invoice_void_note','financial_correction_review','invoice_review','cash_report','cash_verification','cash_allocation','cash_correction','billing_coverage','billing_usage','billing_oracle','finance_budget','finance_budget_approval','finance_restatement','finance_source','finance_review','finance_adjustment','finance_oracle','finance_basis','rfp_commercial_terms','rfp_intake','rfp_deadline','rfp_response','rfp_outcome','rfp_lessons','qa_estimate','product_input','requirements', 'engineering_estimate', 'security_estimate', 'plan', 'costing', 'sow', 'signature', 'completion', 'document', 'support_message', 'resolution', 'policy_decision', 'financial_input', 'meeting_notes', 'change_request', 'client_feedback', 'incident']
class EvidenceForm(forms.Form):
    kind = forms.ChoiceField(choices=[(k, k.replace('_', ' ').title()) for k in EVIDENCE_KINDS + ['deployment_checklist','incident_reporting','rollback_plan','technical_document','test_results','project_artifact','support_document','escalation_document','closure_report','incident_classification','emergency_decision','post_implementation_review','change_procedure','change_preapproval','change_procedure_match','change_implementation','change_validation','risk_reference','root_cause','issue_impact']])
    body = forms.CharField(widget=forms.Textarea, max_length=100000)
    source = forms.CharField(max_length=500)

class PolicyForm(forms.Form):
    envelope = forms.JSONField(widget=forms.Textarea(attrs={'rows': 22, 'spellcheck': 'false'}))

class ReferenceForm(forms.Form):
    ref = forms.CharField(max_length=150)
    schema_ref = forms.CharField(max_length=200)
    content = forms.JSONField(widget=forms.Textarea(attrs={'rows': 5}))
    evidence_id = forms.IntegerField(min_value=1, label='Owner decision evidence ID')
