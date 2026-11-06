from adapters.approvals import SuppliedApprovalReadAdapter
class SuppliedBillingEvidenceAdapter(SuppliedApprovalReadAdapter):
 """Strict supplied control observations, not an authenticated Power Automate reader."""
 pass
class LocalBillingEvidenceReportAdapter:
 def read(self,actor,case_id,assessment_id):
  from apps.finance.billing_evidence import report
  return report(actor,case_id,assessment_id)
