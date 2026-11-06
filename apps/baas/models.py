from django.db import models
from .partner_models import PartnerRecord,PartnerDecision,OnboardingEvent,PartnerReport,PartnerReportReview,PartnerFollowup,PartnerFinanceJob,PartnerFinanceReceipt,PartnerBillingImport,PartnerMeterClaim
from .reconciliation_models import ReconciliationBatch,ReconciliationAttestation,ReconciliationRun,CorrectiveRequest,CorrectiveDecision,CorrectiveJob,CorrectiveDelivery,EngineeringOutcome,OutcomeVerification

class SupportCase(models.Model):
    case = models.OneToOneField('core.Case', on_delete=models.PROTECT)
    channel = models.CharField(max_length=100)
    external_ref = models.CharField(max_length=200)
    status = models.CharField(max_length=20, default='open')
    resolution = models.ForeignKey('core.Evidence', on_delete=models.PROTECT, null=True)
    first_response_at = models.DateTimeField(null=True)
    resolved_at = models.DateTimeField(null=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['channel', 'external_ref'], name='support_intake_identity')]

from .support_models import SupportIntake,SupportLink,SupportEvent,SupportResult,SupportReport,SupportReview,SupportMerge
from .support_agent_models import SupportProjection,SupportAgentDraft,SupportAgentDraftReview

from .support_release_models import SupportResponsePacket,SupportResponseDecision,SupportResponseJob,SupportResponseReceipt

from .support_channel_models import SupportChannelClaim,SupportChannelCheck,SupportChannelReceipt,SupportChannelReview,SupportClockAttestation,SupportClockCorrection,SupportClockCorrectionReview
from .summary_models import ComplaintSummaryRequest,ComplaintSummaryVersion,ComplaintSummaryReview
