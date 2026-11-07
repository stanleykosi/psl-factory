from django.conf import settings
from django.db import models


class Outbox(models.Model):
    case = models.ForeignKey('core.Case', on_delete=models.PROTECT)
    milestone = models.OneToOneField('pmo.Milestone', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    operation_key = models.CharField(max_length=200, unique=True)
    payload = models.JSONField()
    status = models.CharField(max_length=20, default='pending')
    lease_until = models.DateTimeField(null=True)
    fence = models.PositiveIntegerField(default=0)
    attempts = models.PositiveIntegerField(default=0)
    receipt = models.CharField(max_length=200, blank=True)
    error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class HumanTask(models.Model):
    case = models.ForeignKey('core.Case',on_delete=models.PROTECT)
    version = models.OneToOneField('documents.Version',on_delete=models.PROTECT,null=True)
    kind = models.CharField(max_length=32,default='document_review')
    factory_key = models.CharField(max_length=200,null=True,unique=True)
    context = models.JSONField(default=dict)
    claimed_by = models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.PROTECT,related_name='claimed_human_tasks')
    revision = models.PositiveIntegerField(default=1)
    required_role = models.CharField(max_length=50,default='PMO Lead')
    status = models.CharField(max_length=20,default='open')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class TaskEvent(models.Model):
    task = models.ForeignKey(HumanTask,on_delete=models.PROTECT,related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    action = models.CharField(max_length=30)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

from .operator_models import OperatorInventory,RecoveryPlan,RecoveryProof,RecoveryJob,RecoveryArtifact,RecoveryAssessment,RecoveryReview

from .readiness_models import AcceptedProtectionReadiness,PrivateFileReadiness,PrivateProtectionReadiness,IntegrationContract,IntegrationProbe,IntegrationObservation,IntegrationAssessment,IntegrationReview,IntegrationSelection

from .application_recovery_models import RecoveryAttachment,ApplicationRecoveryPlan,ApplicationRecoveryJob,ApplicationRecoveryReview
from .cold_recovery_models import ColdControlIdentity,ColdRecoveryPlan,ColdRecoveryReview,ColdRecoveryJob
from .reconstitution_models import ReconstitutionPlan,ReconstitutionJob,ReconstitutionDisposition,ReconstitutionReview
from .domain_contract_models import DomainContract,DomainObservation,DomainContractReview
from .native_finance_models import NativeFinanceMapping,NativeFinanceObservation,NativeFinancePacket,NativeFinanceReview,NativeFinancePublicationJob
from .finance_readback_models import FinanceFollowupReadback,FinanceFollowupReadbackReview
from .followup_transport_models import FinanceFollowupDispatch
from .factory_models import FactoryWork,FactoryActivity,FactoryAttempt
from .factory_planning_models import FactoryPlanningReceipt,FactoryPlanningRecovery,FactoryPlanningReceiptUse
from .factory_execution_models import FactoryExecutionBinding
from .change_intake_models import ChangeIntakeConfirmation

from .factory_models import FactoryInvoicePreparationBinding
