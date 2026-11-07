from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly
from .commercial_models import CommercialCase, CommercialRevision, CommercialDecision, CommercialDocumentBinding, ClientResponse, BaselineAdoption
from .change_models import ChangeRequest, ChangeVersion, ChangeAssessment, ChangeDecision, ChangeAuthorization, ChangeDocumentBinding, ChangeExecutionEvent, ChangeClosure
from .standard_models import StandardPreapproval, StandardBinding
from .rfp_models import RFPCase,RFPIntake,RFPAssignment,RFPContribution,RFPResponse,RFPReview,RFPDocumentBinding,RFPSubmission,RFPOutcome,RFPDisposition
from .delivery_models import DeliveryDossier,DeliverySource,DeliverySourceVerification,DeliveryRecord,DeliveryDocumentBinding,DeliverySignal,DeliveryScanCursor
from .recovery_models import AuthorityRecoveryRequest, AuthorityRecoveryDecision, AuthorityRecoveryRecord, EmergencyFollowup, EmergencyFollowupCompletion
from .emergency_models import EmergencyProfile, EmergencyDecision, EmergencyAuthorization, EmergencyOutcome, EmergencyReview, EmergencyRetrospectiveDecision, EmergencyRetrospectiveRecord, EmergencyDocumentBinding, EmergencyDeadlineSignal, EmergencyScanCursor
from .issue_models import Issue, IssueState, IssueClosureEntry
from .escalation_models import EscalationProfile, EscalationRequest, EscalationDecision, EscalationDocumentBinding, EscalationSignal, EscalationScanCursor


class Baseline(models.Model):
    case = models.OneToOneField('core.Case', on_delete=models.PROTECT)
    plan = models.ForeignKey('core.Evidence', on_delete=models.PROTECT, related_name='+')
    costing = models.ForeignKey('core.Evidence', on_delete=models.PROTECT, related_name='+')
    sow = models.ForeignKey('core.Evidence', on_delete=models.PROTECT, related_name='+')
    signed = models.ForeignKey('core.Evidence', null=True, on_delete=models.PROTECT, related_name='+')


class Decision(AppendOnly):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    role = models.CharField(max_length=50)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    policy = models.ForeignKey('policy.Configuration', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['evidence', 'role', 'policy'], name='decision_subject_role_policy')]


class Milestone(models.Model):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT, related_name='milestones')
    name = models.CharField(max_length=200)
    evidence = models.ForeignKey('core.Evidence', on_delete=models.PROTECT)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'name'], name='milestone_identity')]


class DeliveryCandidate(AppendOnly):
    def __str__(self):
        return self.reference

    case = models.ForeignKey('core.Case',on_delete=models.PROTECT)
    reference = models.CharField(max_length=160)
    requirements = models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','reference'],name='delivery_candidate_identity')]


class GateRecord(AppendOnly):
    candidate = models.ForeignKey(DeliveryCandidate,on_delete=models.PROTECT,related_name='gates')
    kind = models.CharField(max_length=40)
    external_ref = models.CharField(max_length=240)
    source_owner = models.CharField(max_length=60)
    evidence = models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=['candidate','kind','external_ref','evidence'],name='gate_source_identity')]


class GateVerification(AppendOnly):
    record = models.ForeignKey(GateRecord,on_delete=models.PROTECT,related_name='verifications')
    adapter = models.CharField(max_length=100)
    result = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class GateDocumentBinding(AppendOnly):
    version = models.OneToOneField('documents.Version',on_delete=models.PROTECT,related_name='gate_binding')
    candidate = models.ForeignKey(DeliveryCandidate,on_delete=models.PROTECT)
    manifest = models.JSONField()


class Meeting(models.Model):
    case = models.ForeignKey('core.Case',on_delete=models.PROTECT)
    reference = models.CharField(max_length=160)
    current = models.ForeignKey('MeetingVersion',null=True,on_delete=models.PROTECT,related_name='+')
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','reference'],name='formal_meeting_identity')]
    def __str__(self):return self.reference


class MeetingVersion(AppendOnly):
    meeting = models.ForeignKey(Meeting,on_delete=models.PROTECT,related_name='versions')
    number = models.PositiveIntegerField()
    kind = models.CharField(max_length=30)
    occurred_at = models.DateTimeField()
    purpose = models.CharField(max_length=240)
    summary = models.TextField()
    participant_ids = models.JSONField()
    decisions = models.JSONField()
    evidence = models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['meeting','number'],name='meeting_revision')]


class ActionItem(models.Model):
    case = models.ForeignKey('core.Case',on_delete=models.PROTECT)
    meeting = models.ForeignKey(Meeting,null=True,on_delete=models.PROTECT,related_name='actions')
    reference = models.CharField(max_length=160)
    current = models.ForeignKey('ActionState',null=True,on_delete=models.PROTECT,related_name='+')
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','reference'],name='action_identity')]
    def __str__(self):return self.reference


class ActionState(AppendOnly):
    item = models.ForeignKey(ActionItem,on_delete=models.PROTECT,related_name='states')
    number = models.PositiveIntegerField()
    description = models.CharField(max_length=1000)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.PROTECT,related_name='+')
    due_at = models.DateTimeField(null=True)
    due_basis = models.CharField(max_length=30,default='explicit')
    clock_meta = models.JSONField(default=dict)
    status = models.CharField(max_length=20,default='open')
    paused_at = models.DateTimeField(null=True)
    policies = models.JSONField(default=dict)
    evidence = models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    change_evidence = models.ForeignKey('core.Evidence',null=True,on_delete=models.PROTECT,related_name='+')
    reason = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['item','number'],name='action_revision')]


class PeriodReport(models.Model):
    case = models.ForeignKey('core.Case',on_delete=models.PROTECT)
    kind = models.CharField(max_length=30)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    audience = models.CharField(max_length=20)
    document = models.OneToOneField('documents.Document',null=True,on_delete=models.PROTECT)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','kind','start_at','end_at','audience'],name='report_period_identity')]


class MinutesReportBinding(AppendOnly):
    version = models.OneToOneField('documents.Version',on_delete=models.PROTECT)
    meeting = models.ForeignKey(Meeting,null=True,on_delete=models.PROTECT)
    report = models.ForeignKey(PeriodReport,null=True,on_delete=models.PROTECT)
    manifest = models.JSONField()
    policies = models.JSONField(default=dict)

    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(meeting__isnull=False,report__isnull=True)|models.Q(meeting__isnull=True,report__isnull=False),name='minutes_report_one_source')]


class ReportSchedule(models.Model):
    case = models.ForeignKey('core.Case',on_delete=models.PROTECT)
    kind = models.CharField(max_length=30)
    template = models.ForeignKey('documents.Template',on_delete=models.PROTECT)
    audience = models.CharField(max_length=20)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    status = models.CharField(max_length=20,default='draft')
    next_due_at = models.DateTimeField(null=True)
    next_start_at = models.DateTimeField(null=True)
    next_end_at = models.DateTimeField(null=True)
    policies = models.JSONField(default=dict)
    error = models.CharField(max_length=500,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['case','kind','audience'],name='report_schedule_identity')]


class ReportOccurrence(AppendOnly):
    schedule = models.ForeignKey(ReportSchedule,on_delete=models.PROTECT)
    due_at = models.DateTimeField()
    binding = models.ForeignKey(MinutesReportBinding,on_delete=models.PROTECT)
    policies = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['schedule','due_at'],name='scheduled_report_once')]


class MeetingActionLink(AppendOnly):
    meeting = models.ForeignKey(Meeting,on_delete=models.PROTECT,related_name='action_links')
    item = models.ForeignKey(ActionItem,on_delete=models.PROTECT)
    evidence = models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['meeting','item'],name='meeting_action_link_once')]

from .approval_models import ApprovalRequest,ApprovalContractReview,ApprovalRouteJob,ApprovalRouteReceipt,ApprovalSourceReceipt,ApprovalObservation,ApprovalGateBinding

from .costing_models import CostingRule,CostingOracle,CostingReview,CostingRun,CostingBinding,CostingAF13Binding
from .engagement_models import EngagementRecord,ProjectIdentifier
from .identity_resolution_models import ProjectIdentityDecision

from .issue_models import IssueReferenceContract, IssueReferenceObservation, IssueReferenceRevision

from .signature_models import CommercialSignaturePacket, CommercialSignatureUse, CommercialSignatureReaffirmation, BaselineSignatureExemption

from .progress_models import DeliveryProgressSource, DeliveryProgressObservation, DeliveryProgressCorrelation
