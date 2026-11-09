from django.db import models
from apps.core.models import AppendOnly


class SignedBaselineIntake(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    adoption = models.OneToOneField('pmo.BaselineAdoption', on_delete=models.PROTECT)
    operation_key = models.CharField(max_length=160, unique=True)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)


class Handoff(models.Model):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    milestone = models.OneToOneField('pmo.Milestone', on_delete=models.PROTECT)
    operation_key = models.CharField(max_length=200, unique=True)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)


class FinancialImport(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    evidence = models.OneToOneField('core.Evidence', on_delete=models.PROTECT)
    source_sha256 = models.CharField(max_length=64)
    rows = models.JSONField()
    findings = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'source_sha256'], name='financial_import_content_identity')]


class ImportValidation(AppendOnly):
    batch = models.ForeignKey(FinancialImport, on_delete=models.PROTECT)
    policies = models.JSONField()
    findings = models.JSONField()
    status = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)


class InvoicePreparation(models.Model):
    handoff = models.OneToOneField(Handoff, on_delete=models.PROTECT)
    status = models.CharField(max_length=30, default='evidence_received')
    created_at = models.DateTimeField(auto_now_add=True)

from .analysis_models import FinanceSource,FinanceAdjustment,FinanceRun,FinanceReview,FinanceDocumentBinding
from .performance_models import FinanceBudget,FinancePeriod,FinanceRestatement,FinancePerformance,FinancePerformanceDecision,FinancePerformanceBinding

from .billing_models import BillingCoverage,BillingUsage,BillingPreparation

from .settlement_models import Invoice,InvoiceReview,InvoiceJob,InvoiceIssue,InvoiceDelivery,CashReceipt,CashVerification,CashAssignment,CashAllocation,CashReversal,ReceivableSnapshot

from .correction_models import InvoiceCorrection,CashSuccessor,FinancialCorrectionReview,InvoiceCorrectionAcceptance,InvoiceCorrectionDelivery,CashSuccessorAcceptance
from .forecast_models import ForecastItemSupport,ForecastScenario,ForecastRun,ForecastReview,ForecastActual,ForecastActualVerification,ForecastMatch,ForecastBinding,ForecastMatchReversal,ForecastPriority
from .payment_models import PaymentAssessment,PaymentException,PaymentDecision,PaymentReleaseReservation

from .recognition_models import ProgressPacket,RecognitionRecord

from .hrfinance_models import HRFinanceNeed,HRDisclosure,HRReadSnapshot,HRHandoffRecord

from .payroll_models import PayrollRequest,PayrollInput,PayrollRun,PayrollReview,PayrollPublication,PayrollReportReceipt,PayrollHRFollowup

from .bu_models import BUWork,BUReview,BUReport,BUReceipt,BUEventClaim

from .schedule_models import ScheduleWork,ScheduleReview,ScheduleAdjustment

from .ledger_models import LedgerLineage,LedgerCheck,LedgerDecision,LedgerResolution,LedgerResolutionMember,LedgerResolutionReview

from .d03_models import BillingEvidenceSource,BillingEvidenceReview,BillingReleaseProfile,BillingControlReceipt,BillingReleaseAssessment,BillingReleaseBinding

from .ledger_agent_models import LedgerProjection,LedgerAgentDraft,LedgerAgentDraftReview

from .acceptance_models import FinanceHandoff,FinanceHandoffDecision

from .acceptance_models import AcceptedFinanceDocument

from .acceptance_models import FinancePublicationReadiness
from .acceptance_models import PrivateReadinessPacket
from .receipt_followup_models import FinanceReceiptFollowup,FinanceReceiptFollowupDecision
from .followup_successor_models import FinanceFollowupSuccessor,FinanceFollowupSuccessorReview
from .transport_models import FinanceAuthenticatedIntake

from .statement_models import FinanceStatementInput,FinanceStatementPPEInput,FinanceStatementPPEProjection

from .coverage_models import (CoverageAccess, CoverageSource, CoverageTerms, CoverageTermsEvent,
    CoverageInvoiceReference, CoverageAssessment, CoveragePreparationRequest, CoveragePreparationReceipt, CoveragePreparationRoute, CoverageEvidenceScope)

from .fixed_charge_models import CoverageFixedCharge, CoverageNativePreparation, CoveragePreparationContinuation

from .usage_intake_models import UsageIntakeSource, UsageIntakeReceipt, UsageIntakeAcceptance, UsageIntakeWithdrawal

from .draft_generation_models import DraftGeneration, DraftGenerationAttempt, DraftGenerationObservation, DraftGenerationCancellation

from .obligation_models import ObligationNamespace, ObligationClaim, ObligationLocalKey, ObligationAlias, ObligationBinding, ObligationEffect
from .obligation_models import ObligationLegacyAttempt, ObligationLegacyObservation
