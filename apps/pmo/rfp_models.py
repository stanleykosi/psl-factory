from django.conf import settings
from django.db import models
from apps.core.models import AppendOnly


class RFPCase(models.Model):
    case=models.OneToOneField('core.Case',on_delete=models.PROTECT)
    tenant=models.CharField(max_length=100)
    reference=models.CharField(max_length=160)
    current_intake=models.ForeignKey('RFPIntake',null=True,on_delete=models.PROTECT,related_name='+')
    current_response=models.ForeignKey('RFPResponse',null=True,on_delete=models.PROTECT,related_name='+')
    class Meta:
        constraints=[models.UniqueConstraint(fields=['tenant','reference'],name='rfp_tenant_reference')]


class RFPIntake(AppendOnly):
    rfp=models.ForeignKey(RFPCase,on_delete=models.PROTECT,related_name='intakes')
    number=models.PositiveIntegerField()
    received_at=models.DateTimeField()
    deadline_status=models.CharField(max_length=20)
    deadline_at=models.DateTimeField(null=True)
    deadline_evidence=models.ForeignKey('core.Evidence',null=True,on_delete=models.PROTECT,related_name='+')
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    note=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['rfp','number'],name='rfp_intake_revision')]


class RFPAssignment(AppendOnly):
    intake=models.ForeignKey(RFPIntake,on_delete=models.PROTECT,related_name='assignments')
    pm=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    role=models.CharField(max_length=50)
    authority=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    note=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)


class RFPContribution(AppendOnly):
    intake=models.ForeignKey(RFPIntake,on_delete=models.PROTECT,related_name='contributions')
    team=models.CharField(max_length=30)

    received_at = models.DateTimeField(null=True, blank=True)
    source_party = models.CharField(max_length=160, null=True, blank=True)
    summary = models.CharField(max_length=4000, null=True, blank=True)
    person_days = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)


class RFPResponse(AppendOnly):
    def __str__(self):return f'Response #{self.pk} · revision {self.number}'
    rfp=models.ForeignKey(RFPCase,on_delete=models.PROTECT,related_name='responses')
    intake=models.ForeignKey(RFPIntake,on_delete=models.PROTECT)
    assignment=models.ForeignKey(RFPAssignment,on_delete=models.PROTECT)
    commercial=models.OneToOneField('pmo.CommercialRevision',on_delete=models.PROTECT)
    number=models.PositiveIntegerField()
    snapshot=models.JSONField()
    matrix=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['rfp','number'],name='rfp_response_revision')]


class RFPReview(AppendOnly):
    response=models.ForeignKey(RFPResponse,on_delete=models.PROTECT,related_name='reviews')
    role=models.CharField(max_length=50)
    verdict=models.CharField(max_length=20)
    authority=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT)
    note=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)


class RFPDocumentBinding(AppendOnly):
    def __str__(self):return f'Response #{self.response_id} · controlled version #{self.version_id}'
    version=models.OneToOneField('documents.Version',on_delete=models.PROTECT)
    response=models.ForeignKey(RFPResponse,on_delete=models.PROTECT)
    snapshot=models.JSONField()


class RFPSubmission(AppendOnly):
    def __str__(self):return f'Submission #{self.pk} · response #{self.response_id} · {self.submitted_at.isoformat()}'
    response=models.ForeignKey(RFPResponse,on_delete=models.PROTECT,related_name='submissions')
    version=models.OneToOneField('documents.Version',on_delete=models.PROTECT)
    snapshot=models.JSONField()
    receipt_ids=models.JSONField()
    submitted_at=models.DateTimeField()
    late=models.BooleanField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)


class RFPOutcome(AppendOnly):
    def __str__(self):return f'Outcome #{self.pk} · {self.result} · submission #{self.submission_id}'
    submission=models.ForeignKey(RFPSubmission,on_delete=models.PROTECT,related_name='outcomes')
    result=models.CharField(max_length=20)
    observed_at=models.DateTimeField()

    followup_on=models.DateField(null=True,blank=True)

    customer_expected_on = models.DateField(null=True, blank=True)

    remind_at = models.DateTimeField(null=True, blank=True)

    loss_reason = models.JSONField(default=dict, blank=True)
    debrief_version = models.ForeignKey('pmo.MeetingVersion', on_delete=models.PROTECT, null=True, blank=True)
    role=models.CharField(max_length=50)
    authority=models.JSONField()
    evidence=models.ForeignKey('core.Evidence',on_delete=models.PROTECT,null=True,blank=True)
    note=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)

    award_amount = models.DecimalField(max_digits=32, decimal_places=8, null=True, blank=True)
    award_currency = models.CharField(max_length=3, null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(result='unknown') | models.Q(evidence__isnull=False),
                                   name='rfp_asserted_outcome_has_evidence'),
            models.CheckConstraint(condition=models.Q(customer_expected_on__isnull=True) |
                                   models.Q(result='pending', evidence__isnull=False),
                                   name='rfp_customer_date_for_evidenced_pending'),
            models.CheckConstraint(condition=models.Q(remind_at__isnull=True) |
                                   models.Q(result__in=['pending', 'unknown'], followup_on__isnull=True,
                                            remind_at__gte=models.F('observed_at')),
                                   name='rfp_exact_reminder_open_outcome'),
            models.CheckConstraint(condition=(models.Q(award_amount__isnull=True, award_currency__isnull=True) |
                models.Q(result='won', award_amount__isnull=False, award_amount__gte=0, award_amount__lt=10**24,
                         award_currency__isnull=False, award_currency__regex=r'^[A-Z]{3}$')),
                name='rfp_award_complete_won_pair'),
        ]


class RFPDisposition(AppendOnly):
    rfp=models.OneToOneField(RFPCase,on_delete=models.PROTECT)
    outcome=models.OneToOneField(RFPOutcome,on_delete=models.PROTECT)
    kind=models.CharField(max_length=30)
    snapshot=models.JSONField()
    lessons=models.ForeignKey('core.Evidence',null=True,on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
